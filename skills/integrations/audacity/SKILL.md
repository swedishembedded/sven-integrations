---
name: integrations/audacity
description: |
  Use when asked to edit audio, trim clips, apply audio effects, mix tracks,
  export audio to MP3/WAV/FLAC, or work with Audacity projects. Trigger phrases:
  "edit audio", "trim audio", "apply audio effect", "mix audio", "export audio",
  "add audio track", "noise reduction", "normalize audio", "Audacity".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-audacity]
---

# sven-integrations-audacity

Stateful CLI for Audacity audio editing. Communicates with a **running Audacity
instance** via its mod-script-pipe named pipe interface. Both Audacity AND
mod-script-pipe must be enabled before using this integration.

## Prerequisites — enable mod-script-pipe

1. Open Audacity
2. Go to **Edit → Preferences → Modules** (or **Audacity → Preferences → Modules** on macOS)
3. Set **mod-script-pipe** to **Enabled**
4. Restart Audacity
5. Verify: `sven-integrations-audacity --json connect`

## Minimal working example

```bash
P=/tmp/audacity_project.json

# 1. Connect to running Audacity
sven-integrations-audacity --json -p "$P" connect

# 2. Import a media file (creates a track)
sven-integrations-audacity --json -p "$P" media import /path/to/audio.wav

# 3. Apply effect to first track
sven-integrations-audacity --json -p "$P" effect apply normalize --track 0 --params "PeakLevel=-1.0"

# 4. Export result
sven-integrations-audacity --json -p "$P" export render /tmp/output.wav --format wav

# 5. Verify
ls -lh /tmp/output.wav
```

## Key rules for agents

1. **Audacity must be running** with mod-script-pipe enabled before ANY command.
2. **Always run `connect` first** to verify the pipe is available — it gives a clear error if not.
3. **Always pass `-p /absolute/path/to/project.json`** to persist state across calls.
4. **Track indices start at 0** — track 0 is the first track. Use `track list` to check indices.
5. **`export render OUTPUT_PATH`** exports the final mix. Use absolute paths.
6. **Selections define which audio is affected** — use `select range --start S --end E` before time-based operations.
7. **Effects use `--params key=value`** syntax. Use `effect list-available` to see all effects and their parameters.

## Command groups

### connect
```bash
sven-integrations-audacity --json connect
```
Verifies mod-script-pipe is available and Audacity is responding. Always run first.

### track
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a new empty audio track | `--name NAME`, `--type mono\|stereo` |
| `remove` | Remove a track by index | `--track N` |
| `list` | List all tracks with indices | — |
| `get` | Get properties of a track | `--track N` |
| `set` | Set track property | `--track N`, `--name NAME`, `--volume 0.0–1.0`, `--mute`, `--solo` |

### select
| Command | Description | Key flags |
|---------|-------------|-----------|
| `range` | Select a time range on a track | `--track N`, `--start S`, `--end E` (seconds) |
| `all` | Select all audio | — |
| `none` | Clear selection | — |

### effect
| Command | Description | Key flags |
|---------|-------------|-----------|
| `apply` | Apply an effect to selected audio | `--track N`, `--params key=value` (repeatable) |
| `list-available` | List all available effects | — |

**Common effects and params:**
```
normalize       PeakLevel=-1.0 (dB, -60 to 0)
amplify         Ratio=2.0 (linear multiplier)
fade-in         (no params)
fade-out        (no params)
noise-reduction NoiseGain=12 SensitivityThreshold=0 FrequencySmoothingBands=3
compressor      Threshold=-12 NoiseFloor=-40 Ratio=4 AttackTime=0.2 ReleaseTime=1.0
eq              (complex — prefer the Audacity GUI for EQ)
```

### clip
| Command | Description | Key flags |
|---------|-------------|-----------|
| `trim` | Trim audio to selected range | `--track N` |
| `split` | Split a clip at the cursor | `--track N`, `--at TIME` |
| `delete` | Delete selected audio | `--track N` |
| `move` | Move a clip | `--track N`, `--clip-id ID`, `--to TIME` |

### label
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add a label at a time position | `--time T`, `--text "LABEL"` |
| `list` | List all labels | — |

### media
| Command | Description | Key flags |
|---------|-------------|-----------|
| `import` | Import a media file as a new track | `PATH` |

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `render` | Export the project mix | `OUTPUT_PATH` (required), `--format wav\|mp3\|flac\|ogg\|aiff` |
| `presets` | List available export formats | — |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: import, trim, normalize, export

```bash
P=/tmp/audio_edit.json

# Connect to Audacity
sven-integrations-audacity --json -p "$P" connect

# Import a recording
sven-integrations-audacity --json -p "$P" media import /path/to/recording.wav

# Check track list
sven-integrations-audacity --json -p "$P" track list

# Select from 2s to 30s on track 0 (remove silence at start/end)
sven-integrations-audacity --json -p "$P" select range --track 0 --start 2.0 --end 30.0

# Trim to selection
sven-integrations-audacity --json -p "$P" clip trim --track 0

# Select all and normalize
sven-integrations-audacity --json -p "$P" select all
sven-integrations-audacity --json -p "$P" effect apply normalize --track 0 --params "PeakLevel=-1.0"

# Add a label at the start
sven-integrations-audacity --json -p "$P" label add --time 0.0 --text "Intro"

# Export as MP3
sven-integrations-audacity --json -p "$P" export render /tmp/final_audio.mp3 --format mp3
ls -lh /tmp/final_audio.mp3
```

## Common pitfalls

- **"Audacity pipe not found"** — Audacity is not running OR mod-script-pipe is not enabled. Enable in Preferences → Modules, then restart Audacity.
- **Commands time out (30s default)** — Audacity may be busy processing a long effect. For very long audio files, this is expected; the command will eventually complete.
- **Effect params are case-sensitive** — use `PeakLevel` not `peaklevel`. Check `effect list-available` for exact parameter names.
- **`export render` always exports the full project mix** — to export only a selection, use `select range` first.
- **Track indices change after `track remove`** — re-run `track list` after removing tracks to get updated indices.
- **Export format must match the file extension** — use `--format mp3` with `/tmp/out.mp3`.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/audacity
