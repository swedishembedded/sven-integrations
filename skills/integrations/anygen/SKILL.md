---
name: integrations/anygen
description: |
  Use when asked to generate presentations, documents, or other content using the
  AnyGen AI generation API. Trigger phrases: "generate presentation", "AI presentation",
  "generate document with AI", "create slides automatically", "AnyGen", "generate report".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-anygen]
---

# sven-integrations-anygen

CLI for the AnyGen AI content generation API. Creates presentations (PPTX),
documents (DOCX), PDFs, images, and more from natural language prompts.

## Setup

```bash
sven-integrations-anygen config set api_key sk-your-api-key
```

## Quick start

```bash
# Full workflow: create, poll until done, download
sven-integrations-anygen --json task run --operation slide --prompt "AI trends 2025" --output ./

# Step by step
sven-integrations-anygen --json task create --operation slide --prompt "AI trends"
sven-integrations-anygen --json task status <task-id>
sven-integrations-anygen --json task download <task-id> --output ./output.pptx

# Multi-turn preparation
sven-integrations-anygen --json task prepare --operation doc --prompt "Technical report"
```

## Command groups

### task
`run` (full workflow), `create`, `status`, `download`, `list`, `prepare`

### file
`verify` (checks PPTX/DOCX/PDF/PNG/SVG integrity)

### config
`set`, `get`, `list`

### session
`undo`, `redo`, `history`

## Operations
`slide` (PPTX), `doc` (DOCX), `pdf`, `image` (PNG/SVG), `data` (JSON/XML)

## For agents
- `task run` is the simplest: one command handles create → poll → download
- `task run` accepts `--output` as a directory path
- `config set api_key <key>` must be run before any task operations
- All outputs are verified automatically with `file verify`
