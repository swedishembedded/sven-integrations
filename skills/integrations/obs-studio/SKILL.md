---
name: integrations/obs-studio
description: |
  Use when asked to control OBS Studio: manage scenes, sources, audio, start/stop
  recording or streaming, apply filters, or manage outputs. Requires OBS Studio
  to be running with obs-websocket enabled. Trigger phrases: "start recording",
  "stop recording", "start streaming", "OBS scene", "switch scene", "add source",
  "control OBS", "screen capture", "add audio source".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-obs-studio]
---

# sven-integrations-obs-studio

CLI for controlling OBS Studio via the obs-websocket v5 protocol. **OBS Studio
must be running** with the WebSocket server enabled before using any commands.

## Prerequisites — enable obs-websocket

1. Open OBS Studio
2. Go to **Tools → WebSocket Server Settings**
3. Check **Enable WebSocket server**
4. Set a port (default 4455) and optionally a password
5. Click OK
6. Connect: `sven-integrations-obs-studio --json connect --host localhost --port 4455`

## Minimal working example

```bash
P=/tmp/obs_project.json

# 1. Connect to OBS
sven-integrations-obs-studio --json -p "$P" connect --host localhost --port 4455

# 2. List existing scenes
sven-integrations-obs-studio --json -p "$P" scene list

# 3. Create a new scene
sven-integrations-obs-studio --json -p "$P" scene create --name "My Scene"

# 4. Switch to the new scene
sven-integrations-obs-studio --json -p "$P" scene switch --name "My Scene"

# 5. Add a display capture source
sven-integrations-obs-studio --json -p "$P" source add --scene "My Scene" --name "Desktop" --type display_capture

# 6. Start recording
sven-integrations-obs-studio --json -p "$P" output recording start --path /tmp/recording.mkv

# 7. ... do work ...

# 8. Stop recording
sven-integrations-obs-studio --json -p "$P" output recording stop
```

## Key rules for agents

1. **OBS must be running** with WebSocket server enabled (Tools → WebSocket Server Settings).
2. **Always `connect` first** — without a connection, all commands fail.
3. **Always pass `-p /path/to/project.json`** to persist connection settings across commands.
4. **Scenes must exist before adding sources** — use `scene create` or verify with `scene list`.
5. **Source types are OBS-specific** — common types: `display_capture`, `window_capture`, `browser_source`, `image_source`, `text_ft2_source_v2`, `obs_virtual_camera`, `wasapi_input_capture` (Windows), `pulse_input_capture` (Linux).
6. **Audio sources are separate from video sources** — use `audio add` for microphones/output capture.
7. **`output recording start --path`** — the path must be absolute and use a supported extension (`.mkv`, `.mp4`).

## Command groups

### connect
```bash
sven-integrations-obs-studio --json connect --host localhost --port 4455 [--password PASSWORD]
```
Connects to OBS WebSocket. Shows OBS version on success.

### scene
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List all scenes | — |
| `create` | Create a new scene | `--name NAME` |
| `remove` | Remove a scene | `--name NAME` |
| `switch` | Set the active/preview scene | `--name NAME` |
| `current` | Get the current program/preview scene | — |
| `duplicate` | Duplicate a scene | `--name NAME`, `--new-name NEW_NAME` |

### source
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List sources in a scene | `--scene NAME` |
| `add` | Add a source to a scene | `--scene NAME`, `--name NAME`, `--type TYPE`, `--settings '{"key": "value"}'` |
| `remove` | Remove a source from a scene | `--scene NAME`, `--name NAME` |
| `show` | Make a source visible | `--scene NAME`, `--name NAME` |
| `hide` | Hide a source | `--scene NAME`, `--name NAME` |
| `transform` | Set position/size | `--scene NAME`, `--name NAME`, `--x X`, `--y Y`, `--width W`, `--height H` |

**Common source types and settings:**
```
display_capture      {}  (captures entire display)
window_capture       {"window": "Window Title:App:Class"}
browser_source       {"url": "https://...", "width": 1280, "height": 720}
image_source         {"file": "/absolute/path/to/image.png"}
text_ft2_source_v2   {"text": "Hello", "font": {"face": "Arial", "size": 64}}
media_source         {"local_file": "/path/to/video.mp4", "looping": true}
```

### audio
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add an audio capture source | `--name NAME`, `--type TYPE`, `--device DEVICE_ID` |
| `remove` | Remove audio source | `--name NAME` |
| `volume` | Set source volume | `--name NAME`, `--volume 0.0–1.0` |
| `mute` | Mute a source | `--name NAME` |
| `unmute` | Unmute a source | `--name NAME` |
| `list` | List audio sources | — |
| `monitor` | Set audio monitoring | `--name NAME`, `--mode none\|monitor\|both` |

