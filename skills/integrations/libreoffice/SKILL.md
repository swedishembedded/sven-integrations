---
name: integrations/libreoffice
description: |
  Use when asked to create Word documents, spreadsheets, presentations, or convert
  between document formats. Handles Writer (DOCX/ODT), Calc (XLSX/ODS), and
  Impress (PPTX/ODP). Trigger phrases: "create Word document", "create spreadsheet",
  "create presentation", "convert to PDF", "convert document", "LibreOffice",
  "write report", "create table", "add slide".
version: 2.0.0
sven:
  requires_bins: [sven-integrations-libreoffice]
---

# sven-integrations-libreoffice

Stateful CLI for LibreOffice document creation and conversion. Builds Writer,
Calc, and Impress documents as XML and renders them via the `libreoffice --headless`
binary. **LibreOffice must be installed**.

## Minimal working example — create a report

```bash
P=/tmp/libreoffice_project.json

# 1. Create a Writer document
sven-integrations-libreoffice --json -p "$P" document new --type writer --name "My Report"

# 2. Add content
sven-integrations-libreoffice --json -p "$P" writer paragraph "Introduction" --style Heading1
sven-integrations-libreoffice --json -p "$P" writer paragraph "This report covers key findings." --style Normal

# 3. Add a table
sven-integrations-libreoffice --json -p "$P" writer table add --rows 3 --cols 2 --header "Metric|Value"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 1 --col 0 --value "Revenue"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 1 --col 1 --value "$1.2M"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 2 --col 0 --value "Users"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 2 --col 1 --value "45,000"

# 4. Export to PDF
sven-integrations-libreoffice --json -p "$P" export render /tmp/report.pdf --format pdf

# 5. Verify
ls -lh /tmp/report.pdf
```

## Minimal working example — spreadsheet

```bash
P=/tmp/calc_project.json

# 1. Create a Calc spreadsheet
sven-integrations-libreoffice --json -p "$P" document new --type calc --name "Budget"

# 2. Add headers and data
sven-integrations-libreoffice --json -p "$P" calc cell --sheet 0 --row 0 --col 0 --value "Month"
sven-integrations-libreoffice --json -p "$P" calc cell --sheet 0 --row 0 --col 1 --value "Revenue"
sven-integrations-libreoffice --json -p "$P" calc cell --sheet 0 --row 1 --col 0 --value "January"
sven-integrations-libreoffice --json -p "$P" calc cell --sheet 0 --row 1 --col 1 --value "12000"

# 3. Export to XLSX
sven-integrations-libreoffice --json -p "$P" export render /tmp/budget.xlsx --format xlsx
ls -lh /tmp/budget.xlsx
```

## Key rules for agents

1. **Always run `document new` first** with the correct `--type` (writer/calc/impress).
2. **Always pass `-p /path/to/project.json`** to persist state.
3. **`export render` requires LibreOffice installed** — verify with `which libreoffice` or `libreoffice --version`.
4. **Writer paragraphs use styles** — standard styles: `Normal`, `Heading1`, `Heading2`, `Heading3`, `Title`, `Subtitle`, `Body Text`, `List`, `Code`.
5. **Calc cells are 0-indexed** — row 0, col 0 is the first cell (A1 in spreadsheet notation).
6. **Impress slides** — use `impress slide add` to add slides, then `impress slide content` to set title/body.
7. **`convert` works without a project** — for simple format conversion: `sven-integrations-libreoffice --json convert input.docx --to pdf`.

## Command groups

### document
| Command | Description | Key flags |
|---------|-------------|-----------|
| `new` | Create a new document | `--type writer\|calc\|impress`, `--name NAME` |
| `open PATH` | Load an existing document | — |
| `info` | Show document info | — |

### writer (text documents)
| Command | Description | Key flags |
|---------|-------------|-----------|
| `paragraph TEXT` | Add a paragraph | `--style STYLE`, `--align left\|center\|right\|justify` |
| `heading TEXT` | Add a heading | `--level 1\|2\|3` |
| `list` | Add a bullet/numbered list | `--items "item1|item2|item3"`, `--ordered` |
| `table add` | Add a table | `--rows N`, `--cols N`, `--header "H1\|H2\|..."` |
| `table set-cell` | Set table cell value | `--row N`, `--col N`, `--value TEXT` |
| `image` | Insert an image | `--path PATH`, `--width MM`, `--height MM` |
| `page-break` | Insert a page break | — |
| `bookmark` | Add a bookmark | `--name NAME` |
| `style apply` | Apply a paragraph style | `--style STYLE_NAME` |

**Available paragraph styles:**
```
Normal              Default body text
Heading1..Heading4  H1 through H4
Title               Large document title
Subtitle            Subtitle under title
Body Text           Indented body text
List                Bulleted list item
Code                Monospaced code block
Caption             Figure/table caption
```

