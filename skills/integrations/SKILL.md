---
name: integrations
description: |
  Use these skills when you need to control desktop applications — image editors,
  3D tools, audio editors, video editors, office suites, diagramming tools, or AI
  image generators. Trigger phrases: "edit image", "create 3D scene", "edit audio",
  "edit video", "create diagram", "generate image", "create presentation",
  "create spreadsheet", "control OBS", "start recording", "zoom meeting".
version: 1.0.0
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
| `integrations/inkscape` | `sven-integrations-inkscape` | Vector graphics |
| `integrations/audacity` | `sven-integrations-audacity` | Audio editing and mixing |
| `integrations/libreoffice` | `sven-integrations-libreoffice` | Writer, Calc, Impress |
| `integrations/obs-studio` | `sven-integrations-obs-studio` | Streaming and recording |
| `integrations/kdenlive` | `sven-integrations-kdenlive` | Video editing (MLT) |
| `integrations/shotcut` | `sven-integrations-shotcut` | Video editing (MLT) |
| `integrations/zoom` | `sven-integrations-zoom` | Zoom meetings and recordings |
| `integrations/drawio` | `sven-integrations-drawio` | Draw.io diagrams |
| `integrations/mermaid` | `sven-integrations-mermaid` | Mermaid diagrams |
| `integrations/anygen` | `sven-integrations-anygen` | AI content generation |
| `integrations/comfyui` | `sven-integrations-comfyui` | ComfyUI AI image workflows |

## Usage pattern

Load the relevant sub-skill first, then use the binary:

```bash
# Always use --json for parseable output
sven-integrations-gimp --session my-project new --width 1920 --height 1080
sven-integrations-gimp --session my-project --json layer add Background
sven-integrations-gimp --session my-project --json export /tmp/output.png
```

## Key principles

1. Always use `--json` flag for machine-readable output
2. Check return code — 0 means success, non-zero means error
3. Use absolute paths for all file arguments
4. Use `--session` / `-s` to name your workspace (persists across calls)
5. The `--help` flag shows all available subcommands for any tool
