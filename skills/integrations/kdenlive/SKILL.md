---
name: integrations/kdenlive
description: |
  Use when asked to edit video with Kdenlive, create video projects, add video clips
  to a timeline, apply video filters or transitions, or render video. Trigger phrases:
  "edit video with Kdenlive", "create video project", "add video clip", "video timeline",
  "apply video filter", "add transition", "render video".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-kdenlive]
---

# sven-integrations-kdenlive

Stateful CLI for Kdenlive video editing using MLT XML format. Renders via `melt`.

## Quick start

```bash
sven-integrations-kdenlive --json project new -o /tmp/video.json --profile hd1080p30
sven-integrations-kdenlive --json bin import clip.mp4 -p /tmp/video.json
sven-integrations-kdenlive --json timeline add-track --name "Video 1" --type video -p /tmp/video.json
sven-integrations-kdenlive --json timeline add-clip --track 0 --bin-id <id> --start 0 -p /tmp/video.json
sven-integrations-kdenlive --json export render output.mp4 -p /tmp/video.json
```

## Command groups

### project
`new`, `open`, `save`, `info`, `list-profiles`

### bin
`import`, `remove`, `list`, `get`

### timeline
`add-track`, `remove-track`, `add-clip`, `remove-clip`, `trim-clip`,
`split-clip`, `move-clip`, `list`

### filter
`list-available`, `add`, `remove`, `set`, `list`

### transition
`list-available`, `add`, `remove`, `list`

### guide
`add`, `remove`, `list`

### export
`presets`, `render`

### session
`undo`, `redo`, `history`

## Profiles
`hd1080p30`, `hd1080p25`, `hd1080p24`, `hd720p30`, `hd720p25`,
`4k_uhd_30`, `4k_uhd_25`, `sd_ntsc`, `sd_pal`

## For agents
- `bin import` registers a media file in the project bin and returns its ID
- Track index 0 is the first track; use `timeline list` to see track indices
- `export render` requires `melt` (MLT renderer) to be installed
