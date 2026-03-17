---
name: integrations/mermaid
description: |
  Use when asked to generate diagrams from text descriptions: flowcharts, sequence
  diagrams, class diagrams, Gantt charts, state diagrams, ER diagrams, pie charts.
  Prefer Mermaid when the diagram is simple and can be described in text.
  Trigger phrases: "create flowchart", "sequence diagram", "class diagram",
  "Gantt chart", "Mermaid diagram", "generate diagram from text".
version: 2.1.0
sven:
  requires_bins: [sven-integrations-mermaid]
---

# sven-integrations-mermaid

Code-first diagram generation using the Mermaid syntax. Renders diagrams using
either the `mmdc` CLI (preferred) or the `mermaid.ink` public API (fallback when
mmdc is not installed). Best for simple diagrams described in text.

## Minimal working example — flowchart

```bash
P=/tmp/mermaid_project.json

# 1. Render a flowchart from inline definition
sven-integrations-mermaid --json -p "$P" render \
  "flowchart TD
    A[Start] --> B{Decision?}
    B -->|Yes| C[Action A]
    B -->|No| D[Action B]
    C --> E[End]
    D --> E" \
  --type flowchart \
  --output /tmp/flowchart.png

# 2. Verify
ls -lh /tmp/flowchart.png
```

## Minimal working example — from file

```bash
cat > /tmp/diagram.mmd << 'EOF'
sequenceDiagram
    participant User
    participant API
    participant DB
    User->>API: POST /login
    API->>DB: SELECT user
    DB-->>API: User found
    API-->>User: JWT token
EOF

sven-integrations-mermaid --json render --file /tmp/diagram.mmd -o /tmp/sequence.png
```

## Key rules for agents

1. **Pass definition as ARGUMENT or use `--file`** — inline: `render "flowchart TD ..."` or from file: `render --file /path/to/diagram.mmd`.
2. **`--output` must be an absolute path** — `/tmp/diagram.png` not `diagram.png`.
3. **Newlines in definitions** — use shell multiline syntax (`\`) or store in a file first.
4. **Renderer selection** — `mmdc` (from `@mermaid-js/mermaid-cli`) is used if found; otherwise `mermaid.ink` API is used (requires internet, limited to 1000-char definitions).
5. **For complex diagrams, use `--file`** — pass the definition via a `.mmd` file to avoid shell quoting issues.
6. **Diagram type must match definition** — `flowchart TD` needs `--type flowchart`; `sequenceDiagram` needs `--type sequence`.

## Mermaid syntax reference

### Flowchart
```
flowchart TD
    A[Box node]
    B(Rounded node)
    C{Diamond/decision}
    D((Circle))
    E>Asymmetric]
    A --> B
    B --> C
    C -->|Yes| D
    C -->|No| E
    A -- Text on line --> B
```

### Sequence Diagram
```
sequenceDiagram
    participant Alice
    participant Bob
    Alice->>Bob: Hello Bob
    Bob-->>Alice: Hi Alice
    Alice->>Bob: How are you?
    note over Alice: Thinking...
    Bob->>Alice: I'm fine!
```

### Class Diagram
```
classDiagram
    class Animal {
        +String name
        +int age
        +speak() void
    }
    class Dog {
        +fetch() void
    }
    Animal <|-- Dog : extends
```

### Gantt Chart
```
gantt
    title Project Timeline
    dateFormat  YYYY-MM-DD
    section Phase 1
    Task A    :done, 2025-01-01, 2025-01-15
    Task B    :active, 2025-01-10, 2025-01-30
    section Phase 2
    Task C    :2025-02-01, 2025-02-28
```

### Entity-Relationship (ER)
```
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE-ITEM : contains
    CUSTOMER {
        string name
        string email
    }
    ORDER {
        int id
        date placed
    }
```

### State Diagram
```
stateDiagram-v2
    [*] --> Idle
    Idle --> Running : start
    Running --> Idle : stop
    Running --> Error : fail
    Error --> Idle : reset
```

### Pie Chart
```
pie title Browser Usage
    "Chrome" : 64.9
    "Safari" : 19.1
    "Firefox" : 3.4
    "Other"  : 12.6
```

## Command groups

### render
| Argument/Flag | Description | Values |
|---------------|-------------|--------|
| `DEFINITION` | Mermaid syntax (positional, optional) | Valid Mermaid text |
| `--file PATH` | Read definition from a .mmd file | Absolute path |
| `--type TYPE` | Diagram type hint | `flowchart`, `sequence`, `gantt`, `class`, `er`, `state`, `pie` |
| `--output PATH` | Output file path (required, absolute) | `/tmp/out.png` |
| `--format FORMAT` | Output format | `png`, `svg`, `pdf` |
| `--theme THEME` | Visual theme | `default`, `dark`, `neutral`, `forest` |

### diagram
| Command | Description | Key flags |
|---------|-------------|-----------|
| `add` | Add named diagram to project | `--title TITLE`, `--type TYPE` |
| `list` | List diagrams in project | — |
| `show` | Show diagram source | `--title TITLE` |
| `remove` | Remove diagram | `--title TITLE` |
| `render` | Render a named diagram to file | `--title TITLE`, `-o PATH`, `--format png\|svg\|pdf` |

### flowchart / sequence / gantt (shortcuts with --output)
Pre-built builders; use `--output` to render directly:
```bash
sven-integrations-mermaid --json flowchart --nodes '[{"id":"A","label":"Start"},{"id":"B","label":"End"}]' --edges '[{"from":"A","to":"B","label":"go"}]' -o /tmp/fc.png
sven-integrations-mermaid --json sequence --participants '["User","API","DB"]' --messages '[{"from":"User","to":"API","text":"login"}]' -o /tmp/seq.png
sven-integrations-mermaid --json gantt --title "Project" --tasks '[{"name":"Task A","start":"2025-01-01","end":"2025-01-15","status":"done"}]' -o /tmp/gantt.png
```
- **flowchart**: `--nodes`, `--edges`, `--direction TB|LR|BT|RL`, `-o PATH`
- **sequence**: `--participants` or `--actors`, `--messages`, `-o PATH`
- **gantt**: `--title`, `--tasks` (flat list) or `--sections` (structured), `-o PATH`

### session
| Command | Description |
|---------|-------------|
| `show` | Show active session |
| `list` | List all sessions |
| `delete` | Delete current session |

## Common pitfalls

- **"definition is empty"** — pass the definition as the first argument (`render "flowchart ..."`) or via `--file /path/to/file.mmd`.
- **Shell quoting** — Mermaid definitions contain spaces, brackets, and newlines. Use `--file` for anything complex:
  ```bash
  cat > /tmp/d.mmd << 'EOF'
  flowchart TD
      A --> B
  EOF
  sven-integrations-mermaid --json render --file /tmp/d.mmd --output /tmp/d.png
  ```
- **`mmdc` not found → API fallback** — if mmdc is not installed, the tool falls back to `mermaid.ink`. Install locally: `npm install -g @mermaid-js/mermaid-cli`.
- **`--output` must be absolute** — `diagram.png` will fail; use `/tmp/diagram.png`.
- **Diagram type mismatch** — `flowchart TD ...` with `--type sequence` may cause rendering issues. Match `--type` to the definition.
- **mermaid.ink API limit** — the public API has a ~2000-character limit. For large diagrams use `mmdc` locally.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/mermaid
