---
name: integrations/gimp
description: |
  Use when asked to edit images, create image compositions, apply filters, add layers,
  resize or crop images, or export to PNG/JPEG/WebP/TIFF/PDF. Trigger phrases:
  "edit image", "add layer", "apply filter", "resize image", "crop image",
  "convert image format", "create image", "draw text on image".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-gimp]
---

# sven-integrations-gimp

Stateful CLI for raster image editing. Manages layered image projects as JSON
with Pillow-based rendering and optional GIMP backend for advanced operations.

## Quick start

```bash
# Create a new 1920×1080 project
sven-integrations-gimp --json project new -o /tmp/project.json --width 1920 --height 1080

# Add a background layer from file
sven-integrations-gimp --json layer add-from-file photo.jpg --name Background -p /tmp/project.json

# Add a text layer
sven-integrations-gimp --json draw text "Hello World" --layer 0 --x 100 --y 100 -p /tmp/project.json

# Apply brightness filter
sven-integrations-gimp --json filter add brightness --layer 0 --param factor=1.2 -p /tmp/project.json

# Render to PNG
sven-integrations-gimp --json export render output.png -p /tmp/project.json
```

## Command groups

### project
| Command | Description |
|---------|-------------|
| `new` | Create a new project |
| `open` | Open an existing project |
| `save` | Save the current project |
| `info` | Show project information |
| `profiles` | List available canvas profiles |
| `json` | Print raw project JSON |

### layer
| Command | Description |
|---------|-------------|
| `new` | Create a new blank layer |
| `add-from-file` | Add a layer from an image file |
| `list` | List all layers |
| `remove` | Remove a layer by index |
| `duplicate` | Duplicate a layer |
| `move` | Move a layer to a new position |
| `set` | Set a layer property |
| `flatten` | Flatten all visible layers |
| `merge-down` | Merge a layer with the one below |

### canvas
| Command | Description |
|---------|-------------|
| `info` | Show canvas information |
| `resize` | Resize the canvas |
| `scale` | Scale the canvas and content |
| `crop` | Crop the canvas |
| `mode` | Set the canvas color mode |
| `dpi` | Set the canvas DPI |

### filter
| Command | Description |
|---------|-------------|
| `list-available` | List all available filters |
| `add` | Add a filter to a layer |
| `remove` | Remove a filter by index |
| `set` | Set a filter parameter |
| `list` | List filters on a layer |

### export
| Command | Description |
|---------|-------------|
| `presets` | List export presets |
| `render` | Render the project to an image file |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo the last operation |
| `redo` | Redo the last undone operation |
| `history` | Show undo history |

## Canvas profiles

`hd` (1920×1080), `4k` (3840×2160), `square_1080` (1080×1080),
`portrait_1080` (1080×1920), `a4_300dpi` (2480×3508), `twitter_header`,
`youtube_thumbnail`, `facebook_cover`, `instagram_post`

## For agents

- `--json` flag on every command for structured output
- `--project` / `-p` flag to specify project file path
- `--overwrite` flag on render to replace existing output file
- Filter names: `brightness`, `contrast`, `saturation`, `sharpness`,
  `blur`, `gaussian_blur`, `edge_enhance`, `grayscale`, `sepia`,
  `invert`, `flip_h`, `flip_v`, `rotate`, `crop_filter`, `resize_filter`
