---
name: integrations/zoom
description: |
  Use when asked to manage Zoom meetings, list recordings, manage participants,
  or configure Zoom via API. Trigger phrases: "create Zoom meeting", "list Zoom meetings",
  "download Zoom recording", "add Zoom participant", "schedule meeting", "Zoom API".
version: 1.0.0
sven:
  requires_bins: [sven-integrations-zoom]
---

# sven-integrations-zoom

CLI for Zoom meeting, participant, and recording management via the Zoom REST API.
Requires OAuth2 credentials from Zoom Marketplace.

## Setup

```bash
sven-integrations-zoom auth setup --client-id <ID> --client-secret <SECRET>
sven-integrations-zoom auth login
```

## Quick start

```bash
sven-integrations-zoom --json meeting create --topic "Standup" --duration 30
sven-integrations-zoom --json meeting list
sven-integrations-zoom --json meeting get <meeting-id>
sven-integrations-zoom --json recording list --from 2024-01-01 --to 2024-12-31
```

## Command groups

### auth
`setup`, `login`, `login-with-code`, `status`, `logout`

### meeting
`create`, `list`, `get`, `update`, `delete`, `join-url`

### participant
`add-registrant`, `add-batch`, `list-registrants`, `remove-registrant`, `list-past`

### recording
`list`, `get`, `download`, `delete`, `delete-file`

## For agents
- Run `auth setup` once with your Zoom OAuth app credentials
- Run `auth login` to complete the OAuth2 flow
- All commands use `--json` for structured output
- `recording download` saves the file to `--output` path
