---
name: integrations/kdenlive
description: |
  Use when asked to edit video with Kdenlive on Linux/KDE, create video projects,
  add video clips to a timeline, apply video filters, add transitions, or render video.
  Trigger phrases: "edit video with Kdenlive", "Kdenlive timeline", "video project",
  "add video clip", "apply video filter", "render video", "video transition".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-kdenlive]
---

# sven-integrations-kdenlive

Stateful CLI for Kdenlive video editing using the MLT XML format. Builds MLT
project files, applies effects and transitions, and renders via the `melt` CLI.
**No running Kdenlive needed** for most operations — the integration works in
XML-only mode. DBus live editing is attempted first but falls back automatically.

## Minimal working example

```bash
P=/tmp/kdenlive_project.json

# 1. Create a new project
sven-integrations-kdenlive --json -p "$P" project new --profile hd1080p30

# 2. Import media into the project bin
sven-integrations-kdenlive --json -p "$P" bin import /path/to/video.mp4

# 3. Note the bin ID from the output, then add a track and a clip
sven-integrations-kdenlive --json -p "$P" timeline add-track --name "Video 1" --type video
sven-integrations-kdenlive --json -p "$P" timeline add-clip --track 0 --bin-id <id-from-step-2> --start 0

# 4. Render (requires melt to be installed: apt install melt)
sven-integrations-kdenlive --json -p "$P" export render --output /tmp/output.mp4

# 5. Verify
ls -lh /tmp/output.mp4
```

## Key rules for agents

1. **Always run `project new` first** — sets the profile (resolution, FPS) for the project.
2. **Always pass `-p /path/to/project.json`** to persist state across commands.
3. **`bin import` returns a bin ID** — capture it and use it in `timeline add-clip --bin-id <id>`.
4. **Track indices start at 0** — use `timeline list` to check current track indices.
5. **`export render` requires `melt`** — install with `apt-get install melt` (Ubuntu/Debian) or `brew install mlt` (macOS).
6. **Profile controls resolution/FPS** — always set with `project new --profile` before adding content.
7. **Time units** — the `--start` and `--end` parameters for clips are in **frames**, not seconds. Multiply seconds × FPS.

## Command groups

### project
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create a new project | `--profile PROFILE_NAME`, `-o /path/to/save.json` |
| `open PATH` | Open an existing .kdenlive file | — |
| `save` | Save project to file | `--path /output.kdenlive` |
| `info` | Show project metadata | — |
| `list-profiles` | List available render profiles | — |

### bin
| Command | Description | Key flags |
|---------|-------------|-----------|
| `import PATH` | Import media file (returns bin ID) | — |
| `remove` | Remove media from bin | `--bin-id ID` |
| `list` | List all bin entries | — |
| `get` | Get info about a bin entry | `--bin-id ID` |

### timeline
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add-track` | Add a track | `--name NAME`, `--type video\|audio` |
| `remove-track` | Remove a track | `--track-id ID` |
| `add-clip` | Place a clip on the timeline | `--track N`, `--bin-id ID`, `--start FRAME`, `--end FRAME` |
| `remove-clip` | Remove a clip | `--clip-id ID` |
| `move-clip` | Move a clip | `--clip-id ID`, `--new-start FRAME` |
| `trim-clip` | Trim clip in/out points | `--clip-id ID`, `--in FRAME`, `--out FRAME` |
| `split-clip` | Split a clip at a frame | `--clip-id ID`, `--at FRAME` |
| `list` | List tracks and clips | — |

### filter
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list-available` | List all available MLT filters | — |
| `add` | Add a filter to a clip/track | `--clip-ref CLIP_ID`, `--filter FILTER_NAME`, `--param key=value` (repeatable) |
| `remove` | Remove a filter | `--filter-id ID` |
| `set` | Update a filter parameter | `--filter-id ID`, `--param key=value` |
| `list` | List filters on a clip | `--clip-ref CLIP_ID` |

