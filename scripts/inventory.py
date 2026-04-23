"""Auto-Inventory: scannt Claude-Code-Ressourcen + lokale Projekte, schreibt INVENTORY.md in den Obsidian-Vault.

Aufrufbar standalone, via SessionStart-Hook oder Scheduled Task.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from config import VAULT_DIR, now_iso

# ── Pfade ──────────────────────────────────────────────────────────────
CLAUDE_DIR = Path.home() / ".claude"
SKILLS_DIR = CLAUDE_DIR / "skills"
AGENTS_DIR = CLAUDE_DIR / "agents"
PLUGINS_FILE = CLAUDE_DIR / "plugins" / "installed_plugins.json"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
PROJECTS_DIR = Path(r"C:\Projekte")
OUTPUT_FILE = VAULT_DIR / "INVENTORY.md"

# ── Projekt-Klassifizierung ───────────────────────────────────────────
PROJECT_CATEGORIES: dict[str, str] = {
    "kommandozentrale": "Infra",
    "kommandozentrale-jarvis": "Infra",
    "wissensspeicher": "Infra",
    "entruencer-synapse": "Produkt",
    "webforge": "Produkt",
    "meta-publisher": "Produkt",
    "outlook-buddy": "Produkt",
    "hooker-ai": "Produkt",
    "deine-nicci-entscheidungs-tool": "Kunde",
    "token-dashboard": "Archiv",
}
DEFAULT_CATEGORY = "Experiment"


# ── Datentypen ─────────────────────────────────────────────────────────
@dataclass
class Skill:
    name: str
    description: str
    path: str
    empty: bool = False


@dataclass
class Plugin:
    id: str
    version: str
    scope: str
    enabled: bool


@dataclass
class MCP:
    name: str
    url: str
    status: str


@dataclass
class Hook:
    event: str
    command: str


@dataclass
class Project:
    name: str
    category: str
    has_git: bool
    has_claude_md: bool


@dataclass
class Inventory:
    skills: list[Skill] = field(default_factory=list)
    plugins: list[Plugin] = field(default_factory=list)
    mcps: list[MCP] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)
    agents: list[Skill] = field(default_factory=list)  # gleiche Struktur wie Skills
    projects: list[Project] = field(default_factory=list)


# ── Scanner ────────────────────────────────────────────────────────────
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str]:
    """Minimaler YAML-Frontmatter-Parser (flache key: value-Paare, inkl. multiline-Werte)."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    result: dict[str, str] = {}
    current_key: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        # neuer Key?
        m = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", line)
        if m and not line.startswith(" "):
            current_key = m.group(1)
            value = m.group(2).strip()
            if value in ("", ">", "|"):
                result[current_key] = ""
            else:
                result[current_key] = value.strip('"').strip("'")
        elif current_key and line.startswith(" "):
            # Fortsetzungszeile
            result[current_key] = (result.get(current_key, "") + " " + line.strip()).strip()
    return result


def scan_skills(base: Path) -> list[Skill]:
    """Scannt Skill-Ordner: sucht SKILL.md + parst Frontmatter."""
    if not base.exists():
        return []
    results: list[Skill] = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            results.append(Skill(name=entry.name, description="(kein SKILL.md)", path=str(entry), empty=True))
            continue
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        results.append(
            Skill(
                name=fm.get("name", entry.name),
                description=fm.get("description", "").strip(),
                path=str(skill_md),
            )
        )
    return results


def scan_plugins() -> tuple[list[Plugin], set[str]]:
    """Liest installed_plugins.json + settings.enabledPlugins."""
    if not PLUGINS_FILE.exists():
        return [], set()
    data = json.loads(PLUGINS_FILE.read_text(encoding="utf-8"))
    enabled: set[str] = set()
    if SETTINGS_FILE.exists():
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        enabled = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
    result: list[Plugin] = []
    for plugin_id, installs in data.get("plugins", {}).items():
        for inst in installs:
            result.append(
                Plugin(
                    id=plugin_id,
                    version=inst.get("version", "unknown"),
                    scope=inst.get("scope", "?"),
                    enabled=plugin_id in enabled,
                )
            )
    return result, enabled


