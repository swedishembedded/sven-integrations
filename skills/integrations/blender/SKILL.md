---
name: integrations/blender
description: |
  Use when asked to create 3D scenes, add 3D objects, set materials, animate objects,
  configure lighting, or render images/animations. Trigger phrases: "create 3D scene",
  "add 3D object", "set material", "render scene", "create animation", "3D modeling",
  "add light", "configure camera".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-blender]
---

# sven-integrations-blender

Stateful CLI for 3D scene creation and rendering. Manages Blender scenes as JSON
and generates bpy scripts for headless Blender rendering.

## Quick start

```bash
sven-integrations-blender --json scene new -o /tmp/scene.json
sven-integrations-blender --json object add cube --name MyCube -p /tmp/scene.json
sven-integrations-blender --json material create Red --color 1.0 0.0 0.0 1.0 -p /tmp/scene.json
sven-integrations-blender --json material assign Red --object MyCube -p /tmp/scene.json
sven-integrations-blender --json light add SUN --name Sun --energy 5.0 -p /tmp/scene.json
sven-integrations-blender --json render execute output.png -p /tmp/scene.json
```

## Command groups

### scene
`new`, `open`, `save`, `info`, `profiles`, `json`

### object
`add` (cube/sphere/cylinder/cone/plane/torus/monkey/empty),
`remove`, `duplicate`, `transform`, `set`, `list`, `get`

### material
`create`, `assign`, `set`, `list`, `get`

### modifier
`list-available`, `add`, `remove`, `set`, `list`

### camera
`add`, `set`, `set-active`, `list`

### light
`add` (POINT/SUN/SPOT/AREA), `set`, `list`

### animation
`keyframe`, `remove-keyframe`, `frame-range`, `fps`, `list-keyframes`

### render
`settings`, `info`, `presets`, `execute`, `script`

### session
`undo`, `redo`, `history`

## Object types
`cube`, `sphere`, `cylinder`, `cone`, `plane`, `torus`, `monkey`, `empty`

## For agents
- `--json` for structured output; `-p` for project file
- `render execute` generates a bpy script and runs Blender headlessly
- `render script` generates the bpy script without running Blender
