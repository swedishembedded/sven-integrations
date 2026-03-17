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

# 3. Add connectors (source/target are cell IDs from the add output)
sven-integrations-drawio --json -p "$P" connector add --source <START_ID> --target <DECISION_ID> --label "→"
sven-integrations-drawio --json -p "$P" connector add --source <DECISION_ID> --target <ACTIONA_ID> --label "Yes"
sven-integrations-drawio --json -p "$P" connector add --source <DECISION_ID> --target <ACTIONB_ID> --label "No"

# 4. Export to PNG (requires Draw.io desktop app)
sven-integrations-drawio --json -p "$P" export --format png --output /tmp/diagram.png

# 5. Verify
ls -lh /tmp/diagram.png
```

## Key rules for agents

1. **Always run `new` first** to create a fresh document with at least one page.
2. **Always pass `-p /absolute/path/to/project.json`** to persist state.
3. **Shape `add` returns a `cell_id`** — capture it for connector `--source` and `--target`.
4. **`export` requires Draw.io desktop installed** — for just the `.drawio` XML, use `save` instead.
5. **Coordinates are in diagram units (pixels at 100% zoom)** — typical values: x/y 50–800, width/height 120–200 for labels.
6. **Page management** — multi-page diagrams use `page add/rename/switch`; shapes go on the active page.
7. **Use `shape list` and `connector list`** to inspect what's already on the diagram.

## Command groups

### document
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create new document | `--name NAME` |
| `open PATH` | Load existing .drawio file | — |
| `save PATH` | Save diagram to .drawio XML | — |
| `info` | Show document info | — |

### page
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List all pages | — |
| `add` | Add a page | `--name NAME` |
| `rename` | Rename a page | `--index N`, `--name NEW_NAME` |
| `switch` | Set active page | `--index N` |
| `remove` | Remove a page | `--index N` |

### shape
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a shape | `--type TYPE`, `--label TEXT`, `--x X`, `--y Y`, `--width W`, `--height H`, `--style STYLE` |
| `edit` | Edit a shape | `--id ID`, `--label TEXT`, `--style STYLE` |
| `move` | Move a shape | `--id ID`, `--x X`, `--y Y` |
| `resize` | Resize a shape | `--id ID`, `--width W`, `--height H` |
| `remove` | Remove a shape | `--id ID` |
| `list` | List all shapes | — |
| `style` | Apply style to a shape | `--id ID`, `--style STYLE_STRING` |

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

**Style string examples:**
```
"fillColor=#dae8fc;strokeColor=#6c8ebf;"          (light blue box)
"fillColor=#d5e8d4;strokeColor=#82b366;"          (light green box)
"fillColor=#fff2cc;strokeColor=#d6b656;"          (yellow box)
"fillColor=#f8cecc;strokeColor=#b85450;"          (red/error box)
"shape=hexagon;fillColor=#e1d5e7;strokeColor=#9673a6;"  (purple hexagon)
```

### connector
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a connector between shapes | `--source ID`, `--target ID`, `--label TEXT`, `--style STYLE` |
| `edit` | Edit a connector | `--id ID`, `--label TEXT` |
| `remove` | Remove a connector | `--id ID` |
| `list` | List all connectors | — |

**Connector style examples:**
```
"edgeStyle=orthogonalEdgeStyle;"     (right-angle routing, default)
"edgeStyle=elbowEdgeStyle;"          (elbow routing)
"edgeStyle=entityRelationEdgeStyle;" (ER diagram lines)
"dashed=1;"                          (dashed line)
"endArrow=ERzeroToMany;"            (ER zero-to-many)
```

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `export` | Export to image/PDF (requires Draw.io desktop) | `--format png\|svg\|pdf`, `--output PATH` (required), `--page N` |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: architecture diagram

```bash
P=/tmp/arch.json

# Create document
sven-integrations-drawio --json -p "$P" new --name "System Architecture"

# Add nodes with blue styling for services
sven-integrations-drawio --json -p "$P" shape add --type rounded --label "Browser" --x 50 --y 50 --style "fillColor=#dae8fc;strokeColor=#6c8ebf;"
sven-integrations-drawio --json -p "$P" shape add --type rectangle --label "API Gateway" --x 250 --y 50 --style "fillColor=#d5e8d4;strokeColor=#82b366;"
sven-integrations-drawio --json -p "$P" shape add --type rectangle --label "Auth Service" --x 150 --y 200 --style "fillColor=#d5e8d4;strokeColor=#82b366;"
sven-integrations-drawio --json -p "$P" shape add --type rectangle --label "User Service" --x 350 --y 200 --style "fillColor=#d5e8d4;strokeColor=#82b366;"
sven-integrations-drawio --json -p "$P" shape add --type cylinder --label "PostgreSQL" --x 250 --y 350 --style "fillColor=#fff2cc;strokeColor=#d6b656;"

# Connect them (using cell IDs from output)
sven-integrations-drawio --json -p "$P" connector add --source <BROWSER_ID> --target <GATEWAY_ID> --label "HTTPS"
sven-integrations-drawio --json -p "$P" connector add --source <GATEWAY_ID> --target <AUTH_ID> --label "validate"
sven-integrations-drawio --json -p "$P" connector add --source <GATEWAY_ID> --target <USER_ID> --label "route"
sven-integrations-drawio --json -p "$P" connector add --source <USER_ID> --target <DB_ID> --label "SQL"

# Verify
sven-integrations-drawio --json -p "$P" shape list
sven-integrations-drawio --json -p "$P" connector list

# Export (requires Draw.io desktop installed)
sven-integrations-drawio --json -p "$P" export --format png --output /tmp/architecture.png
```

## Common pitfalls

- **`export` needs Draw.io desktop** — if not installed, use `save /tmp/diagram.drawio` to get the XML file and open it manually in Draw.io.
- **Capture cell IDs from output** — `shape add` returns `{"cell_id": "..."}`. You need this for connectors and edits.
- **Style strings are semicolon-separated** — copy from Draw.io's style editor. Example: `"fillColor=#dae8fc;strokeColor=#6c8ebf;rounded=1;"`.
- **Default page index is 0** — to add shapes to a specific page, use `page switch --index N` first.
- **Coordinates start at top-left** — increasing Y moves DOWN. Typical diagram area: 50–1000 × 50–800.
- **`new` always required first** — if the document is empty, `shape add` will fail with "No document in session".

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/drawio