**Audio source types:**
```
pulse_input_capture     Linux microphone input (PulseAudio/PipeWire)
pulse_output_capture    Linux desktop audio output capture
wasapi_input_capture    Windows microphone
wasapi_output_capture   Windows desktop audio
coreaudio_input_capture macOS microphone
```

### filter
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a filter to a source | `--source NAME`, `--filter-name NAME`, `--type TYPE`, `--param key=value` (repeatable) |
| `remove` | Remove a filter | `--source NAME`, `--filter-name NAME` |
| `set` | Update filter parameters | `--source NAME`, `--filter-name NAME`, `--param key=value` |
| `list` | List filters on a source | `--source NAME` |

**Common filter types:**
```
color_correction        brightness, contrast, saturation, gamma, hue_shift
sharpen                 sharpness
chroma_key_filter_v2    similarity, smoothness, key_color (for green-screen)
color_key_filter_v2     similarity, smoothness, key_color
crop_filter             left, right, top, bottom (pixels)
scale_filter            resolution (e.g. "1920x1080")
```

### output
| Command | Description | Key flags |
|---------|-------------|-----------|
| `recording start` | Start recording | `--path /absolute/output.mkv` |
| `recording stop` | Stop recording | — |
| `recording status` | Get recording status | — |
| `streaming start` | Start streaming | — |
| `streaming stop` | Stop streaming | — |
| `streaming status` | Get streaming status | — |
| `virtualcam start` | Start virtual camera | — |
| `virtualcam stop` | Stop virtual camera | — |

### transition
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List available transitions | — |
| `add` | Add a transition | `--name NAME`, `--type TYPE`, `--duration MS` |
| `remove` | Remove a transition | `--name NAME` |
| `set-active` | Set active transition | `--name NAME` |
| `duration` | Set transition duration | `--name NAME`, `--duration MS` |

**Transition types:** `cut`, `fade`, `swipe`, `slide`, `stinger`, `fade_to_color`, `luma_wipe`

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: set up a scene and record

```bash
P=/tmp/obs_session.json

# Connect
sven-integrations-obs-studio --json -p "$P" connect --host localhost --port 4455

# Check current state
sven-integrations-obs-studio --json -p "$P" scene list

# Create a streaming scene
sven-integrations-obs-studio --json -p "$P" scene create --name "Stream"
sven-integrations-obs-studio --json -p "$P" scene switch --name "Stream"

# Add desktop capture
sven-integrations-obs-studio --json -p "$P" source add --scene "Stream" --name "Desktop" --type display_capture

# Add microphone
sven-integrations-obs-studio --json -p "$P" audio add --name "Mic" --type pulse_input_capture

# Add a text overlay
sven-integrations-obs-studio --json -p "$P" source add \
  --scene "Stream" \
  --name "Title" \
  --type text_ft2_source_v2 \
  --settings '{"text": "Live Now", "color1": 4294967295, "font": {"face": "Arial", "size": 72}}'

# Position the text at top-center
sven-integrations-obs-studio --json -p "$P" source transform \
  --scene "Stream" --name "Title" --x 760 --y 10 --width 400 --height 100

# Apply chroma key to a source (green screen)
sven-integrations-obs-studio --json -p "$P" filter add \
  --source "Desktop" \
  --filter-name "GreenScreen" \
  --type chroma_key_filter_v2 \
  --param similarity=80 \
  --param smoothness=25

# Start recording
sven-integrations-obs-studio --json -p "$P" output recording start --path /tmp/recording.mkv

# ... do your recording ...

# Stop
sven-integrations-obs-studio --json -p "$P" output recording stop
ls -lh /tmp/recording.mkv
```

## Common pitfalls

- **"Cannot connect to OBS WebSocket"** — OBS must be running AND WebSocket enabled. Check Tools → WebSocket Server Settings. Make sure Enable is checked and port matches.
- **Connection times out** — if OBS is running but doesn't respond, check the firewall isn't blocking port 4455.
- **Password required** — if you set a password in OBS, pass it with `--password yourpassword`.
- **Source type names are platform-specific** — `pulse_input_capture` works on Linux; use `wasapi_input_capture` on Windows and `coreaudio_input_capture` on macOS.
- **`output recording start` path must be absolute** — use `/tmp/recording.mkv` not `recording.mkv`.
- **Scene doesn't exist** — always `scene create` before `source add --scene`. Use `scene list` to verify.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/obs-studio
