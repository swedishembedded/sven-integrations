---
name: integrations/drawio
description: |
  Use when asked to create or edit Draw.io diagrams, flowcharts, architecture
  diagrams, network diagrams, UML diagrams, entity-relationship diagrams, or any
  other structured diagram format. Trigger phrases: "create diagram", "flowchart",
  "architecture diagram", "network topology", "draw.io", "UML diagram", "ERD".
version: 2.2.0
sven:
  requires_bins: [sven-integrations-drawio]
---

# sven-integrations-drawio

Stateful CLI for creating and editing Draw.io `.drawio` / `.xml` diagrams. Stores
a diagram model in a JSON project file. Does not require Draw.io desktop for any
operation except `export` (PNG/PDF/VSDX).

## Minimal working example — simple flowchart

```bash
P=/tmp/drawio_project.json

# 1. Create a new document
sven-integrations-drawio --json -p "$P" new --name "My Flowchart"

# 2. Add shapes (capture cell_id from each response)
sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Start" --x 200 --y 50
sven-integrations-drawio --json -p "$P" shape add --type rhombus --label "Decision?" --x 175 --y 170 --width 250 --height 80
sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Action A" --x 100 --y 330
sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Action B" --x 340 --y 330

# 3. Add connectors (--from and --to take cell IDs from the add output above)
sven-integrations-drawio --json -p "$P" connector add --from <START_ID> --to <DECISION_ID>
sven-integrations-drawio --json -p "$P" connector add --from <DECISION_ID> --to <ACTIONA_ID> --label "Yes"
sven-integrations-drawio --json -p "$P" connector add --from <DECISION_ID> --to <ACTIONB_ID> --label "No"

# 4. Save to .drawio XML and render a standalone SVG (viewable in Cursor, any browser/image viewer)
sven-integrations-drawio --json -p "$P" save /tmp/diagram.drawio
sven-integrations-drawio --json -p "$P" svg /tmp/diagram.svg

# 5. Verify
ls -lh /tmp/diagram.drawio /tmp/diagram.svg
```

## Key rules for agents

1. **Always run `new` first** to create a fresh document with at least one page.
2. **Always pass `-p /absolute/path/to/project.json`** to persist state.
3. **Shape `add` returns a `cell_id`** — capture it immediately for connector `--from` and `--to`.
4. **`export` requires Draw.io desktop** — use `save /path/to/diagram.drawio` to write XML and `svg /path/to/diagram.svg` to render a viewable image (neither requires the desktop app).
5. **Coordinates are in diagram units (pixels at 100% zoom)** — typical values: x/y 50–800, width/height 120–200 for labels.
6. **Page management** — multi-page diagrams use `page add` and `page remove`; shapes go on the first page by default.
7. **Use `shape list`** to inspect all shapes and capture cell IDs for connectors.
8. **Cell IDs are unique per document** — if you run `new` or delete the project file, ALL previous cell IDs become invalid. Never reuse cell IDs from a previous shell run or a different document.

## Recommended workflow for agents (two-phase)

**Phase 1 — Shapes only:** Run one shell with `new` and all `shape add` commands. Do NOT add connectors yet.

**Phase 2 — Connectors:** Parse `cell_id` from Phase 1 output (or run `shape list`), then run a separate shell with `connector add` commands using those IDs.

