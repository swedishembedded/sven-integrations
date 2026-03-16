---
name: integrations/obs-studio
description: |
  Use when asked to control OBS Studio, configure streaming or recording, manage
  scenes, add sources, or configure audio. Trigger phrases: "start recording",
  "start streaming", "add OBS scene", "configure OBS", "add video source",
  "configure stream", "set up recording", "OBS filter".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-obs-studio]
---

# sven-integrations-obs-studio

Stateful CLI for OBS Studio configuration. Manages OBS project files as JSON;
actual streaming/recording requires OBS with obs-websocket.

## Quick start

```bash
sven-integrations-obs-studio --json project new -o /tmp/obs.json
sven-integrations-obs-studio --json scene add --name "Main Scene" -p /tmp/obs.json
sven-integrations-obs-studio --json source add video_capture --name "Webcam" --scene "Main Scene" -p /tmp/obs.json
sven-integrations-obs-studio --json audio set-volume --source "Mic" --volume 0.8 -p /tmp/obs.json
sven-integrations-obs-studio --json output configure-stream --url rtmp://live.twitch.tv/app --key YOUR_KEY -p /tmp/obs.json
```

## Command groups

### project
`new`, `open`, `save`, `info`

### scene
`add`, `remove`, `duplicate`, `set-active`, `list`

### source
`add`, `remove`, `set`, `list` — types: `video_capture`, `audio_capture`,
`display_capture`, `browser`, `color`, `text`, `image`, `media_source`, `scene`

### filter
`add`, `remove`, `set`, `list` — video: `color_correction`, `chroma_key`, `lut`;
audio: `gain`, `compressor`, `noise_gate`, `limiter`, `noise_suppression`

### audio
`set-volume`, `set-mute`, `set-monitor`, `set-balance`, `set-sync-offset`, `list`

### transition
`add`, `set-active`, `list`

### output
`configure-stream`, `configure-recording`, `list-encoders`, `get-status`

### session
`undo`, `redo`, `history`

## For agents
- Project files are JSON; actual OBS control requires obs-websocket
- Source types require the corresponding OBS plugin/capture device
