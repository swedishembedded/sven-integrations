---
name: integrations/anygen
description: |
  Use when asked to generate AI-powered documents: PPTX presentations, DOCX reports,
  PDF documents, data tables, or images using the AnyGen API. Requires an API key.
  Trigger phrases: "generate presentation", "AI-generated document", "create PPTX with AI",
  "generate report with AI", "AnyGen", "AI document generation".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-anygen]
---

# sven-integrations-anygen

CLI for AI-powered document generation via the AnyGen API. Submits generation
tasks (PPTX, DOCX, PDF, images, data) and downloads the results. Requires an
API key from AnyGen.

## Prerequisites — configure API key

```bash
# Set your API key (stored in session)
sven-integrations-anygen --json config set api_key YOUR_API_KEY

# Verify
sven-integrations-anygen --json config show
```

## Minimal working example — generate a presentation

```bash
P=/tmp/anygen_project.json

# 1. Configure API key (once)
sven-integrations-anygen --json -p "$P" config set api_key YOUR_API_KEY

# 2. Generate a PPTX presentation
sven-integrations-anygen --json -p "$P" task submit \
  --operation generate_pptx \
  --prompt "Create a 5-slide investor pitch for a SaaS startup in the healthcare space" \
  --output /tmp/investor_pitch.pptx

# 3. Check status (if needed — task submit blocks until complete by default)
sven-integrations-anygen --json -p "$P" task status

# 4. Verify
ls -lh /tmp/investor_pitch.pptx
```

## Key rules for agents

1. **Configure API key before first use** — `config set api_key YOUR_KEY`. This persists to the project file.
2. **Always pass `-p /path/to/project.json`** to persist API key and task history.
3. **`task submit` blocks until complete** by default — it polls the API until the task finishes.
4. **`--output` must be an absolute path** with the correct extension for the operation type.
5. **Operation types match output formats** — `generate_pptx` → `.pptx`, `generate_docx` → `.docx`, `generate_pdf` → `.pdf`.
6. **Check `task list-operations`** to see all supported operation types and their required parameters.
7. **Verify output file** after every generate — check it exists and has non-zero size.

## Command groups

### config
| Command | Description | Key flags |
|---------|-------------|-----------|
| `set api_key KEY` | Store the API key | — |
| `set api_base_url URL` | Override the API base URL | — |
| `show` | Show current config (key is masked) | — |
| `clear` | Remove API key from session | — |

### task
| Command | Description | Key flags |
|---------|-------------|-----------|
| `submit` | Submit a generation task and wait for completion | `--operation TYPE`, `--prompt TEXT`, `--output PATH`, `--style STYLE`, `--params 'key=value'` (repeatable) |
| `status` | Get status of the last/specified task | `--task-id ID` |
| `list` | List recent tasks in the project | — |
| `download TASK_ID` | Download output for a completed task | `--output PATH` |
| `cancel TASK_ID` | Cancel a pending task | — |
| `list-operations` | List all supported operation types | — |

**Supported operation types:**
```
generate_pptx        PowerPoint presentation (.pptx)
generate_docx        Word document (.docx)
generate_pdf         PDF document (.pdf)
generate_image       Image file (.png, .jpg)
generate_data        Structured data (.json, .csv)
summarize_document   Text summary (.txt)
translate_document   Translated document
```

### history
| Command | Description |
|---------|-------------|
| `list` | List all generation history entries |
| `get ENTRY_ID` | Get details of a history entry |
| `clear` | Clear history (keeps API key) |

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: research report + presentation

```bash
P=/tmp/anygen_work.json

# Set API key
sven-integrations-anygen --json -p "$P" config set api_key YOUR_API_KEY

# Generate a DOCX report
sven-integrations-anygen --json -p "$P" task submit \
  --operation generate_docx \
  --prompt "Write a comprehensive market analysis report for the electric vehicle industry in 2025. Include market size, key players, growth trends, and investment opportunities. Use professional business language with section headers." \
  --output /tmp/ev_market_report.docx

ls -lh /tmp/ev_market_report.docx

# Generate a PPTX presentation from the same topic
sven-integrations-anygen --json -p "$P" task submit \
  --operation generate_pptx \
  --prompt "Create an 8-slide executive presentation on the EV market. Slides: Overview, Market Size, Key Players, Growth Drivers, Challenges, Investment Opportunities, Outlook, Q&A. Professional blue corporate theme." \
  --style professional \
  --output /tmp/ev_presentation.pptx

ls -lh /tmp/ev_presentation.pptx

# Check history
sven-integrations-anygen --json -p "$P" history list
```

## Common pitfalls

- **"API key not configured"** — run `config set api_key YOUR_KEY` first. The key persists in the project file.
- **`--output` must be absolute** — use `/tmp/output.pptx` not `output.pptx`.
- **File extension must match operation** — `generate_pptx` must output to `.pptx`; using `.docx` may produce an unusable file.
- **Task submit can take 30–120 seconds** — large documents take longer. The CLI waits automatically.
- **`verify output`** — always run `ls -lh /tmp/output.pptx` to confirm the file was created and has reasonable size (>5KB).
- **Prompt quality matters** — more specific prompts produce better results. Include: topic, purpose, audience, desired sections, tone, length.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/anygen
