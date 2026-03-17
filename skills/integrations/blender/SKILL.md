---
name: integrations/blender
description: |
  Use when asked to create 3D scenes, add 3D objects, set materials or lighting,
  configure cameras, animate objects, or render images with Blender. Trigger phrases:
  "create 3D scene", "add 3D object", "render 3D", "Blender scene", "set material",
  "blender render", "3D model", "add cube", "add sphere", "lighting".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-blender]
---

# sven-integrations-blender

Stateful CLI for Blender 3D operations. Stores a scene description (objects,
materials, frame range, FPS) in a JSON project file and executes Python scripts
inside Blender's headless mode (`blender --background --python-expr`).
**Blender must be installed** and on PATH for `render` to work.

## Minimal working example — create a scene and render it

```bash
P=/tmp/blender_project.json

# 1. Start a new session with a scene
sven-integrations-blender --json -p "$P" scene frame-range 1 250
sven-integrations-blender --json -p "$P" scene fps 24

# 2. Add objects
sven-integrations-blender --json -p "$P" object add CUBE --location 0 0 0
sven-integrations-blender --json -p "$P" object add LIGHT --location 4 4 6

# 3. Set a material on the cube
sven-integrations-blender --json -p "$P" material create "BlueMat" --color 0.1 0.3 0.9 1.0

# 4. Render frame 1 (requires Blender to be installed)
sven-integrations-blender --json -p "$P" render --output /tmp/blender_render.png --frame 1

# 5. Verify
ls -lh /tmp/blender_render.png
```

## Key rules for agents

1. **Blender must be on PATH** — install Blender and verify with `which blender`. Set `BLENDER_BIN` env variable to override.
2. **Always use `-p /absolute/path/to/project.json`** to persist session state across commands.
3. **`object add` takes a MESH_TYPE argument** — valid types: `CUBE`, `SPHERE`, `CYLINDER`, `CONE`, `PLANE`, `TORUS`, `CAMERA`, `LIGHT`, `EMPTY`.
4. **`render --output` requires an absolute path** with a recognized extension (`.png`, `.jpg`, `.exr`).
5. **Materials use RGBA floats (0.0–1.0)** — `--color R G B A` where all values are 0.0–1.0.
6. **`scene frame-range` and `scene fps` set scene parameters** — call these before rendering.
7. **`object list` shows what's tracked in the session** — use to verify objects before rendering.

## Command groups

### scene
| Command | Description | Key flags |
|---------|-------------|-----------|
| `frame-range START END` | Set frame range | `START`, `END` (integers) |
| `fps VALUE` | Set frames per second | `VALUE` (integer, e.g. 24, 30, 60) |
| `info` | Show scene details from session | — |

### object
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add MESH_TYPE` | Add a primitive mesh | `--location X Y Z` (default: 0 0 0) |
| `delete NAME` | Delete a named object | — |
| `move NAME X Y Z` | Move object to new coordinates | — |
| `list` | List all tracked objects | — |

**Valid MESH_TYPE values:** `CUBE`, `SPHERE`, `CYLINDER`, `CONE`, `PLANE`, `TORUS`, `CAMERA`, `LIGHT`, `EMPTY`, `CIRCLE`, `GRID`, `MONKEY`

### material
| Command | Description | Key flags |
|---------|-------------|-----------|
| `create NAME` | Create Principled BSDF material | `--color R G B A` (floats 0–1) |
| `assign OBJECT_NAME MATERIAL_NAME` | Assign material to object | — |
| `list` | List all materials script | — |

### modifier
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add OBJECT_NAME TYPE` | Add a modifier | `--params key=value` (repeatable) |
| `list OBJECT_NAME` | List modifiers on an object | — |

**Valid modifier types:** `SUBDIVISION`, `SOLIDIFY`, `ARRAY`, `MIRROR`, `BOOLEAN`, `BEVEL`, `DECIMATE`

### camera
| Command | Description | Key flags |
|---------|-------------|-----------|
| `set` | Set active camera properties | `--location X Y Z`, `--rotation X Y Z`, `--lens FOCAL_LENGTH` |

### light
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add TYPE` | Add a light | `--location X Y Z`, `--energy WATTS`, `--color R G B` |

**Light types:** `SUN`, `POINT`, `SPOT`, `AREA`

### animation
| Command | Description | Key flags |
|---------|-------------|-----------|
| `keyframe OBJECT_NAME FRAME` | Insert keyframe | `--location X Y Z`, `--rotation X Y Z` |

### render
| Command | Description | Key flags |
|---------|-------------|-----------|
| `render` | Render frame to file (runs Blender) | `--output PATH` (required), `--frame N` |
| `open PATH` | Record a .blend file path in session | — |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `show` | Show session info |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: scene with cube, material, and render

```bash
P=/tmp/my_scene.json

# Set up scene
sven-integrations-blender --json -p "$P" scene frame-range 1 48
sven-integrations-blender --json -p "$P" scene fps 24

# Add objects at different positions
sven-integrations-blender --json -p "$P" object add PLANE --location 0 0 -0.5
sven-integrations-blender --json -p "$P" object add CUBE --location 0 0 1
sven-integrations-blender --json -p "$P" object add SPHERE --location 3 0 0.5
sven-integrations-blender --json -p "$P" object add LIGHT --location 5 5 10

# Create and assign materials
sven-integrations-blender --json -p "$P" material create "RedMat" --color 0.9 0.1 0.1 1.0
sven-integrations-blender --json -p "$P" material create "GreenMat" --color 0.1 0.8 0.1 1.0
sven-integrations-blender --json -p "$P" material assign CUBE RedMat
sven-integrations-blender --json -p "$P" material assign Sphere GreenMat

# Configure camera
sven-integrations-blender --json -p "$P" camera set --location 7 -7 5 --rotation 63 0 46 --lens 50

# Verify objects before render
sven-integrations-blender --json -p "$P" object list

# Render
sven-integrations-blender --json -p "$P" render --output /tmp/scene_render.png --frame 1
ls -lh /tmp/scene_render.png
```

## Common pitfalls

- **"Blender binary not found"** — install Blender, verify `which blender`. If installed in a non-standard location, set `BLENDER_BIN=/path/to/blender` before running.
- **`--output` must be absolute** — use `/tmp/render.png` not `render.png`. Relative paths fail silently.
- **Color values are floats 0.0–1.0** — not 0–255. `--color 1.0 0.0 0.0 1.0` is red; `--color 255 0 0 1.0` is wrong.
- **`object add` takes the mesh type as ARGUMENT** not an option — `object add CUBE` not `object add --type CUBE`.
- **`render` requires a `.blend` file OR a script** — without a `.blend` file, the render uses the default empty scene. Use `open /path/to/file.blend` first to render an existing blend file.
- **Frame range must be set before rendering** — `scene frame-range 1 250` sets the timeline; without it you get the default 1–250.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from this JSON file
- `-s` / `--session NAME` — named session in state directory (use `-p` instead for explicitness)
- `--location X Y Z` — 3D coordinates as three floats
- `--color R G B A` — RGBA color as four floats in range 0.0–1.0

Base directory: /usr/share/sven/skills/integrations/blender
