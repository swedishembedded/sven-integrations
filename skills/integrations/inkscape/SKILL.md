---
name: integrations/inkscape
description: |
  Use when asked to create or edit SVG vector graphics, draw shapes, add text,
  apply styles, create gradients, work with layers, or export to PNG/PDF/SVG.
  Trigger phrases: "create SVG", "vector graphic", "draw shapes in Inkscape",
  "create icon", "SVG export", "scalable graphic", "add path", "SVG layers".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-inkscape]
---

# sven-integrations-inkscape

Stateful CLI for Inkscape SVG vector graphics. Stores an SVG document model in a
JSON project file and optionally calls the `inkscape` binary for advanced operations
(export, path operations). Basic shape/text/style operations work without Inkscape.

## Minimal working example — create an SVG with shapes

```bash
P=/tmp/inkscape_project.json

# 1. Create a new A4 document
sven-integrations-inkscape --json document new --width 210 --height 297 -p "$P"

# 2. Add shapes
sven-integrations-inkscape --json -p "$P" shape rect --x 20 --y 20 --width 80 --height 40 --fill "#4488ff" --id "rect1"
sven-integrations-inkscape --json -p "$P" shape circle --cx 150 --cy 80 --r 30 --fill "#ff4422" --id "circle1"

# 3. Add text
sven-integrations-inkscape --json -p "$P" text add --x 20 --y 150 --text "Hello SVG" --size 24 --fill "#000000"

# 4. Export to PNG
sven-integrations-inkscape --json -p "$P" export png --output /tmp/output.png --dpi 96

# 5. Verify
ls -lh /tmp/output.png
```

## Key rules for agents

1. **Always use `document new` first** — this creates the project with a blank SVG canvas.
2. **Always pass `-p /path/to/project.json`** to load/save state across commands.
3. **Coordinates are in mm by default** — `document new --width 210 --height 297` is A4 in mm. For pixels, use `--units px`.
4. **`export png` requires Inkscape to be installed** for rendering; `export svg` works without it.
5. **Element IDs are important** — use `--id myid` when creating elements to reference them later for style changes.
6. **Colors accept hex (`#RRGGBB`), named colors (`red`, `blue`), and CSS values**.
7. **`style set --id ELEMENT_ID`** changes attributes on an existing element.

## Command groups

### document
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create a new SVG document | `--width W`, `--height H`, `--units mm\|px\|pt` |
| `open PATH` | Record an SVG file path in session | `--width W`, `--height H` |
| `info` | Show document dimensions | — |
| `save PATH` | Save SVG to file | — |

### shape
| Command | Description | Key flags |
|---------|-------------|-----------|
| `rect` | Add a rectangle | `--x X`, `--y Y`, `--width W`, `--height H`, `--fill COLOR`, `--stroke COLOR`, `--stroke-width N`, `--id ID` |
| `circle` | Add a circle | `--cx X`, `--cy Y`, `--r R`, `--fill COLOR`, `--stroke COLOR`, `--id ID` |
| `ellipse` | Add an ellipse | `--cx X`, `--cy Y`, `--rx RX`, `--ry RY`, `--fill COLOR`, `--id ID` |
| `line` | Add a line | `--x1 X1`, `--y1 Y1`, `--x2 X2`, `--y2 Y2`, `--stroke COLOR`, `--stroke-width N` |
| `polygon` | Add a polygon | `--points "x1,y1 x2,y2 ..."`, `--fill COLOR`, `--id ID` |

### text
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a text element | `--x X`, `--y Y`, `--text "..."`, `--size POINTS`, `--fill COLOR`, `--font FAMILY`, `--id ID` |
| `edit` | Update text content | `--id ID`, `--text "new text"` |

### style
| Command | Description | Key flags |
|---------|-------------|-----------|
| `set` | Set style attribute on element | `--id ELEMENT_ID`, `--fill COLOR`, `--stroke COLOR`, `--opacity 0.0–1.0`, `--stroke-width N` |
| `get` | Get style of element | `--id ELEMENT_ID` |

