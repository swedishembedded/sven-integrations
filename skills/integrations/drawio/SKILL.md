---
name: integrations/drawio
description: |
  Use when asked to create flowcharts, architecture diagrams, network diagrams,
  entity-relationship diagrams, or any visual diagram using Draw.io. Trigger phrases:
  "create flowchart", "create architecture diagram", "draw ER diagram",
  "create network diagram", "add shapes and connectors", "create diagram".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-drawio]
---

# sven-integrations-drawio

Stateful CLI for Draw.io (mxGraph) diagram creation. Manages `.drawio` XML files
and exports to PNG/PDF/SVG via the Draw.io desktop app.

## Quick start

```bash
sven-integrations-drawio --json project new --preset letter -o /tmp/diagram.drawio
sven-integrations-drawio --json shape add rectangle --label "Start" -p /tmp/diagram.drawio
sven-integrations-drawio --json shape add diamond --label "Decision?" -p /tmp/diagram.drawio
sven-integrations-drawio --json connect <source_id> <target_id> --label "Yes" -p /tmp/diagram.drawio
sven-integrations-drawio --json export png output.png -p /tmp/diagram.drawio
```

## Command groups

### project
`new`, `open`, `save`, `info`, `list-presets`

### shape
`add`, `remove`, `update-label`, `move`, `resize`, `set-style`, `list`, `list-types`

### connect
Adds a connector between two shapes (positional args: source_id, target_id)

### page
`add`, `remove`, `rename`, `list`

### export
`png`, `pdf`, `svg`, `vsdx`, `xml`

### session
`undo`, `redo`, `history`

## Shape types
`rectangle`, `rounded_rectangle`, `diamond`, `ellipse`, `parallelogram`,
`hexagon`, `cylinder`, `cloud`, `star`, `actor`, `database`, `document`,
`process`, `terminator`, `note`

## Presets
`letter` (850×1100), `a4` (827×1169), `hd` (1280×720), `presentation` (1280×960)

## For agents
- `shape add` returns the new shape's ID in `--json` output
- Use shape IDs from `shape list` to reference shapes in `connect` and `set-style`
- `export png` requires the Draw.io desktop app (`draw.io` or `drawio` binary)