def scan_mcps() -> list[MCP]:
    """Ruft `claude mcp list` auf und parst die Ausgabe."""
    claude_exe = Path.home() / ".local" / "bin" / "claude.exe"
    cmd = str(claude_exe) if claude_exe.exists() else "claude"
    try:
        proc = subprocess.run(
            [cmd, "mcp", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    result: list[MCP] = []
    for line in proc.stdout.splitlines():
        # Format: "claude.ai Canva: https://mcp.canva.com/mcp - ✓ Connected"
        m = re.match(r"^(.*?):\s*(https?://\S+)\s*-\s*(.+)$", line.strip())
        if m:
            result.append(MCP(name=m.group(1).strip(), url=m.group(2), status=m.group(3).strip()))
    return result


def scan_hooks() -> list[Hook]:
    """Liest Hook-Konfiguration aus settings.json."""
    if not SETTINGS_FILE.exists():
        return []
    settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    result: list[Hook] = []
    for event, entries in settings.get("hooks", {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                result.append(Hook(event=event, command=hook.get("command", "")))
    return result


def scan_projects(base: Path) -> list[Project]:
    if not base.exists():
        return []
    result: list[Project] = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        result.append(
            Project(
                name=entry.name,
                category=PROJECT_CATEGORIES.get(entry.name, DEFAULT_CATEGORY),
                has_git=(entry / ".git").exists(),
                has_claude_md=(entry / "CLAUDE.md").exists(),
            )
        )
    return result


# ── Rendering ──────────────────────────────────────────────────────────
def render(inv: Inventory) -> str:
    lines: list[str] = []
    lines.append("# Inventory")
    lines.append("")
    lines.append(f"_Auto-generated: {now_iso()}_")
    lines.append("")
    lines.append("_Quelle: `~/.claude/` + `C:\\Projekte\\`. Nicht manuell bearbeiten — wird überschrieben._")
    lines.append("")

    # Skills
    lines.append("## Skills (eigene)")
    lines.append("")
    if inv.skills:
        lines.append("| Name | Beschreibung | Status |")
        lines.append("|---|---|---|")
        for s in inv.skills:
            desc = s.description.replace("\n", " ").replace("|", "\\|")
            if len(desc) > 120:
                desc = desc[:117] + "…"
            status = "⚠️ leer" if s.empty else "✓"
            lines.append(f"| `{s.name}` | {desc} | {status} |")
    else:
        lines.append("_keine_")
    lines.append("")

    # Plugins
    lines.append("## Plugins")
    lines.append("")
    if inv.plugins:
        lines.append("| ID | Version | Scope | Enabled |")
        lines.append("|---|---|---|---|")
        for p in inv.plugins:
            lines.append(f"| `{p.id}` | {p.version} | {p.scope} | {'✓' if p.enabled else '—'} |")
    else:
        lines.append("_keine_")
    lines.append("")

    # MCPs
    lines.append("## MCP-Server")
    lines.append("")
    if inv.mcps:
        lines.append("| Name | URL | Status |")
        lines.append("|---|---|---|")
        for m in inv.mcps:
            lines.append(f"| {m.name} | `{m.url}` | {m.status} |")
    else:
        lines.append("_keine oder `claude mcp list` nicht erreichbar_")
    lines.append("")

    # Agents
    lines.append("## Agents (eigene)")
    lines.append("")
    if inv.agents:
        lines.append("| Name | Beschreibung |")
        lines.append("|---|---|")
        for a in inv.agents:
            desc = a.description.replace("\n", " ").replace("|", "\\|")
            if len(desc) > 120:
                desc = desc[:117] + "…"
            lines.append(f"| `{a.name}` | {desc} |")
    else:
        lines.append("_keine — nur Built-ins + Plugin-Agents aktiv_")
    lines.append("")

    # Hooks
    lines.append("## Hooks")
    lines.append("")
    if inv.hooks:
        lines.append("| Event | Command |")
        lines.append("|---|---|")
        for h in inv.hooks:
            cmd = h.command.replace("|", "\\|")
            if len(cmd) > 160:
                cmd = cmd[:157] + "…"
            lines.append(f"| `{h.event}` | {cmd} |")
    else:
        lines.append("_keine_")
    lines.append("")

    # Projekte
    lines.append("## Projekte (`C:\\Projekte\\`)")
    lines.append("")
    grouped: dict[str, list[Project]] = {}
    for p in inv.projects:
        grouped.setdefault(p.category, []).append(p)
    for category in ["Infra", "Produkt", "Kunde", "Experiment", "Archiv"]:
        items = grouped.get(category, [])
        if not items:
            continue
        lines.append(f"### {category}")
        lines.append("")
        lines.append("| Name | Git | CLAUDE.md |")
        lines.append("|---|---|---|")
        for p in items:
            lines.append(f"| `{p.name}` | {'✓' if p.has_git else '—'} | {'✓' if p.has_claude_md else '—'} |")
        lines.append("")

    return "\n".join(lines) + "\n"


# ── Main ───────────────────────────────────────────────────────────────
def build_inventory() -> Inventory:
    inv = Inventory()
    inv.skills = scan_skills(SKILLS_DIR)
    inv.plugins, _ = scan_plugins()
    inv.mcps = scan_mcps()
    inv.hooks = scan_hooks()
    inv.agents = scan_skills(AGENTS_DIR)  # wenn vorhanden, selbe Struktur wie Skills
    inv.projects = scan_projects(PROJECTS_DIR)
    return inv


def main() -> None:
    inv = build_inventory()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(render(inv), encoding="utf-8")
    print(f"OK -> {OUTPUT_FILE}")
    print(
        f"  Skills: {len(inv.skills)} | Plugins: {len(inv.plugins)} | "
        f"MCPs: {len(inv.mcps)} | Hooks: {len(inv.hooks)} | "
        f"Agents: {len(inv.agents)} | Projekte: {len(inv.projects)}"
    )


if __name__ == "__main__":
    main()
