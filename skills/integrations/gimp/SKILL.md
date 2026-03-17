---
name: integrations/gimp
description: |
  Use when asked to edit images, create image compositions, apply filters, add layers,
  resize or crop images, export to PNG/JPEG/WebP/TIFF, or draw shapes, text, and graphics.
  Trigger phrases: "edit image", "add layer", "apply filter", "resize image", "crop image",
  "convert image format", "create image", "draw text on image", "draw a cat", "generate image".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-gimp]
---

# sven-integrations-gimp

Stateful CLI for raster image editing. Stores all drawing operations in a JSON project file
and renders them to a real image file using Pillow. No GIMP installation required for basic
operations.

## Minimal working example — draw something and get a PNG

```bash
# 1. Create project (auto-creates Background layer at index 0 with white fill)
sven-integrations-gimp --json project new --width 800 --height 600 --name "My Image" -o /tmp/proj.json

# 2. Draw on layer 0 (always exists after project new)
sven-integrations-gimp --json -p /tmp/proj.json draw rect --x 50 --y 50 --w 700 --h 500 --fill "#4488ff" --layer 0
sven-integrations-gimp --json -p /tmp/proj.json draw ellipse --cx 400 --cy 300 --rx 150 --ry 100 --fill "#ff8800" --layer 0
sven-integrations-gimp --json -p /tmp/proj.json draw text --text "Hello World" --x 280 --y 270 --size 36 --color "#ffffff" --layer 0

# 3. Render to PNG (creates the actual file)
sven-integrations-gimp --json -p /tmp/proj.json export render /tmp/output.png --overwrite

# 4. Verify the file was created
ls -lh /tmp/output.png
```

## Key rules for agents

1. **Always use `project new` first** — it creates the project JSON and a "Background" layer at index 0.
2. **Use `--layer 0` for the default layer** — immediately after `project new`, layer 0 is the white Background.
3. **Always pass `-p /path/to/project.json`** on every command to load/save state.
4. **`export render` writes an actual file** — verify with `ls -la` after rendering.
5. **Colors** accept `#RRGGBB` hex (`#FF8800`), named colors (`red`, `blue`, `white`, `black`, `orange`), or `transparent`.
6. **All draw commands queue operations** — nothing is rasterized until `export render`.

## Command groups

### project
| Command | Description |
|---------|-------------|
| `new` | Create a new project (auto-creates Background layer 0) |
| `open` | Open an existing project JSON |
| `save` | Save the current project to a JSON file |
| `info` | Show project information |
| `profiles` | List available canvas profiles |
| `json` | Print raw project JSON |

**project new options:**
- `--width` / `-w` — canvas width in pixels (default: 1920)
- `--height` / `-h` — canvas height in pixels (default: 1080)
- `--name` / `-n` — project name
- `--output` / `-o` — save project JSON to this path (required for `-p` to work)
- `--bg` — background fill color (default: `white`; use `transparent`, `black`, or `#hex`)

### layer
| Command | Description |
|---------|-------------|
| `new` | Create a new blank layer |
| `add-from-file` | Add a layer from an image file |
| `list` | List all layers with indices |
| `remove` | Remove a layer by index |
| `duplicate` | Duplicate a layer |
| `move` | Move a layer to a new stack position |
| `set` | Set a layer property (name, opacity, visible, fill_color, offset_x, offset_y) |
| `flatten` | Flatten all visible layers into one |
| `merge-down` | Merge a layer with the one below |

**layer new options:**
- `--name` — layer name
- `--fill` — fill color (default: `transparent`)
- `--position` — stack index (0 = top)

### draw
| Command | Description |
|---------|-------------|
| `rect` | Draw a filled rectangle |
| `ellipse` | Draw an ellipse |
| `circle` | Draw a circle |
| `line` | Draw a line |
| `text` | Draw text |
| `shape` | Generic dispatcher (--type ellipse\|circle\|rect\|line) |

**Common draw options (on all commands):**
- `--layer` / `-l` — layer index (default: 0)
- `--fill` — fill color for shapes (default: `#000000`)
- `--outline` — outline/border color
- `--stroke-width` — outline or line width in pixels