### calc (spreadsheets)
| Command | Description | Key flags |
|---------|-------------|-----------|
| `cell` | Set a cell value | `--sheet N`, `--row N`, `--col N`, `--value TEXT\|NUMBER`, `--formula "=SUM(A1:A10)"` |
| `sheet add` | Add a new sheet | `--name NAME` |
| `sheet rename` | Rename a sheet | `--index N`, `--name NAME` |
| `sheet list` | List all sheets | — |
| `range set` | Set a range of cells | `--sheet N`, `--start-row N`, `--start-col N`, `--data '[[val,val],[val,val]]'` |
| `style cell` | Style a cell | `--sheet N`, `--row N`, `--col N`, `--bold`, `--italic`, `--bg-color #RRGGBB` |

### impress (presentations)
| Command | Description | Key flags |
|---------|-------------|-----------|
| `slide add` | Add a new slide | `--layout LAYOUT_NAME` |
| `slide content` | Set slide title and body | `--index N`, `--title TEXT`, `--body TEXT` |
| `slide remove` | Remove a slide | `--index N` |
| `slide list` | List all slides | — |
| `slide image` | Insert image on slide | `--index N`, `--path PATH`, `--x X`, `--y Y` |
| `theme apply` | Apply a presentation theme | `--theme THEME_NAME` |

**Slide layouts:** `blank`, `title`, `title_content`, `two_content`, `title_only`, `centered_text`

### styles
| Command | Description | Key flags |
|---------|-------------|-----------|
| `list` | List all document styles | `--type paragraph\|character\|page` |
| `apply` | Apply a named style | `--name NAME`, `--range RANGE` |

### export
| Command | Description | Key flags |
|---------|-------------|-----------|
| `render OUTPUT_PATH` | Export document to file | `--format pdf\|docx\|odt\|xlsx\|ods\|pptx\|odp\|html\|txt` |

### convert (standalone, no project needed)
```bash
sven-integrations-libreoffice --json convert /path/to/input.docx --to pdf
sven-integrations-libreoffice --json convert /path/to/input.xlsx --to pdf --output-dir /tmp
```

### session
| Command | Description |
|---------|-------------|
| `undo` | Undo last operation |
| `history` | Show operation history |
| `list` | List all sessions |
| `delete` | Delete current session |

## Export format matrix

| Source type | Output formats |
|-------------|---------------|
| Writer | `pdf`, `docx`, `odt`, `html`, `txt`, `rtf` |
| Calc | `pdf`, `xlsx`, `ods`, `csv`, `html` |
| Impress | `pdf`, `pptx`, `odp`, `png` (first slide), `html` |

## Complete recipe: quarterly report with table

```bash
P=/tmp/quarterly_report.json

# Create writer document
sven-integrations-libreoffice --json -p "$P" document new --type writer --name "Q3 Report"

# Add title and intro
sven-integrations-libreoffice --json -p "$P" writer paragraph "Q3 2025 Financial Report" --style Title
sven-integrations-libreoffice --json -p "$P" writer paragraph "Executive Summary" --style Heading1
sven-integrations-libreoffice --json -p "$P" writer paragraph "Q3 showed strong growth across all business units with total revenue increasing 18% YoY." --style Normal

# Add a section with table
sven-integrations-libreoffice --json -p "$P" writer paragraph "Key Metrics" --style Heading2
sven-integrations-libreoffice --json -p "$P" writer table add --rows 4 --cols 3 --header "Metric|Q2 2025|Q3 2025"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 1 --col 0 --value "Revenue"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 1 --col 1 --value "$10.2M"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 1 --col 2 --value "$12.0M"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 2 --col 0 --value "Active Users"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 2 --col 1 --value "38,500"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 2 --col 2 --value "45,200"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 3 --col 0 --value "NPS Score"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 3 --col 1 --value "62"
sven-integrations-libreoffice --json -p "$P" writer table set-cell --row 3 --col 2 --value "71"

# Add conclusion
sven-integrations-libreoffice --json -p "$P" writer paragraph "Next Steps" --style Heading1
sven-integrations-libreoffice --json -p "$P" writer list --items "Hire 5 engineers|Expand to 3 new markets|Launch mobile app" --ordered

# Export to PDF
sven-integrations-libreoffice --json -p "$P" export render /tmp/q3_report.pdf --format pdf
ls -lh /tmp/q3_report.pdf
```

## Common pitfalls

- **"LibreOffice not found"** — install LibreOffice and verify `which libreoffice`. On some systems it may be `soffice`.
- **Data injection not supported via `open_and_export`** — the `export render` command exports the document as-is; populate cells/paragraphs via `writer`, `calc`, `impress` commands first.
- **Style names are case-sensitive** — use `Heading1` not `heading1`; use `Normal` not `normal`.
- **Calc cells are 0-indexed** — A1 = row 0, col 0; B3 = row 2, col 1.
- **Impress slide indices are 0-based** — slide 1 is `--index 0`.
- **Large exports take time** — LibreOffice headless startup takes 2–5 seconds. For many documents, this adds up.

## For agents: full flag reference

- `--json` — emit structured JSON output (always use this)
- `-p` / `--project PATH` — load/save project state from JSON file
- `-s` / `--session NAME` — named session (use `-p` for explicitness)

Base directory: /usr/share/sven/skills/integrations/libreoffice
