---
name: integrations/audacity
description: |
  Use when asked to edit audio, mix tracks, apply audio effects, trim clips,
  add labels/markers, or export audio files. Trigger phrases: "edit audio",
  "mix audio tracks", "apply audio effect", "trim audio", "add audio label",
  "export audio", "create podcast", "record audio", "normalize audio".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-audacity]
---

# sven-integrations-audacity

Stateful CLI for audio editing. Manages multi-track audio projects as JSON
with pure-Python WAV rendering (no Audacity binary required for basic ops).

## Quick start

```bash
sven-integrations-audacity --json project new -o /tmp/audio.json --sample-rate 44100
sven-integrations-audacity --json track add --name "Vocals" --type mono -p /tmp/audio.json
sven-integrations-audacity --json clip add --track 0 --source vocals.wav -p /tmp/audio.json
sven-integrations-audacity --json effect add normalize --track 0 -p /tmp/audio.json
sven-integrations-audacity --json export render output.wav -p /tmp/audio.json
```

## Command groups

### project
`new`, `open`, `save`, `info`, `settings`, `json`

### track
`add`, `remove`, `list`, `set`

### clip
`import`, `add`, `remove`, `trim`, `split`, `move`, `list`

### effect
`list-available`, `add`, `remove`, `set`, `list`

### selection
`set`, `all`, `none`, `info`

### label
`add`, `remove`, `list`

### media
`probe`, `check`

### export
`presets`, `render`

### session
`undo`, `redo`, `history`

## Available effects
`amplify`, `normalize`, `fade_in`, `fade_out`, `reverse`, `silence`,
`tone`, `change_speed`, `change_pitch`, `change_tempo`, `echo`,
`low_pass`, `high_pass`, `compress`, `limit`, `noise_reduction`

## Export formats
`wav` (8/16/24/32-bit), `mp3`, `flac`, `ogg`, `aiff`

## For agents
- `-p` specifies project file; `--json` for structured output
- `clip import` probes WAV metadata before adding to track
- `selection set --start 0 --end 5.0` selects a 5-second range
