# Claude Memory Compiler

[![Fork](https://img.shields.io/badge/Fork%20von-coleam00%2Fclaude--memory--compiler-181717.svg?logo=github)](https://github.com/coleam00/claude-memory-compiler)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab.svg)
![Claude Agent SDK](https://img.shields.io/badge/Claude%20Agent%20SDK-aktiv-d97757.svg)
![uv](https://img.shields.io/badge/uv-managed-de5fe9.svg)

> **Fork-Hinweis:** Dies ist ein Fork von
> **[coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler)**.
> Die Architektur und der Großteil des Codes stammen von Cole Medin (coleam00), inspiriert
> von [Karpathys LLM-Knowledge-Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
> Dieser Fork ergänzt das Original um ein **Auto-Inventory-Script** und einen
> **SessionStart-Hook-Trigger** (siehe [Erweiterungen in diesem Fork](#erweiterungen-in-diesem-fork)).

Deine KI-Unterhaltungen kompilieren sich selbst zu einer durchsuchbaren Wissensdatenbank.
Statt Web-Artikel zu sammeln, sind die Rohdaten deine eigenen Sessions mit Claude Code.
Wenn eine Session endet (oder mitten drin auto-komprimiert), greifen Claude-Code-Hooks das
Transkript ab und starten einen Hintergrundprozess. Der nutzt das
[Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk), um das Wichtige zu
extrahieren - Entscheidungen, Lessons Learned, Muster, Stolperfallen - und hängt es an ein
Tageslog an. Aus diesen Tageslogs werden strukturierte, querverlinkte Wissensartikel nach
Konzept kompiliert. Das Retrieval läuft über eine einfache Index-Datei statt RAG - keine
Vektordatenbank, keine Embeddings, nur Markdown.

Die private Nutzung des Claude Agent SDK ist laut Anthropic über das bestehende
Claude-Abo (Max, Team oder Enterprise) abgedeckt - keine separaten API-Credits nötig.

---

## Was das System macht

- **Hooks** greifen Unterhaltungen automatisch ab (Session-Ende plus PreCompact als
  Sicherheitsnetz).
- **flush.py** ruft das Claude Agent SDK auf, entscheidet was speicherwürdig ist, und
  stößt nach 18 Uhr automatisch die Tageskompilierung an.
- **compile.py** macht aus Tageslogs organisierte Konzept-Artikel mit Querverweisen
  (automatisch oder manuell ausführbar).
- **query.py** beantwortet Fragen per index-geführtem Retrieval (kein RAG bei
  persönlicher Größenordnung nötig).
- **lint.py** fährt 7 Health-Checks (tote Links, verwaiste Artikel, Widersprüche,
  Veralterung).

---

## So funktioniert es

```text
Unterhaltung -> SessionEnd/PreCompact-Hooks -> flush.py extrahiert Wissen
    -> daily/YYYY-MM-DD.md -> compile.py -> knowledge/concepts/, connections/, qa/
        -> SessionStart-Hook injiziert Index in die nächste Session -> Kreislauf
```

---

## Schnellstart

Sag deinem KI-Coding-Agenten:

> "Klone https://github.com/m-entruencer/claude-memory-compiler in dieses Projekt. Richte
> die Claude-Code-Hooks ein, damit meine Unterhaltungen automatisch in Tageslogs erfasst,
> zu einer Wissensdatenbank kompiliert und in künftige Sessions zurückgespielt werden. Lies
> die AGENTS.md für die vollständige technische Referenz."

Der Agent wird:

1. Das Repo klonen und `uv sync` für die Abhängigkeiten ausführen
2. `.claude/settings.json` ins Projekt kopieren (oder die Hooks in deine bestehenden
   Settings mergen)
3. Die Hooks aktivieren sich beim nächsten Öffnen von Claude Code automatisch

Ab da sammeln sich deine Unterhaltungen. Nach 18 Uhr Ortszeit stößt der nächste Flush die
Kompilierung des Tages automatisch an. Manuell jederzeit per
`uv run python scripts/compile.py`.

---

## Wichtige Befehle

```bash
uv run python scripts/compile.py                     # neue Tageslogs kompilieren
uv run python scripts/query.py "Frage"               # die Wissensdatenbank fragen
uv run python scripts/query.py "Frage" --file-back   # fragen + Antwort zurückspeichern
uv run python scripts/lint.py                        # Health-Checks
uv run python scripts/lint.py --structural-only      # nur kostenlose Struktur-Checks
uv run python scripts/inventory.py                   # Auto-Inventory schreiben (Fork)
```

---

## Erweiterungen in diesem Fork

Gegenüber dem Original von coleam00 ergänzt dieser Fork:

- **`scripts/inventory.py` (Auto-Inventory)** - scannt Claude-Code-Ressourcen (Skills,
  Agents, Plugins) plus lokale Projekte und schreibt eine `INVENTORY.md` in den Vault.
  Standalone, per SessionStart-Hook oder als Scheduled Task aufrufbar.
- **SessionStart-Hook-Trigger** - bindet den Inventory-Lauf in den Session-Start ein, damit
  der Überblick aktuell bleibt.

Die Pfade in `inventory.py` (z.B. Projektverzeichnis, Kategorien) sind auf das eigene Setup
zugeschnitten und vor dem Einsatz anzupassen.

---

## Warum kein RAG?

Karpathys Einsicht: Bei persönlicher Größenordnung (50 bis 500 Artikel) schlägt das LLM,
das eine strukturierte `index.md` liest, die Vektor-Ähnlichkeit. Das LLM versteht, was du
wirklich fragst; Cosine-Similarity findet nur ähnliche Wörter. RAG wird erst ab ~2.000
Artikeln nötig, wenn der Index das Kontextfenster sprengt.

---

## Technische Referenz

Siehe **[AGENTS.md](AGENTS.md)** für die vollständige technische Referenz: Artikel-Formate,
Hook-Architektur, Script-Interna, Cross-Platform-Details, Kosten und Anpassungsoptionen.
Die AGENTS.md ist so angelegt, dass ein KI-Agent damit alles hat, um das System zu
verstehen, zu ändern oder neu zu bauen.

---

## Lizenz & Credits

Architektur und Kern-Code von **[Cole Medin (coleam00)](https://github.com/coleam00/claude-memory-compiler)**,
inspiriert von Andrej Karpathy. Die Fork-Erweiterungen stammen von der
**[Entruencer UG (haftungsbeschränkt)](https://entruencer.de/)**.

Für die Lizenzbedingungen gilt das [Upstream-Repository](https://github.com/coleam00/claude-memory-compiler).