**Common filters:**
```
brightness          value=0.0 (−1.0 to 1.0, 0=no change)
contrast            value=1.0 (multiplier)
saturation          value=1.0 (0=grayscale, 2=vivid)
blur                value=5 (pixel radius)
sharpen             value=0.5
volume              gain=0.0 (dB)
```

### transition
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list-available` | List available transitions | — |
| `add` | Add a transition between tracks | `--from-track N`, `--to-track N`, `--start FRAME`, `--end FRAME`, `--type luma\|mix\|composite` |
| `remove` | Remove a transition | `--transition-id ID` |
| `list` | List all transitions | — |

### guide
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a guide marker | `--time FRAME`, `--label "LABEL"` |
| `remove` | Remove a guide | `--guide-id ID` |
| `list` | List all guides | — |

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `presets` | List export presets | — |
| `render` | Render project to file (uses melt) | `--output PATH` (required), `--profile PROFILE` |
| `xml` | Export project as MLT XML | `--output PATH` |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `redo` | Redo last undone operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Available profiles

```
hd1080p30    1920×1080 @ 30fps
hd1080p25    1920×1080 @ 25fps
hd1080p24    1920×1080 @ 24fps
hd720p30     1280×720 @ 30fps
hd720p25     1280×720 @ 25fps
4k_uhd_30    3840×2160 @ 30fps
4k_uhd_25    3840×2160 @ 25fps
sd_ntsc      720×480 @ 29.97fps
sd_pal       720×576 @ 25fps
```

## Complete recipe: two-clip edit with fade transition

```bash
P=/tmp/edit.json

# Create project at 30fps HD
sven-integrations-kdenlive --json -p "$P" project new --profile hd1080p30

# Import two clips
sven-integrations-kdenlive --json -p "$P" bin import /path/to/clip1.mp4
# Note the id from output, e.g. "clip-001"
sven-integrations-kdenlive --json -p "$P" bin import /path/to/clip2.mp4
# Note the id from output, e.g. "clip-002"

# Add two video tracks
sven-integrations-kdenlive --json -p "$P" timeline add-track --name "V1" --type video
sven-integrations-kdenlive --json -p "$P" timeline add-track --name "A1" --type audio

# Place clips on timeline (30fps: 90 frames = 3 seconds)
sven-integrations-kdenlive --json -p "$P" timeline add-clip --track 0 --bin-id clip-001 --start 0 --end 90
sven-integrations-kdenlive --json -p "$P" timeline add-clip --track 0 --bin-id clip-002 --start 90 --end 180

# Add a luma fade transition at the cut point (15-frame overlap)
sven-integrations-kdenlive --json -p "$P" transition add --from-track 0 --to-track 0 --start 75 --end 105 --type luma

# Apply brightness boost to clip 1
sven-integrations-kdenlive --json -p "$P" filter add --clip-ref clip-001 --filter brightness --param value=0.2

# Verify timeline
sven-integrations-kdenlive --json -p "$P" timeline list

# Render (requires melt)
sven-integrations-kdenlive --json -p "$P" export render --output /tmp/edited_video.mp4
ls -lh /tmp/edited_video.mp4
```

## Common pitfalls

- **`bin import` ID is required** — always capture the `id` field from the JSON output before `timeline add-clip`.
- **Frames not seconds** — `--start 0 --end 90` is frames; at 30fps that's 3 seconds. Multiply: `seconds × fps = frames`.
- **`melt` not found** — install MLT framework: `apt-get install melt` (Ubuntu) or `brew install mlt` (macOS). Without `melt`, `export render` fails.
- **`export xml` to inspect** — use `export xml --output /tmp/check.mlt` to see the generated MLT XML before rendering.
- **DBus connection message is informational** — "DBus connection failed; falling back to XML mode" is expected when Kdenlive is not running. Everything works in XML mode.
- **Profile must match clips** — if your clips are 1080p25 and you chose `hd1080p30`, melt may upscale/convert. Match profile to source material.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/kdenlive