**draw rect:** `--x1 --y1 --x2 --y2` OR `--x --y --w --h`
**draw ellipse:** `--cx --cy --rx --ry`
**draw circle:** `--cx --cy --r`
**draw line:** `--x1 --y1 --x2 --y2 --stroke <color> --width <px>`
**draw text:** `--text "..." --x --y --font --size --color`

### filter
| Command | Description |
|---------|-------------|
| `add` | Add a filter to a layer (applied on export) |
| `remove` | Remove a filter by index |
| `set` | Update a filter parameter |
| `list` | List filters on a layer |
| `list-available` | Show all available filter names |

**filter add syntax:**
```bash
sven-integrations-gimp --json -p /tmp/proj.json filter add brightness --layer 0 --param factor=1.3
sven-integrations-gimp --json -p /tmp/proj.json filter add gaussian_blur --layer 0 --param radius=3
sven-integrations-gimp --json -p /tmp/proj.json filter add grayscale --layer 0
sven-integrations-gimp --json -p /tmp/proj.json filter add sepia --layer 0 --param strength=0.8
```

**Available filters:** `brightness`, `contrast`, `saturation`, `sharpness`, `blur`, `gaussian_blur`,
`box_blur`, `edge_enhance`, `grayscale`, `sepia`, `invert`, `flip_h`, `flip_v`, `rotate`

### export
| Command | Description |
|---------|-------------|
| `render` | Render project to image file (PNG/JPEG/WebP/TIFF) |
| `presets` | List export presets |

**export render options:**
- `OUTPUT_PATH` — absolute path for the output file (e.g. `/tmp/result.png`)
- `--overwrite` — overwrite existing file
- `--format` — format override (png, jpeg, webp, tiff)
- `--quality` — quality for JPEG/WebP (default: 90)

## Canvas profiles

`hd` (1920×1080), `4k` (3840×2160), `square_1080` (1080×1080),
`portrait_1080` (1080×1920), `a4_300dpi` (2480×3508), `twitter_header`,
`youtube_thumbnail`, `facebook_cover`, `instagram_post`

## Complete recipe: multi-layer image

```bash
P=/tmp/myimage.json

# Create project
sven-integrations-gimp --json project new --width 1080 --height 1080 --name "Poster" --bg white -o "$P"

# Add a second layer on top
sven-integrations-gimp --json -p "$P" layer new --name Overlay --fill transparent

# Draw background gradient simulation (blue rect on layer 0)
sven-integrations-gimp --json -p "$P" draw rect --x 0 --y 0 --w 1080 --h 1080 --fill "#1a237e" --layer 0

# Draw title text on the overlay (layer 0 is bottom, new layers insert at top = index 0)
# After layer new, check layer list to get correct indices:
sven-integrations-gimp --json -p "$P" layer list

# Draw on whichever index the Overlay layer is at
sven-integrations-gimp --json -p "$P" draw text --text "My Poster" --x 200 --y 480 --size 80 --color "#ffffff" --layer 0

# Apply a brightness filter
sven-integrations-gimp --json -p "$P" filter add brightness --layer 0 --param factor=1.1

# Render to PNG
sven-integrations-gimp --json -p "$P" export render /tmp/poster.png --overwrite

# Confirm file exists
ls -lh /tmp/poster.png
```

## Common pitfalls

- **"Layer index 0 out of range"** — this only happens if you forget to use `project new`. After `project new`, layer 0 always exists.
- **Relative paths in `export render`** — always use absolute paths like `/tmp/output.png`, not `output.png`, to ensure the file ends up where expected.
- **Drawing on the wrong layer** — after `layer new`, layers are inserted at the top. Use `layer list` to check current indices before drawing.
- **Forgetting `-p`** — every command after `project new` needs `-p /path/to/project.json` to load the saved state.
- **Colors** — use `#RRGGBB` format or named colors. Do NOT use CSS `rgb()` notation.
- **`export render` without `--overwrite`** — if the output file exists, the command will fail unless `--overwrite` is passed.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project JSON (pass before or after subcommand)
- `--overwrite` — on `export render`, allows replacing an existing file

Base directory: /usr/share/sven/skills/integrations/gimp
