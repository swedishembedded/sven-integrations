---
name: integrations/shotcut
description: |
  Use when asked to edit video with Shotcut, create video timelines, add clips,
  apply filters, add compositing effects, or render video. Prefer Shotcut over
  Kdenlive on non-KDE/non-Linux systems. Trigger phrases: "edit video with Shotcut",
  "Shotcut timeline", "MLT video", "video filter", "video compositing", "render video".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-shotcut]
---

# sven-integrations-shotcut

Stateful CLI for Shotcut video editing using the MLT XML format. Builds MLT
project files and renders them via the `melt` CLI. Cross-platform; choose this
over `kdenlive` for non-KDE environments.

## Minimal working example

```bash
P=/tmp/shotcut_project.json

# 1. Create a new project
sven-integrations-shotcut --json -p "$P" project new --profile atsc_1080p_30

# 2. Import media
sven-integrations-shotcut --json -p "$P" media import /path/to/video.mp4

# 3. Add a timeline track
sven-integrations-shotcut --json -p "$P" timeline add-track --type video --name "V1"

# 4. Add the clip to the track (use clip ID from media import output)
sven-integrations-shotcut --json -p "$P" timeline add-clip --track-id <TRACK_ID> --clip-path /path/to/video.mp4 --start 0

# 5. Render (requires melt: apt install melt)
sven-integrations-shotcut --json -p "$P" export render --output /tmp/output.mp4

# 6. Verify
ls -lh /tmp/output.mp4
```

## Key rules for agents

1. **Always run `project new` first** with a `--profile` to set resolution/FPS.
2. **Always pass `-p /path/to/project.json`** to persist state.
3. **`media import` registers a file** and returns a clip ID used in timeline operations.
4. **Track IDs come from `timeline add-track` output** — capture the JSON `track_id` field.
5. **`export render` requires `melt`** — install with `apt-get install melt` or `brew install mlt`.
6. **Blend modes apply to compositing** — use `composite set-blend` for video layer blending.
7. **Time is in frames** — multiply seconds × FPS to get frame numbers.

## Command groups

### project
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create a new project | `--profile PROFILE`, `-o PATH` |
| `open PATH` | Load an existing MLT file | — |
| `save` | Save project to MLT file | `--output PATH` |
| `info` | Show project metadata | — |
| `list-profiles` | List available render profiles | — |

### media
| Command | Description | Key flags |
|---------|-------------|-----------|
| `import PATH` | Register a media file (returns clip ID) | — |
| `info PATH` | Get media file metadata | — |

