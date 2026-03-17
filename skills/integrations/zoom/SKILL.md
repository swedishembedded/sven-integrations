---
name: integrations/zoom
description: |
  Use when asked to manage Zoom meetings: create, list, or delete meetings, manage
  participants, list or download recordings, or authenticate with Zoom. Requires
  Zoom OAuth2 credentials. Trigger phrases: "create Zoom meeting", "schedule meeting",
  "Zoom recording", "list meetings", "add participant", "manage Zoom".
version: 2.1.0
sven:
  requires_bins: [sven-integrations-zoom]
---

# sven-integrations-zoom

CLI for the Zoom REST API v2. Manages meetings, participants, and recordings using
OAuth2 authentication. Requires a Zoom OAuth app with Server-to-Server or User
OAuth credentials.

## Prerequisites — Zoom OAuth2 setup

1. Create a Zoom OAuth app at [marketplace.zoom.us](https://marketplace.zoom.us/develop/create)
2. Choose "Server-to-Server OAuth" (for automation) or "User OAuth"
3. Note your **Client ID** and **Client Secret**
4. For Server-to-Server: also note your **Account ID**
5. Authenticate: `sven-integrations-zoom --json auth login --client-id ... --client-secret ...`

## Minimal working example — create and list a meeting

```bash
P=/tmp/zoom_project.json

# 1. Authenticate (uses ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET env vars or flags)
export ZOOM_CLIENT_ID="your_client_id"
export ZOOM_CLIENT_SECRET="your_client_secret"
sven-integrations-zoom --json -p "$P" auth login --client-id "$ZOOM_CLIENT_ID" --client-secret "$ZOOM_CLIENT_SECRET"

# 2. Create a scheduled meeting
sven-integrations-zoom --json -p "$P" meeting create \
  --topic "Weekly Team Sync" \
  --start-time "2025-03-25T14:00:00Z" \
  --duration 60 \
  --timezone "UTC" \
  --passcode "secret123"

# 3. List all meetings
sven-integrations-zoom --json -p "$P" meeting list

# 4. Get meeting details (use meeting ID from create output)
sven-integrations-zoom --json -p "$P" meeting get --id <MEETING_ID>
```

## Key rules for agents

1. **Always authenticate first** — run `auth login` before any meeting/recording commands.
2. **Always pass `-p /path/to/project.json`** to persist the OAuth token across commands.
3. **Meeting IDs are numeric** — capture the `id` field from `meeting create` or `meeting list` output.
4. **Timestamps must be ISO 8601 format** — `2025-03-25T14:00:00Z` or with timezone offset `2025-03-25T14:00:00-05:00`.
5. **API credentials can be set via environment variables** — `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET`, `ZOOM_REDIRECT_URI`.
6. **Token expires** — if commands return auth errors, re-run `auth login`.
7. **`recording download --output`** must be an absolute path.

## Command groups

### auth
| Command | Description | Key flags |
|---------|-------------|-----------|
| `login` | Authenticate with Zoom OAuth | `--client-id ID`, `--client-secret SECRET`, `--redirect-uri URL`, `--code CODE` |
| `status` | Check authentication status | — |
| `logout` | Clear stored credentials | — |

**Environment variables (alternative to flags):**
```
ZOOM_CLIENT_ID        OAuth app Client ID
ZOOM_CLIENT_SECRET    OAuth app Client Secret
ZOOM_REDIRECT_URI     OAuth redirect URI (default: http://localhost:4199/callback)
```

### meeting
| Command | Description | Key flags |
|---------|-------------|-----------|
| `create` | Create a new meeting | `--topic TEXT`, `--start-time ISO8601`, `--duration MINUTES`, `--timezone TZ`, `--passcode PASS`, `--agenda TEXT`, `--type instant\|scheduled\|recurring\|recurring_fixed` |
| `list` | List meetings for the user | `--type scheduled\|live\|past\|pastOne` |
| `get` | Get meeting details | `--id MEETING_ID` |
| `update` | Update meeting properties | `--id MEETING_ID`, `--topic TEXT`, `--start-time ISO8601`, `--duration`, `--timezone`, `--passcode`, `--agenda` |
| `delete` | Delete a meeting | `--id MEETING_ID` |
| `url` | Return join or start URL | `--id MEETING_ID`, `--passcode PASS`, `--host` |

**Meeting types (create):**
```
instant         Instant meeting (type 1)
scheduled       Scheduled meeting (type 2, default)
recurring       Recurring meeting, no fixed time (type 3)
recurring_fixed Recurring meeting with fixed end (type 8)
```

### participant
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add MEETING_ID` | Register a participant | `--email EMAIL`, `--first-name NAME`, `--last-name NAME` |
| `list MEETING_ID` | List registrants | `--status pending\|approved\|denied` |
| `remove MEETING_ID REGISTRANT_ID` | Remove a registrant | — |
| `batch MEETING_ID CSV_FILE` | Add multiple participants from CSV | — |
| `attended MEETING_ID` | List participants who attended | — |

**Batch CSV format:**
```csv
email,first_name,last_name
alice@example.com,Alice,Smith
bob@example.com,Bob,Jones
```

### recording
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List recordings | `--meeting-id ID` OR `--from YYYY-MM-DD` and `--to YYYY-MM-DD` |
| `download` | Download a recording file | `--meeting-id ID`, `--output PATH` (absolute) |

### session
| Command | Description |
|---------|-------------|
| `show` | Show active session data |
| `list` | List all sessions |
| `delete` | Delete current session |

## Complete recipe: schedule a meeting series

```bash
P=/tmp/zoom_meetings.json

# Authenticate (using env vars)
export ZOOM_CLIENT_ID="xxxxx"
export ZOOM_CLIENT_SECRET="yyyyy"
sven-integrations-zoom --json -p "$P" auth login

# Create an instant meeting
sven-integrations-zoom --json -p "$P" meeting create \
  --topic "Product Demo" \
  --type instant

# Create a scheduled meeting
sven-integrations-zoom --json -p "$P" meeting create \
  --topic "Sprint Review" \
  --start-time "2025-04-01T15:00:00Z" \
  --duration 90 \
  --timezone "Europe/London" \
  --passcode "sprint123" \
  --agenda "Review sprint velocity, demo new features, retrospective"

# Note the meeting ID from the output JSON
MEETING_ID="<id from output>"

# Add participants
sven-integrations-zoom --json -p "$P" participant add "$MEETING_ID" \
  --email "alice@company.com" \
  --first-name "Alice" \
  --last-name "Smith"

sven-integrations-zoom --json -p "$P" participant add "$MEETING_ID" \
  --email "bob@company.com" \
  --first-name "Bob" \
  --last-name "Jones"

# Verify participants
sven-integrations-zoom --json -p "$P" participant list "$MEETING_ID"

# List all upcoming meetings
sven-integrations-zoom --json -p "$P" meeting list --type scheduled

# After the meeting, list and download recordings
sven-integrations-zoom --json -p "$P" recording list --meeting-id "$MEETING_ID"
sven-integrations-zoom --json -p "$P" recording download --meeting-id "$MEETING_ID" --output /tmp/sprint_review.mp4
ls -lh /tmp/sprint_review.mp4
```

## Common pitfalls

- **"Not authenticated"** — run `auth login` before any commands. Token is stored in the project file.
- **Token expired** — if you get auth errors, re-run `auth login`. Zoom tokens typically last 1 hour.
- **Meeting ID format** — Zoom meeting IDs are 10–11 digit numbers. Copy exactly from JSON output.
- **ISO 8601 timestamps** — use `2025-03-25T14:00:00Z` format. Omitting timezone causes API errors.
- **`recording download` path must be absolute** — use `/tmp/recording.mp4` not `recording.mp4`.
- **Recordings available after delay** — recordings are not immediately available after a meeting ends; they may take 5–30 minutes to process.
- **Rate limiting** — Zoom API has rate limits (100–500 requests/minute). The backend retries on 429 errors automatically.

## Zoom API error codes reference

| Code | Meaning |
|------|---------|
| 124 | Invalid access token — re-authenticate |
| 200 | Meeting not found |
| 300 | Meeting too old to edit |
| 3000 | Meeting host not found |
| 3001 | Meeting does not exist |
| 404 | Not found |
| 429 | Rate limit exceeded (automatically retried) |

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/zoom
