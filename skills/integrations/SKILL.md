---
name: integrations
description: |
  Use these skills when you need to control desktop applications — image editors,
  3D tools, audio editors, video editors, office suites, diagramming tools, or AI
  image generators. Trigger phrases: "edit image", "create 3D scene", "edit audio",
  "edit video", "create diagram", "generate image", "create presentation",
  "create spreadsheet", "control OBS", "start recording", "zoom meeting".
version: 2.0.0
---

# integrations

Structured CLI interfaces for controlling desktop applications. Each sub-skill
maps to an installed `sven-integrations-<tool>` binary that you invoke via the
`bash` tool with `--json` for reliable machine-readable output.

## Available tools

| Sub-skill | Binary | Domain |
|-----------|--------|--------|
| `integrations/gimp` | `sven-integrations-gimp` | Raster image editing |
| `integrations/blender` | `sven-integrations-blender` | 3D scenes and rendering |
| `integrations/inkscape` | `sven-integrations-inkscape` | Vector graphics (SVG) |
| `integrations/audacity` | `sven-integrations-audacity` | Audio editing and mixing |
| `integrations/libreoffice` | `sven-integrations-libreoffice` | Writer, Calc, Impress |
| `integrations/obs-studio` | `sven-integrations-obs-studio` | Streaming and recording |
| `integrations/kdenlive` | `sven-integrations-kdenlive` | Video editing (MLT/KDE) |
| `integrations/shotcut` | `sven-integrations-shotcut` | Video editing (MLT/cross-platform) |
| `integrations/zoom` | `sven-integrations-zoom` | Zoom meetings and recordings |
| `integrations/drawio` | `sven-integrations-drawio` | Draw.io diagrams |
| `integrations/mermaid` | `sven-integrations-mermaid` | Mermaid diagrams (code-first) |
| `integrations/anygen` | `sven-integrations-anygen` | AI content generation (PPTX, DOCX, PDF) |
| `integrations/comfyui` | `sven-integrations-comfyui` | ComfyUI AI image workflows |

## Choosing the right tool

| Task | Preferred tool |
|------|---------------|
| Edit a raster image (PNG, JPEG), draw shapes, apply filters | `gimp` |
| Create SVG vector graphics, icons, or scalable diagrams | `inkscape` |
| Create a 3D scene or render a 3D model | `blender` |
| Record/edit audio, apply audio effects | `audacity` |
| Create a technical flowchart, UML, or network diagram | `drawio` |
| Generate a diagram from text (flowchart, sequence, Gantt) | `mermaid` |
| Edit video with a full timeline on Linux/KDE | `kdenlive` |
| Edit video with a full timeline (cross-platform) | `shotcut` |
| Create a Word document, spreadsheet, or presentation | `libreoffice` |
| Generate presentations or documents with AI | `anygen` |
| Generate AI images using Stable Diffusion workflows | `comfyui` |
| Record screen/stream to Twitch/YouTube | `obs-studio` |
| Schedule or manage Zoom meetings | `zoom` |

## Usage pattern

**Load the relevant sub-skill first**, then use the binary. Always use `-p`
to specify an explicit project file — this keeps state in a known location and
makes every command idempotent and resumable:

```bash
# Always use --json for parseable output
# Always use -p /absolute/path/to/project.json (persists state across calls)

sven-integrations-gimp --json project new --width 1920 --height 1080 -o /tmp/proj.json
sven-integrations-gimp --json -p /tmp/proj.json draw rect --x 0 --y 0 --w 1920 --h 1080 --fill "#336699"
sven-integrations-gimp --json -p /tmp/proj.json export render /tmp/output.png --overwrite
```

For tools driven by live applications (OBS, Audacity, Zoom, ComfyUI), connect
first, then use commands:

```bash
sven-integrations-obs-studio --json connect --host localhost --port 4455
sven-integrations-obs-studio --json -p /tmp/obs.json scene list
```

## Key principles

1. **Always use `--json`** — machine-readable output on stdout, errors on stderr
2. **Always use `-p /absolute/path/to/file.json`** — explicit state file, idempotent across calls, no hidden directories
3. **Check return code** — 0 = success, non-zero = error; check `{"ok": false}` in JSON
4. **Use absolute paths** for all file arguments (`/tmp/output.png` not `output.png`)
5. **`--help` is always safe** — shows all subcommands and flags for any tool
6. **For tools needing a live app** (OBS, Audacity, ComfyUI, Zoom), run the connection/auth step first

## Error handling pattern

```bash
result=$(sven-integrations-gimp --json -p /tmp/proj.json export render /tmp/out.png --overwrite)
if [ $? -ne 0 ]; then
  echo "Error: $result" >&2
  exit 1
fi
```

In JSON mode, errors include a message in the JSON payload:
```json
{"ok": false, "error": "Layer index 2 out of range"}
```
