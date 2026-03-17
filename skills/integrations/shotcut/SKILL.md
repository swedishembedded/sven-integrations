---
name: integrations/shotcut
description: |
  Use when asked to edit video with Shotcut, create video timelines, add clips,
  apply filters, add compositing effects, or render video. Prefer Shotcut over
  Kdenlive on non-KDE/non-Linux systems. Trigger phrases: "edit video with Shotcut",
  "Shotcut timeline", "MLT video", "video filter", "video compositing", "render video".
version: 2.1.0
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

# 2. Add a track (get track_id from output)
sven-integrations-shotcut --json -p "$P" track add "V1"

# 3. Add a clip (clip add TRACK_ID RESOURCE --out N --pos N)
sven-integrations-shotcut --json -p "$P" clip add <TRACK_ID> /path/to/video.mp4 --out 90 --pos 0

# 4. Optional: save MLT file
sven-integrations-shotcut --json -p "$P" project save -o /tmp/project.mlt

# 5. Render (requires melt: apt install melt)
sven-integrations-shotcut --json -p "$P" export render -o /tmp/output.mp4

ls -lh /tmp/output.mp4
```

## Key rules for agents

1. **Always run `project new` first** with a `--profile` to set resolution/FPS.
2. **Always pass `-p /path/to/project.json`** to persist state.
3. **`clip add` returns clip_id** — use it for filter/transition operations.
4. **Track IDs come from `track add` output** — capture the JSON `track_id` field.
5. **`export render` requires `melt`** — install with `apt-get install melt` or `brew install mlt`.
6. **Time is in frames** — multiply seconds × FPS to get frame numbers (e.g. 3s @ 30fps = 90 frames).
7. **`media import PATH`** — optional; returns path for use in clip add. You can use the path directly in `clip add`.

## Command groups

### project
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create a new project | `--profile PROFILE`, `-o PATH` |
| `save` | Save project to MLT file | `-o PATH` (required) |

### media
| Command | Description | Key flags |
|---------|-------------|-----------|
| `import PATH` | Register media (returns path for clip add) | — |
| `probe PATH` | Get media metadata | — |
| `list` | List resources in project | — |
| `check` | Verify media files exist | — |
| `thumbnail PATH` | Extract thumbnail | `-o PATH`, `--time SEC` |

### track
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `add NAME` | Add a track | `--hide 0\|1\|2` |
| `remove TRACK_ID` | Remove a track | — |
| `list` | List all tracks | — |
| `mute TRACK_ID` | Mute track | `--audio` for audio only |

### clip
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `add TRACK_ID RESOURCE` | Add clip to track | `--in N`, `--out N` (required), `--pos N` |
| `remove CLIP_ID` | Remove a clip | — |
| `trim CLIP_ID` | Trim in/out points | `--in N`, `--out N` |
| `move CLIP_ID POSITION` | Move clip (frames) | — |

### filter
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `add CLIP_ID FILTER_NAME` | Add filter to clip | `-p key=value` (repeatable) |
| `remove CLIP_ID FILTER_NAME` | Remove filter | — |
| `list CLIP_ID` | List filters on clip | — |

**Common filters:** brightness, contrast, blur, fade_in, fade_out

### transition
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `add NAME` | Add transition between tracks | `--track-a N`, `--track-b N`, `--in N`, `--out N`, `-p key=value` |
| `remove INDEX` | Remove transition | — |
| `set INDEX PARAM VALUE` | Set transition param | — |
| `list` | List transitions | — |
| `available` | List available types | `--category dissolve\|wipe` |

### composite
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `set-blend TRACK_INDEX MODE` | Set track blend mode | — |
| `get-blend TRACK_INDEX` | Get blend mode | — |
| `set-opacity TRACK_INDEX VALUE` | Set opacity (0–1) | — |
| `pip TRACK_INDEX CLIP_INDEX` | Picture-in-picture | `--x`, `--y`, `--width`, `--height` |
| `blend-modes` | List blend modes | — |

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `render` | Render via melt | `-o PATH` (required), `-p preset` |
| `presets` | List export presets | — |

**Presets:** youtube, vimeo, dnxhd, prores, gif, mp3

### session
| Command | Description |
|---------|-------------|
| `show` | Show session data |
| `list` | List sessions |
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

## Complete recipe: two-clip video with filter

```bash
P=/tmp/shotcut_edit.json

# Create project at 1080p30
sven-integrations-shotcut --json -p "$P" project new --profile atsc_1080p_30

# Add track
sven-integrations-shotcut --json -p "$P" track add "Main"
# Capture track_id from output

# Add clips (30fps: 90 frames = 3s each)
sven-integrations-shotcut --json -p "$P" clip add <TRACK_ID> /path/to/clip1.mp4 --out 90 --pos 0
# Capture clip_id from output
sven-integrations-shotcut --json -p "$P" clip add <TRACK_ID> /path/to/clip2.mp4 --out 90 --pos 90

# Add brightness filter to second clip
sven-integrations-shotcut --json -p "$P" filter add <CLIP2_ID> brightness -p value=0.15

# Add transition between tracks (need two tracks)
sven-integrations-shotcut --json -p "$P" track add "V2"
sven-integrations-shotcut --json -p "$P" transition add luma --track-a 0 --track-b 1 --in 85 --out 95

# Render
sven-integrations-shotcut --json -p "$P" export render -o /tmp/final_video.mp4
ls -lh /tmp/final_video.mp4
```

## Common pitfalls

- **`melt` required** — install with `apt-get install melt` (Ubuntu) or `brew install mlt` (macOS).
- **`export render -o` must be absolute** — use `/tmp/output.mp4` not `output.mp4`.
- **Frames not seconds** — `--out 90` is 90 frames. At 30fps: 90/30 = 3 seconds.
- **Track IDs are strings** — e.g. `track_abc123`. Capture from `track add` or `track list`.
- **clip add --out required** — always specify `--out` (end frame) for the clip.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/shotcut