**Phase 3 — Save:** Run `save /path/to/diagram.drawio` for the `.drawio` file, and `svg /path/to/diagram.svg` to render a standalone SVG (viewable in Cursor's file preview, any image viewer, or browser — no external tools required).

Do NOT mix connector commands with shape add in the same script unless you already have valid cell IDs from the current run.

## Command reference

### document commands (top-level)
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create new document | `--name NAME` |
| `open PATH` | Load existing .drawio file | — |
| `save PATH` | Save diagram to .drawio XML | — |
| `svg PATH` | Render standalone SVG (pure Python, no external tools) | `--page N` |
| `info` | Show document summary (pages, shape/edge counts) | — |
| `xml` | Print raw .drawio XML | — |
| `export` | Export to PNG/PDF/SVG (requires Draw.io desktop) | `--format png\|svg\|pdf`, `-o PATH` |

### shape
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a shape | `--type TYPE`, `--label TEXT`, `--x X`, `--y Y`, `-w W`, `-H H` |
| `move` | Move shape to new position | `--id ID`, `--x X`, `--y Y` |
| `resize` | Resize a shape | `--id ID`, `-w W`, `-H H` |
| `label` | Update shape label | `--id ID`, `--text TEXT` |
| `style` | Set a single style property | `--id ID KEY VALUE` |
| `info` | Show shape details including parsed style | `--id ID` |
| `remove` | Remove a shape (and its connected edges) | `--id ID` |
| `list` | List all shapes with position | — |
| `types` | List all available shape type presets | — |

**Common shape types:**
```
rectangle       Standard box (default)
rounded         Box with rounded corners
rhombus         Diamond (for decisions)
ellipse         Oval/circle
hexagon         Hexagonal shape
cylinder        Database symbol
cloud           Cloud shape
callout         Speech-bubble callout
note            Folded note
actor           Stick-figure actor
parallelogram   Parallelogram (input/output)
triangle        Triangle
process         Process box
document        Curled document shape
text            Plain text (no border)
```

### connector
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a connector between shapes | `--from ID`, `--to ID`, `--label TEXT`, `--style PRESET` |
| `label` | Update connector label | `--id ID`, `--text TEXT` |
| `style` | Set a single style property | `--id ID KEY VALUE` |
| `styles` | List available edge style presets | — |
| `remove` | Remove a connector | `--id ID` |
| `list` | List all connectors | — |

**Edge style presets** (pass to `--style`):
```
orthogonal      Right-angle routing (default)
straight        Direct line
curved          Smooth curved line
entity-relation ER diagram style
```

### page
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List all pages | — |
| `add` | Add a page | `--name NAME` |
| `remove` | Remove a page | `--name PAGE_NAME` |

### session
| Command | Description |
|---------|-------------|
| `show` | Show current session info |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: architecture diagram

```bash
P=/tmp/arch.json

sven-integrations-drawio --json -p "$P" new --name "System Architecture"

sven-integrations-drawio --json -p "$P" shape add --type rounded    --label "Browser"      --x  50 --y  50
sven-integrations-drawio --json -p "$P" shape add --type rectangle  --label "API Gateway"  --x 250 --y  50
sven-integrations-drawio --json -p "$P" shape add --type rectangle  --label "Auth Service" --x 150 --y 200
sven-integrations-drawio --json -p "$P" shape add --type rectangle  --label "User Service" --x 350 --y 200
sven-integrations-drawio --json -p "$P" shape add --type cylinder   --label "PostgreSQL"   --x 250 --y 350

# Parse IDs from shape list, then connect
sven-integrations-drawio --json -p "$P" connector add --from <BROWSER_ID> --to <GATEWAY_ID>  --label "HTTPS"
sven-integrations-drawio --json -p "$P" connector add --from <GATEWAY_ID> --to <AUTH_ID>     --label "validate"
sven-integrations-drawio --json -p "$P" connector add --from <GATEWAY_ID> --to <USER_ID>     --label "route"
sven-integrations-drawio --json -p "$P" connector add --from <USER_ID>    --to <DB_ID>       --label "SQL"

sven-integrations-drawio --json -p "$P" save /tmp/architecture.drawio
sven-integrations-drawio --json -p "$P" svg  /tmp/architecture.svg
```

## Common pitfalls

- **`export` needs Draw.io desktop** — if not installed, use `save` for XML and `svg` for a viewable image.
- **Capture cell IDs from output** — `shape add` returns `{"cell_id": "..."}`. You need this for connector `--from` and `--to`.
- **`shape remove` cascades** — removing a shape also removes all connectors attached to it.
- **Use `--from` and `--to` for connectors** — not `--source`/`--target`.
- **Coordinates start at top-left** — increasing Y moves DOWN. Typical diagram area: 50–1000 × 50–800.
- **`new` always required first** — if the document is empty, `shape add` will fail.
- **Shell quoting** — run each shell invocation with one command per line. Avoid nested double quotes inside shell strings. Use single-quoted labels for text with special characters (e.g. `--label 'merge PR'`).

## Critical anti-patterns (do NOT do these)

1. **Stale cell IDs** — After `rm` on the project file or `new`, the document is fresh. Cell IDs from any previous run are invalid.
2. **Shapes + connectors in one script with unknown IDs** — Run shapes first, parse IDs, then run connectors in a separate shell.
3. **Nested quotes in shell_command** — Prefer `--label 'text'` over `--label "text"` when passing to a shell tool.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/drawio
