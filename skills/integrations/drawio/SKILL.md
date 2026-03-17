---
name: integrations/drawio
description: |
  Use when asked to create or edit Draw.io diagrams, flowcharts, architecture
  diagrams, network diagrams, UML diagrams, entity-relationship diagrams, or any
  other structured diagram format. Trigger phrases: "create diagram", "flowchart",
  "architecture diagram", "network topology", "draw.io", "UML diagram", "ERD".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-drawio]
---

# sven-integrations-drawio

Stateful CLI for creating and editing Draw.io `.drawio` / `.xml` diagrams. Stores
a diagram model in a JSON project file and can optionally call the Draw.io desktop
application to export to PNG/PDF/SVG.

## Minimal working example — simple flowchart

```bash
P=/tmp/drawio_project.json

# 1. Create a new document
sven-integrations-drawio --json -p "$P" new --name "My Flowchart"

# 2. Add shapes
sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Start" --x 200 --y 50

sven-integrations-drawio --json -p "$P" shape add --type rhombus --label "Decision?" --x 175 --y 170 --width 250 --height 80

sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Action A" --x 100 --y 330

sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Action B" --x 340 --y 330

# 3. Add connectors (--from and --to are cell IDs from the add output)
sven-integrations-drawio --json -p "$P" connector add --from <START_ID> --to <DECISION_ID> --label "→"
sven-integrations-drawio --json -p "$P" connector add --from <DECISION_ID> --to <ACTIONA_ID> --label "Yes"
sven-integrations-drawio --json -p "$P" connector add --from <DECISION_ID> --to <ACTIONB_ID> --label "No"

# 4. Save to .drawio XML (always works) or export to PNG (requires Draw.io desktop)
sven-integrations-drawio --json -p "$P" save /tmp/diagram.drawio

# 5. Verify
ls -lh /tmp/diagram.drawio
```

## Key rules for agents

1. **Always run `new` first** to create a fresh document with at least one page.
2. **Always pass `-p /absolute/path/to/project.json`** to persist state.
3. **Shape `add` returns a `cell_id`** — capture it for connector `--from` and `--to`.
4. **`export` requires Draw.io desktop installed** — use `save /path/to/diagram.drawio` to write XML (no desktop needed).
5. **Coordinates are in diagram units (pixels at 100% zoom)** — typical values: x/y 50–800, width/height 120–200 for labels.
6. **Page management** — multi-page diagrams use `page add` and `page remove`; shapes go on the first page.
7. **Use `shape list`** to inspect shapes and capture cell IDs for connectors.

## Command groups

### document
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create new document | `--name NAME` |
| `open PATH` | Load existing .drawio file | — |
| `save PATH` | Save diagram to .drawio XML (no Draw.io desktop required) | — |
| `export` | Export to PNG/PDF/SVG (requires Draw.io desktop) | `--format png\|svg\|pdf`, `-o PATH` |

### page
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List all pages | — |
| `add` | Add a page | `--name NAME` |
| `remove` | Remove a page | `--name PAGE_NAME` |

### shape
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a shape | `--type TYPE`, `--label TEXT`, `--x X`, `--y Y`, `-w W`, `-H H` |
| `label` | Update shape label | `--id ID`, `--text TEXT` |
| `remove` | Remove a shape | `--id ID` |
| `list` | List all shapes | — |

**Note:** `shape add` does NOT support `--style`. Use `shape label` to change text after creation.

**Common shape types:**
```
rectangle       Standard box (default)
rounded         Box with rounded corners
rhombus         Diamond (for decisions)
ellipse         Oval/circle
hexagon         Hexagonal shape
cylinder        Database symbol
cloud           Cloud shape
parallelogram   Parallelogram (input/output)
triangle        Triangle
process         Thick-bordered process box
document        Curled document shape
```

### connector
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a connector between shapes | `--from ID`, `--to ID`, `--label TEXT` |
| `remove` | Remove a connector | `--id ID` |

**Important:** Use `--from` and `--to` (not `--source`/`--target`). Both accept cell IDs from `shape add` output.

### session
| Command | Description |
|---------|-------------|
| `show` | Show current session info |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: architecture diagram

```bash
P=/tmp/arch.json

# Create document
sven-integrations-drawio --json -p "$P" new --name "System Architecture"

# Add nodes (no --style; use shape types for visual variety)
sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Browser" --x 50 --y 50
sven-integrations-drawio --json -p "$P" shape add --type rectangle --label "API Gateway" --x 250 --y 50
sven-integrations-drawio --json -p "$P" shape add --type rectangle --label "Auth Service" --x 150 --y 200
sven-integrations-drawio --json -p "$P" shape add --type rectangle --label "User Service" --x 350 --y 200
sven-integrations-drawio --json -p "$P" shape add --type cylinder --label "PostgreSQL" --x 250 --y 350

# Connect them (--from and --to use cell IDs from shape add output)
sven-integrations-drawio --json -p "$P" connector add --from <BROWSER_ID> --to <GATEWAY_ID> --label "HTTPS"
sven-integrations-drawio --json -p "$P" connector add --from <GATEWAY_ID> --to <AUTH_ID> --label "validate"
sven-integrations-drawio --json -p "$P" connector add --from <GATEWAY_ID> --to <USER_ID> --label "route"
sven-integrations-drawio --json -p "$P" connector add --from <USER_ID> --to <DB_ID> --label "SQL"

# Save to .drawio (always works) or export PNG (requires Draw.io desktop)
sven-integrations-drawio --json -p "$P" save /tmp/architecture.drawio
```

## Common pitfalls

- **`export` needs Draw.io desktop** — if not installed, use `save /path/to/diagram.drawio` to write XML (no desktop needed).
- **Capture cell IDs from output** — `shape add` returns `{"cell_id": "..."}`. You need this for connector `--from` and `--to`.
- **Do NOT use `--style` on shape add** — the CLI does not support it. Use shape types (rounded, rhombus, cylinder, etc.) for visual variety.
- **Use `--from` and `--to` for connectors** — not `--source`/`--target`.
- **Coordinates start at top-left** — increasing Y moves DOWN. Typical diagram area: 50–1000 × 50–800.
- **`new` always required first** — if the document is empty, `shape add` will fail with "No document in session".
- **Shell quoting** — when chaining multiple commands, prefer one command per line or use single-quoted labels to avoid quote-escaping issues.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/drawio