### timeline
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add-track` | Add a track to the timeline | `--type video\|audio`, `--name NAME` |
| `remove-track` | Remove a track | `--track-id ID` |
| `add-clip` | Place a clip on a track | `--track-id ID`, `--clip-path PATH`, `--start FRAME`, `--end FRAME` |
| `remove-clip` | Remove a clip | `--clip-id ID` |
| `move-clip` | Move a clip in time | `--clip-id ID`, `--start FRAME` |
| `trim-clip` | Adjust clip in/out points | `--clip-id ID`, `--in FRAME`, `--out FRAME` |
| `list` | List tracks and clips | — |

### filter
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a filter to a clip | `--clip-id ID`, `--filter FILTER_NAME`, `--param key=value` (repeatable) |
| `remove` | Remove a filter | `--clip-id ID`, `--filter FILTER_NAME` |
| `set` | Update filter parameter | `--clip-id ID`, `--filter FILTER_NAME`, `--param key=value` |
| `list` | List filters on a clip | `--clip-id ID` |
| `list-available` | List available MLT filters | — |

**Common filters:**
```
brightness      value=0.0 (−1.0 to 1.0)
contrast        value=1.0 (multiplier)
saturation      value=1.0 (0=grayscale, 2=vivid)
blur            value=5 (pixel radius)
volume          gain=0.0 (dB, e.g. gain=6 = +6dB)
```

### transition
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a transition between two overlapping clips | `--clip1-id ID`, `--clip2-id ID`, `--type TRANSITION`, `--param key=value` |
| `remove` | Remove a transition | `--transition-id ID` |
| `set` | Update transition parameter | `--transition-id ID`, `--param key=value` |
| `list` | List all transitions | — |
| `list-available` | List available transition types | — |

**Available transitions:** `luma`, `mix`, `composite`, `qtblend`, `movit.luma_mix`

### composite
| Command | Description | Key flags |
|---------|-------------|-----------|
| `set-blend` | Set track blend mode | `--track-index N`, `--mode MODE` |
| `get-blend` | Get blend mode of a track | `--track-index N` |
| `set-opacity` | Set track opacity | `--track-index N`, `--opacity 0.0–1.0` |
| `pip` | Picture-in-picture setup | `--track-index N`, `--rect "x,y,w,h"` |

**Blend modes:** `normal`, `add`, `multiply`, `screen`, `overlay`, `darken`, `lighten`, `difference`, `exclusion`, `hue`, `saturation`, `color`, `luminosity`

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `presets` | List export presets | — |
| `render` | Render project via melt | `--output PATH` (required), `--preset PRESET` |

**Export presets:** `youtube` (H.264/AAC), `vimeo`, `hevc`, `mp3_audio`, `wav_audio`

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
atsc_1080p_30    1920×1080 @ 29.97fps
atsc_1080p_25    1920×1080 @ 25fps
atsc_1080p_24    1920×1080 @ 24fps
atsc_720p_30     1280×720 @ 29.97fps
atsc_720p_25     1280×720 @ 25fps
uhd_2160p_30     3840×2160 @ 30fps
dv_pal           720×576 @ 25fps
dv_ntsc          720×480 @ 29.97fps
```

## Complete recipe: two-clip video with title overlay

```bash
P=/tmp/shotcut_edit.json

# Create project at 1080p30
sven-integrations-shotcut --json -p "$P" project new --profile atsc_1080p_30

# Import clips
sven-integrations-shotcut --json -p "$P" media import /path/to/clip1.mp4
sven-integrations-shotcut --json -p "$P" media import /path/to/clip2.mp4

# Add video track
sven-integrations-shotcut --json -p "$P" timeline add-track --type video --name "Main"
# Capture track_id from output

# Add clips (30fps: 90 frames = 3s)
sven-integrations-shotcut --json -p "$P" timeline add-clip --track-id <TRACK_ID> --clip-path /path/to/clip1.mp4 --start 0 --end 90
sven-integrations-shotcut --json -p "$P" timeline add-clip --track-id <TRACK_ID> --clip-path /path/to/clip2.mp4 --start 90 --end 180

# Brightness boost on clip 2
sven-integrations-shotcut --json -p "$P" filter add --clip-id <CLIP2_ID> --filter brightness --param value=0.15

# Add fade-in transition at the join
sven-integrations-shotcut --json -p "$P" transition add --clip1-id <CLIP1_ID> --clip2-id <CLIP2_ID> --type luma

# Verify
sven-integrations-shotcut --json -p "$P" timeline list

# Render
sven-integrations-shotcut --json -p "$P" export render --output /tmp/final_video.mp4
ls -lh /tmp/final_video.mp4
```

## Common pitfalls

- **`media import` vs `timeline add-clip`** — you must `media import` first (to get a clip ID), then use `timeline add-clip --clip-path` (for the actual file path). The clip ID from import is used for filter/transition operations.
- **`melt` required for rendering** — install with `apt-get install melt` (Ubuntu) or `brew install mlt` (macOS). Check with `which melt`.
- **`export render --output` must be absolute** — use `/tmp/output.mp4` not `output.mp4`.
- **Frames not seconds** — `--start 90` is frame 90. At 30fps: 90/30 = 3 seconds.
- **Track IDs are strings** — capture them from JSON output; they look like `track-001`.
- **Blend mode changes affect compositing** — only relevant when you have overlapping tracks (picture-in-picture, title overlays). For simple cuts, ignore `composite`.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/shotcut
