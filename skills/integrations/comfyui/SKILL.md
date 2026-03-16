---
name: integrations/comfyui
description: |
  Use when asked to generate AI images using ComfyUI workflows, queue prompts,
  manage ComfyUI models, or download generated images. Trigger phrases:
  "generate image with ComfyUI", "ComfyUI workflow", "queue AI image", "stable diffusion",
  "text to image ComfyUI", "list ComfyUI models", "download generated image".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-comfyui]
---

# sven-integrations-comfyui

CLI for ComfyUI AI image generation. Requires a running ComfyUI instance
(default: http://localhost:8188).

## Quick start

```bash
# Check system status
sven-integrations-comfyui --json system stats

# List available models
sven-integrations-comfyui --json models checkpoints

# Queue a workflow
sven-integrations-comfyui --json queue prompt --workflow my_workflow.json

# Wait for completion and download
sven-integrations-comfyui --json queue status
sven-integrations-comfyui --json images download --filename ComfyUI_00001_.png --output ./output.png
```

## Command groups

### workflow
`load`, `save`, `list`, `validate`

### queue
`prompt` (submit), `status`, `clear`, `history`, `get`, `interrupt`

### models
`checkpoints`, `loras`, `vaes`, `controlnets`, `node-info`, `list-all`

### images
`list`, `download`, `download-prompt`

### system
`stats`, `settings`

## For agents
- ComfyUI must be running locally (default port 8188)
- `--server` option to specify a different host:port
- Workflow files are JSON; use `workflow load` to validate before queuing
- `queue prompt --workflow` returns a `prompt_id` for tracking
- `queue history` shows completed jobs and their output images
- `images download-prompt <prompt_id>` downloads all images from a job