### layer
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a new layer | `--name NAME` |
| `list` | List all layers | — |
| `set-active` | Switch active layer | `--name NAME` |
| `hide` | Hide a layer | `--name NAME` |
| `show` | Show a layer | `--name NAME` |

### transform
| Command | Description | Key flags |
|---------|-------------|-----------|
| `translate` | Move an element | `--id ID`, `--dx DX`, `--dy DY` |
| `rotate` | Rotate an element | `--id ID`, `--angle DEGREES`, `--cx CX`, `--cy CY` |
| `scale` | Scale an element | `--id ID`, `--sx SX`, `--sy SY` |

### gradient
| Command | Description | Key flags |
|---------|-------------|-----------|
| `linear` | Create a linear gradient | `--id ID`, `--x1 X1`, `--y1 Y1`, `--x2 X2`, `--y2 Y2` |
| `stop` | Add a color stop to gradient | `--gradient-id ID`, `--offset 0.0–1.0`, `--color COLOR` |

### path
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add an SVG path | `--d "M 0 0 L 100 100 Z"`, `--fill COLOR`, `--id ID` |

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `png` | Export document to PNG (requires Inkscape binary) | `--output PATH`, `--dpi 96\|150\|300` |
| `svg` | Save the SVG to a file | `--output PATH` |
| `pdf` | Export to PDF (requires Inkscape binary) | `--output PATH` |

### elements
| Command | Description |
|---------|-------------|
| `list` | List all elements with IDs |
| `remove --id ID` | Remove an element |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: logo with gradient and text

```bash
P=/tmp/logo.json

# A4 landscape
sven-integrations-inkscape --json document new --width 297 --height 210 --units mm -p "$P"

# Background rectangle
sven-integrations-inkscape --json -p "$P" shape rect --x 0 --y 0 --width 297 --height 210 --fill "#1a1a2e" --id bg

# Create a linear gradient
sven-integrations-inkscape --json -p "$P" gradient linear --id "blueGrad" --x1 0 --y1 0 --x2 1 --y2 0
sven-integrations-inkscape --json -p "$P" gradient stop --gradient-id blueGrad --offset 0.0 --color "#4488ff"
sven-integrations-inkscape --json -p "$P" gradient stop --gradient-id blueGrad --offset 1.0 --color "#22ffdd"

# Accent rectangle using the gradient
sven-integrations-inkscape --json -p "$P" shape rect --x 20 --y 80 --width 257 --height 5 --fill "url(#blueGrad)" --id accent

# Title text
sven-integrations-inkscape --json -p "$P" text add --x 20 --y 60 --text "My Company" --size 36 --fill "#ffffff" --font "DejaVu Sans" --id title

# Subtitle
sven-integrations-inkscape --json -p "$P" text add --x 20 --y 120 --text "Innovation at scale" --size 18 --fill "#aaaaaa" --id subtitle

# Check elements
sven-integrations-inkscape --json -p "$P" elements list

# Export to PNG at 150 DPI
sven-integrations-inkscape --json -p "$P" export png --output /tmp/logo.png --dpi 150
ls -lh /tmp/logo.png
```

## Common pitfalls

- **"No project in session"** — always run `document new` (or `open`) before any shape/text commands.
- **Coordinates are in document units** — if you created the doc with `--units mm`, then `--x 20` means 20mm. If `--units px`, it means 20px.
- **`export png` fails without Inkscape installed** — `inkscape` binary must be on PATH. For basic export, save as SVG first (`export svg --output /tmp/out.svg`) and use another tool.
- **Gradient fill syntax** — to fill a shape with a gradient, use `--fill "url(#gradientId)"`. The gradient must be created first.
- **`style set` needs the element ID** — always create elements with `--id myid` if you plan to restyle them later.
- **Path data format** — SVG path `d` attribute: `M x,y` (move), `L x,y` (line), `C ...` (curve), `Z` (close). Example: `--d "M 10,10 L 90,10 L 90,90 Z"`.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)
- `--id ID` — element identifier for later reference

Base directory: /usr/share/sven/skills/integrations/inkscape
