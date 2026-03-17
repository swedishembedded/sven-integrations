---
name: integrations/kdenlive
description: |
  Use when asked to edit video with Kdenlive on Linux/KDE, create video projects,
  add video clips to a timeline, apply video filters, add transitions, or render video.
  Trigger phrases: "edit video with Kdenlive", "Kdenlive timeline", "video project",
  "add video clip", "apply video filter", "render video", "video transition".
version: 2.1.0
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

# 2. Import media into the project bin (returns clip_id e.g. C001)
sven-integrations-kdenlive --json -p "$P" bin import /path/to/video.mp4

# 3. Add a video track, then add a clip (use track_id from track list)
sven-integrations-kdenlive --json -p "$P" track add-video "V1"
sven-integrations-kdenlive --json -p "$P" track list   # get track_id e.g. video_abc123
sven-integrations-kdenlive --json -p "$P" clip add "video_abc123" "C001" --out 2 --pos 0

# 4. Save MLT (optional) and render (requires melt)
sven-integrations-kdenlive --json -p "$P" save --path /tmp/project.mlt
sven-integrations-kdenlive --json -p "$P" export render -o /tmp/output.mp4

ls -lh /tmp/output.mp4
```

## Key rules for agents

1. **Always run `project new` first** — sets the profile (resolution, FPS) for the project.
2. **Always pass `-p /path/to/project.json`** to persist state across commands.
3. **`bin import` returns a clip_id** (e.g. C001, C002) — use it in `clip add TRACK_ID BIN_ID`.
4. **Use track_id, not index** — run `track list` to get track_id (e.g. video_abc123) before `clip add`.
5. **Time units are seconds** — `--pos`, `--in`, `--out` for clips; `--position`, `--duration` for transitions.
6. **`export render` requires `melt`** — install with `apt-get install melt` (Ubuntu/Debian) or `brew install mlt` (macOS).
7. **Profile controls resolution/FPS** — set with `project new --profile` before adding content.

## Command groups

### project
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create a new project | `--profile PROFILE`, `-o /path/to/save.json` |

### open / save (top-level)
| Command | Description | Key flags |
|---------|-------------|-----------|
| `open PATH` | Open an existing .kdenlive/.mlt file | — |
| `save` | Save project to MLT XML | `--path /output.mlt` |

### bin
| Command | Description | Key flags |
|---------|-------------|-----------|
| `import SOURCE` | Import media (returns clip_id C001, C002…) | `--type video\|audio\|image\|color\|title`, `--duration N`, `--name NAME` |
| `remove CLIP_ID` | Remove clip from bin | — |
| `list` | List all bin entries | — |
| `get CLIP_ID` | Show details for a bin entry | — |

### track
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add-video NAME` | Add a video track | `-i, --index N` |
| `add-audio NAME` | Add an audio track | `-i, --index N` |
| `list` | List all tracks (returns track_id, name, kind) | — |
| `remove TRACK_ID` | Remove a track | — |
| `mute TRACK_ID` | Mute a track | `--unmute` to unmute |
| `lock TRACK_ID` | Lock a track | `--unlock` to unlock |

### clip
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add TRACK_ID BIN_ID` | Place a clip on a track | `--pos SEC`, `--out SEC` (required), `--in SEC` |
| `move CLIP_ID POSITION` | Move clip to new position (seconds) | — |
| `trim CLIP_ID` | Trim clip in/out points | `--in SEC`, `--out SEC` |
| `split CLIP_ID SPLIT_POS` | Split clip at position (seconds) | — |
| `remove CLIP_ID` | Remove clip from timeline | — |

### effect
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add CLIP_ID EFFECT_NAME` | Add effect to a clip | `-p key=value` (repeatable) |
| `list CLIP_ID` | List effects on a clip | — |
| `remove CLIP_ID EFFECT_ID` | Remove an effect | — |

**Common effects:** brightness, contrast, saturation, blur, sharpen, volume

### transition
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add TYPE TRACK_A TRACK_B` | Add transition between tracks | `--position SEC`, `--duration SEC`, `-p key=value` |
| `list` | List all transitions | — |
| `remove TRANSITION_ID` | Remove a transition | — |
| `set TRANSITION_ID PARAM_NAME VALUE` | Set transition parameter | — |

**Types:** luma, mix, composite, wipe, etc.

### guide
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add POSITION` | Add a guide at position (seconds) | `--label TEXT`, `--type chapter\|section\|comment` |
| `list` | List all guides | — |
| `remove GUIDE_ID` | Remove a guide | — |

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `xml -o PATH` | Export project as MLT XML | — |
| `render -o PATH` | Render to video (uses melt) | `-p, --profile PROFILE` |
| `presets` | List export presets | — |

### session
| Command | Description |
|---------|-------------|
| `list` | List all sessions |
| `show` | Show active session data |
| `delete` | Delete current session |

## Available profiles (project new --profile)

```
hd1080p30    1920×1080 @ 30fps
hd1080p25    1920×1080 @ 25fps
hd720p30     1280×720 @ 30fps
hd720p25     1280×720 @ 25fps
hdv_1080_25p 1920×1080 @ 25fps
hdv_720_25p  1280×720 @ 25fps
```

## Complete recipe: two-clip edit with fade transition

```bash
P=/tmp/edit.json

# Create project at 30fps HD
sven-integrations-kdenlive --json -p "$P" project new --profile hd1080p30

# Import two clips (note clip_id from output: C001, C002)
sven-integrations-kdenlive --json -p "$P" bin import /path/to/clip1.mp4
sven-integrations-kdenlive --json -p "$P" bin import /path/to/clip2.mp4

# Add two video tracks
sven-integrations-kdenlive --json -p "$P" track add-video "V1"
sven-integrations-kdenlive --json -p "$P" track add-video "V2"
sven-integrations-kdenlive --json -p "$P" track list   # get track_ids (e.g. video_abc123, video_def456)

# Place clips on track 1 (pos 0, 3 sec; pos 3, 3 sec)
sven-integrations-kdenlive --json -p "$P" clip add "video_abc123" "C001" --pos 0 --out 3
sven-integrations-kdenlive --json -p "$P" clip add "video_abc123" "C002" --pos 3 --out 3

# Add luma transition between tracks (position 2.5s, 1s duration)
sven-integrations-kdenlive --json -p "$P" transition add luma "video_abc123" "video_def456" --position 2.5 --duration 1

# Apply brightness (use timeline clip_id from "clip add" JSON output)
sven-integrations-kdenlive --json -p "$P" effect add <timeline_clip_id> brightness -p value=0.2

# Render
sven-integrations-kdenlive --json -p "$P" export render -o /tmp/edited_video.mp4
ls -lh /tmp/edited_video.mp4
```

## Common pitfalls

- **`bin import` returns clip_id (C001, C002)** — capture it for `clip add TRACK_ID BIN_ID`.
- **Use track_id, not track index** — run `track list` to get track_id before adding clips.
- **Time in seconds** — `--pos`, `--in`, `--out`, `--position`, `--duration` are all in seconds.
- **`melt` not found** — install MLT: `apt-get install melt` (Ubuntu) or `brew install mlt` (macOS).
- **`export xml -o PATH`** — use to inspect generated MLT before rendering.
- **DBus message is informational** — "falling back to XML mode" is expected when Kdenlive is not running.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/kdenlive
