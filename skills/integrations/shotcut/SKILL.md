---
name: integrations/shotcut
description: |
  Use when asked to edit video with Shotcut, create MLT video projects, add clips to
  a timeline, apply filters, set transitions, configure compositing, or render video.
  Trigger phrases: "edit video with Shotcut", "MLT video project", "video compositing",
  "picture-in-picture", "video blend mode".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-shotcut]
---

# sven-integrations-shotcut

Stateful CLI for Shotcut video editing using lxml-based MLT XML. Renders via
`melt` or `ffmpeg`.

## Quick start

```bash
sven-integrations-shotcut --json project new -o /tmp/video.mlt --profile hd1080p30
sven-integrations-shotcut --json timeline add-track --name "V1" --type video -p /tmp/video.mlt
sven-integrations-shotcut --json timeline add-clip clip.mp4 --track V1 --start 0 -p /tmp/video.mlt
sven-integrations-shotcut --json filter add brightness --clip-ref <ref> --value 0.2 -p /tmp/video.mlt
sven-integrations-shotcut --json export render output.mp4 -p /tmp/video.mlt
```

## Command groups

### project
`new`, `open`, `save`, `info`, `list-profiles`

### timeline
`add-track`, `remove-track`, `add-clip`, `remove-clip`, `trim-clip`,
`split-clip`, `move-clip`, `ripple-delete`, `list`, `show`

### filter
`list-available`, `add`, `remove`, `set`, `list` — 50+ filters including
color correction, keying, distortion, text/graphics, audio processing

### transition
`list-available`, `add`, `remove`, `list`

### composite
`set-blend-mode`, `set-opacity`, `set-pip-position`

### media
`probe`, `list`, `check`, `thumbnail`

### export
`presets`, `render`

### session
`undo`, `redo`, `history`, `save-session`, `list-sessions`

## Blend modes
`normal`, `add`, `multiply`, `screen`, `overlay`, `darken`, `lighten`,
`color_dodge`, `color_burn`, `hard_light`, `soft_light`, `difference`,
`exclusion`, `hue`, `saturation`, `color`, `luminosity`, `dissolve`

## Export presets
`default`, `h264-high`, `h264-fast`, `h265`, `webm-vp9`, `prores`,
`gif`, `audio-mp3`, `audio-wav`, `png-sequence`

## For agents
- Project files are MLT XML (`.mlt`); use `-p` to specify
- `media probe` uses ffprobe if available, falls back to basic probing
- `export render` tries melt → ffmpeg → generates render script
