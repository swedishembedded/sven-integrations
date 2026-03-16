---
name: integrations/inkscape
description: |
  Use when asked to create vector graphics, SVG files, logos, icons, diagrams with
  shapes, or export SVG to PNG/PDF. Trigger phrases: "create vector graphic", "create SVG",
  "add shape", "create logo", "create icon", "draw rectangle", "draw circle",
  "apply gradient", "export SVG", "boolean path operation".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-inkscape]
---

# sven-integrations-inkscape

Stateful CLI for SVG vector graphics editing. Manages Inkscape documents as
SVG XML with Pillow-based PNG rendering.

## Quick start

```bash
sven-integrations-inkscape --json document new -o /tmp/doc.svg --width 800 --height 600
sven-integrations-inkscape --json shape add rect --x 50 --y 50 --width 200 --height 100 -p /tmp/doc.svg
sven-integrations-inkscape --json style set fill --element <id> --value "#ff0000" -p /tmp/doc.svg
sven-integrations-inkscape --json export png output.png -p /tmp/doc.svg
```

## Command groups

### document
`new`, `open`, `save`, `info`, `profiles`, `canvas-resize`

### shape
`add` (rect/circle/ellipse/line/polygon/path/star),
`remove`, `duplicate`, `list`

### text
`add`, `set-property`, `list`

### style
`set`, `get`, `copy`

### transform
`translate`, `rotate`, `scale`, `skewx`, `skewy`

### layer
`add`, `remove`, `move`, `set-property`, `list`

### path
`union`, `intersection`, `difference`, `exclusion`, `to-path`

### gradient
`create` (linear/radial), `apply`

### export
`png`, `svg`, `pdf`

### session
`undo`, `redo`, `history`

## Document profiles
`a4` (794×1123), `letter` (816×1056), `hd` (1920×1080), `icons` (512×512),
`instagram_square` (1080×1080), `twitter_header` (1500×500)

## For agents
- `-p` / `--project` specifies the SVG file to work on
- All coordinates are in SVG user units (px by default)
- IDs are auto-generated; use `shape list` to discover them
