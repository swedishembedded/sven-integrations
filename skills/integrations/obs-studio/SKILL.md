---
name: integrations/obs-studio
description: |
  Use when asked to control OBS Studio: manage scenes, sources, audio, start/stop
  recording or streaming, apply filters, or manage outputs. Requires OBS Studio
  to be running with obs-websocket enabled. Trigger phrases: "start recording",
  "stop recording", "start streaming", "OBS scene", "switch scene", "add source",
  "control OBS", "screen capture", "add audio source".
version: 2.1.0
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
sven-integrations-obs-studio --json -p "$P" scene create "My Scene"

# 4. Switch to the new scene
sven-integrations-obs-studio --json -p "$P" scene switch "My Scene"

# 5. Add a display capture source (source add SCENE NAME KIND)
sven-integrations-obs-studio --json -p "$P" source add "My Scene" "Desktop" display_capture

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
6. **Audio inputs** — use `source add SCENE NAME pulse_input_capture` (Linux) for microphone; `audio` group is project-level config.
7. **`output recording start --path`** — the path must be absolute and use a supported extension (`.mkv`, `.mp4`).

## Command groups

### connect
```bash
sven-integrations-obs-studio --json connect --host localhost --port 4455 [--password PASSWORD]
```
Connects to OBS WebSocket. Shows OBS version on success.

### scene
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `list` | List all scenes | — |
| `create NAME` | Create a new scene | — |
| `remove NAME` | Remove a scene | — |
| `switch NAME` | Set the active scene | — |
| `current` | Get the current scene | — |
| `duplicate NAME` | Duplicate a scene | `--new-name NEW_NAME` |

### source
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `list SCENE` | List sources in a scene | — |
| `add SCENE NAME KIND` | Add a source to a scene | `--settings '{"key": "value"}'` |
| `remove SCENE NAME` | Remove a source | — |
| `show SCENE NAME` | Make a source visible | — |
| `hide SCENE NAME` | Hide a source | — |
| `transform SCENE NAME` | Set position/size | `--x X`, `--y Y`, `--width W`, `--height H` |

**Common source types and settings:**
```
display_capture      {}  (captures entire display)
window_capture       {"window": "Window Title:App:Class"}
browser_source       {"url": "https://...", "width": 1280, "height": 720}
image_source         {"file": "/absolute/path/to/image.png"}
text_ft2_source_v2   {"text": "Hello", "font": {"face": "Arial", "size": 64}}
media_source         {"local_file": "/path/to/video.mp4", "looping": true}
```

### audio (project-level config)
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `add` | Add audio source to project | `--name NAME`, `--type input\|output`, `--device ID` |
| `remove INDEX` | Remove audio source | — |
| `volume INDEX LEVEL` | Set volume (0–3) | — |
| `mute INDEX` | Mute source | — |
| `unmute INDEX` | Unmute source | — |
| `list` | List audio sources | — |
| `monitor INDEX MODE` | Set monitoring | `none`, `monitor_only`, `monitor_and_output` |

**For OBS audio inputs**, use `source add SCENE NAME pulse_input_capture` (Linux) or `wasapi_input_capture` (Windows).

### filter (project-level config)
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `add FILTER_TYPE` | Add filter to source | `--source NAME`, `--name NAME`, `-p key=value` |
| `remove SOURCE INDEX` | Remove filter | — |
| `set SOURCE INDEX PARAM VALUE` | Update filter param | — |
| `list SOURCE` | List filters on source | — |
| `available` | List available filter types | `--category video\|audio` |

**Filter types:** `color_correction`, `chroma_key`, `luma_key`, `noise_suppress`, `noise_gate`, `gain`, `compressor`, `limiter`

### output
| Command | Description | Key flags |
|---------|-------------|-----------|
| `recording start` | Start recording | `--path /tmp/out.mkv` (sets directory) |
| `recording stop` | Stop recording | — |
| `recording status` | Get recording status | — |
| `recording config` | Configure recording (project) | `--path`, `--format mkv\|mp4`, `--quality` |
| `streaming start` | Start streaming | — |
| `streaming stop` | Stop streaming | — |
| `streaming status` | Get streaming status | — |
| `streaming config` | Configure streaming (project) | `--server`, `--key` |
| `settings` | Set encoding settings | `--width`, `--height`, `--fps`, etc. |
| `info` | Show output config | — |
| `presets` | List encoding presets | — |

### transition (project-level config)
| Command | Description | Args/Flags |
|---------|-------------|-------------|
| `list` | List transitions | — |
| `add TYPE` | Add transition | `--name NAME`, `--duration MS` |
| `remove INDEX` | Remove transition | — |
| `set-active INDEX` | Set active transition | — |
| `duration INDEX MS` | Set duration | — |

**Types:** `cut`, `fade`, `swipe`, `slide`, `stinger`, `fade_to_color`, `luma_wipe`

### session
| Command | Description |
|---------|-------------|
| `show` | Show session state |
| `list` | List all sessions |
| `delete NAME` | Delete a session |

## Complete recipe: set up a scene and record

```bash
P=/tmp/obs_session.json

# Connect
sven-integrations-obs-studio --json -p "$P" connect --host localhost --port 4455

# Check current state
sven-integrations-obs-studio --json -p "$P" scene list

# Create a streaming scene
sven-integrations-obs-studio --json -p "$P" scene create "Stream"
sven-integrations-obs-studio --json -p "$P" scene switch "Stream"

# Add desktop capture (source add SCENE NAME KIND)
sven-integrations-obs-studio --json -p "$P" source add "Stream" "Desktop" display_capture

# Add microphone as OBS source
sven-integrations-obs-studio --json -p "$P" source add "Stream" "Mic" pulse_input_capture

# Add a text overlay with settings
sven-integrations-obs-studio --json -p "$P" source add "Stream" "Title" text_ft2_source_v2 \
  --settings '{"text": "Live Now", "font": {"face": "Arial", "size": 72}}'

# Position the text at top-center
sven-integrations-obs-studio --json -p "$P" source transform "Stream" "Title" --x 760 --y 10 --width 400 --height 100

# Apply chroma key (filter add FILTER_TYPE --source NAME -p key=value)
sven-integrations-obs-studio --json -p "$P" filter add chroma_key --source "Desktop" --name "GreenScreen" \
  -p similarity=80 -p smoothness=25

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
