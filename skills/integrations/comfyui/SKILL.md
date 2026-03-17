---
name: integrations/comfyui
description: |
  Use when asked to generate AI images using Stable Diffusion, run ComfyUI
  workflows, upscale images, or manage AI image generation models. Requires a
  running ComfyUI server. Trigger phrases: "generate AI image", "Stable Diffusion",
  "ComfyUI", "text to image", "image to image", "upscale image", "AI art".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-comfyui]
---

# sven-integrations-comfyui

CLI for AI image generation via ComfyUI. Submits workflows to a **running
ComfyUI server** and downloads generated images. The server must be started
separately before using any commands.

## Prerequisites — start ComfyUI server

```bash
# In the ComfyUI directory:
cd /path/to/ComfyUI
python main.py --listen 0.0.0.0 --port 8188

# Then connect:
sven-integrations-comfyui --json connect
```

## Minimal working example — text-to-image

```bash
P=/tmp/comfy_project.json

# 1. Connect (default: http://127.0.0.1:8188)
sven-integrations-comfyui --json -p "$P" connect

# 2. Check available models
sven-integrations-comfyui --json -p "$P" models checkpoints

# 3. Generate an image
sven-integrations-comfyui --json -p "$P" generate \
  --positive "a beautiful sunset over the ocean, golden hour, photorealistic" \
  --negative "blurry, low quality, watermark" \
  --model "v1-5-pruned-emaonly.safetensors" \
  --width 768 \
  --height 512 \
  --steps 20 \
  --output-dir /tmp/comfy-out

# 4. Verify
ls -lh /tmp/comfy-out/
```

## Key rules for agents

1. **ComfyUI server must be running** — start with `python main.py` in the ComfyUI directory. Verify with `connect`.
2. **Always `connect` first** — this verifies the server is reachable and gives a clear error if not.
3. **Always pass `-p /path/to/project.json`** to persist connection settings.
4. **`--model` must match exactly** — use `models checkpoints` to see available model filenames. Use the exact filename including extension.
5. **`--output-dir` must be absolute** — use `/tmp/comfy-out` not `./output`.
6. **Generation is async** — the CLI automatically polls the queue and waits for completion.
7. **Image-to-image requires uploading the input** — use `generate img2img --image /path/to/input.png`.

## Command groups

### connect
```bash
sven-integrations-comfyui --json connect [--server http://127.0.0.1:8188]
```
Tests connectivity to the ComfyUI server. Shows server stats on success.

### generate
| Command | Description | Key flags |
|---------|-------------|-----------|
| `generate` (txt2img) | Generate image from text | `--positive TEXT`, `--negative TEXT`, `--model FILENAME`, `--width W`, `--height H`, `--steps N`, `--cfg SCALE`, `--seed N`, `--output-dir PATH` |
| `generate img2img` | Image-to-image generation | `--image PATH`, `--positive TEXT`, `--negative TEXT`, `--model FILENAME`, `--denoise 0.0–1.0`, `--output-dir PATH` |
| `generate upscale` | Upscale an image | `--image PATH`, `--model UPSCALER`, `--scale 4.0`, `--output-dir PATH` |

**Generation parameters:**
```
--width / --height    512, 768, 1024, 1280, 1536 (must be divisible by 8)
--steps               10–50 (20 is good balance of quality/speed)
--cfg                 1.0–20.0 (7.0 default; higher = more prompt adherence)
--seed                Integer (use same seed for reproducible results; -1 for random)
--denoise             0.0–1.0 (img2img strength; 0.75 default = moderate change)
```

### models
| Command | Description |
|---------|-------------|
| `checkpoints` | List Stable Diffusion checkpoint models |
| `loras` | List LoRA models |
| `vaes` | List VAE models |
| `upscalers` | List upscale models |
| `embeddings` | List textual inversion embeddings |
| `node-info NAME` | Get info about a ComfyUI node type |

### queue
| Command | Description | Key flags |
|---------|-------------|-----------|
| `status` | Show current queue state | — |
| `cancel PROMPT_ID` | Cancel a queued prompt | — |
| `history PROMPT_ID` | Get generation history | — |

### workflow
| Command | Description | Key flags |
|---------|-------------|-----------|
| `load PATH` | Load a workflow JSON file into project | — |
| `save NAME PATH` | Save a named workflow to file | — |
| `show NAME` | Display workflow details | — |
| `validate NAME` | Validate workflow JSON | — |
| `list` | List workflows in project | — |

### images
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list PROMPT_ID` | List output images from a generation | — |
| `download PROMPT_ID` | Download all images from a generation | `--output-dir PATH` (required) |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: generate and upscale

```bash
P=/tmp/comfy_session.json

# Connect to ComfyUI
sven-integrations-comfyui --json -p "$P" connect

# Check available models
sven-integrations-comfyui --json -p "$P" models checkpoints
# Example output: ["v1-5-pruned-emaonly.safetensors", "dreamshaper_8.safetensors"]

sven-integrations-comfyui --json -p "$P" models upscalers
# Example output: ["RealESRGAN_x4plus.pth"]

# Create output directory
mkdir -p /tmp/comfy-images

# Generate at base resolution
sven-integrations-comfyui --json -p "$P" generate \
  --positive "portrait of a young woman, professional headshot, studio lighting, 8k" \
  --negative "cartoon, painting, blurry, watermark, text, nsfw" \
  --model "dreamshaper_8.safetensors" \
  --width 512 \
  --height 768 \
  --steps 25 \
  --cfg 7.5 \
  --seed 42 \
  --output-dir /tmp/comfy-images

ls /tmp/comfy-images/
# Note the generated image filename, e.g. "ComfyUI_00001_.png"

# Upscale 4x
sven-integrations-comfyui --json -p "$P" generate upscale \
  --image /tmp/comfy-images/ComfyUI_00001_.png \
  --model "RealESRGAN_x4plus.pth" \
  --scale 4.0 \
  --output-dir /tmp/comfy-images

ls -lh /tmp/comfy-images/
```

## Common pitfalls

- **"Cannot reach ComfyUI"** — the server is not running or on a different port. Start with `python main.py --port 8188` in the ComfyUI directory.
- **Model filename not found** — use `models checkpoints` to see the exact filename including extension. The `--model` value must match exactly.
- **`--output-dir` must be absolute** — `./output` fails; use `/tmp/comfy-out` or another absolute path.
- **Width/height must be divisible by 8** — 512, 768, 1024 are good. 500, 750 will cause an error.
- **Generation takes time** — 20 steps on CPU takes 5–30 minutes; on GPU it takes 5–30 seconds. The CLI polls until complete.
- **Upscalers must be in the `models/upscale_models/` directory** — download them separately if missing.
- **Prompt engineering matters** — use specific descriptive language: "photorealistic, 8k, detailed" for photo-style; "oil painting, artistic, Van Gogh style" for art-style.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)
- `--server URL` — ComfyUI server URL (default: `http://127.0.0.1:8188`)

Base directory: /usr/share/sven/skills/integrations/comfyui
