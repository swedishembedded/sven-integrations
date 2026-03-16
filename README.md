# Sven Integrations

Sven agent tool harnesses that give the sven AI coding agent full control over
desktop applications via structured CLI interfaces.

Each harness provides a CLI tool that sven can invoke to drive a specific
application — creating projects, editing content, exporting results — all via
structured commands with JSON output for reliable machine consumption.

## Integrations

| Tool | Command | Description |
|------|---------|-------------|
| GIMP | `sven-integrations-gimp` | Raster image editing |
| Blender | `sven-integrations-blender` | 3D scene creation and rendering |
| Inkscape | `sven-integrations-inkscape` | Vector graphics editing |
| Audacity | `sven-integrations-audacity` | Audio editing and mixing |
| LibreOffice | `sven-integrations-libreoffice` | Writer, Calc, Impress documents |
| OBS Studio | `sven-integrations-obs-studio` | Streaming and recording |
| Kdenlive | `sven-integrations-kdenlive` | Video editing (MLT) |
| Shotcut | `sven-integrations-shotcut` | Video editing (MLT) |
| Zoom | `sven-integrations-zoom` | Meeting and recording management |
| Draw.io | `sven-integrations-drawio` | Diagram creation |
| Mermaid | `sven-integrations-mermaid` | Diagram as code |
| AnyGen | `sven-integrations-anygen` | AI content generation |
| ComfyUI | `sven-integrations-comfyui` | AI image generation workflows |

## Installation

### Debian/Ubuntu

```bash
sudo dpkg -i sven-integrations_<version>_amd64.deb
```

### From source (any platform)

```bash
pip install ".[all]"
```

### macOS / local install

```bash
make install
```

## How it works

When installed, each CLI tool registers itself under
`/usr/share/sven/skills/integrations/` (or `/usr/local/share/sven/skills/integrations/`
for local installs). Sven discovers these skills automatically at startup and
presents them in the `/sven-integrations/*` namespace.

Each skill is gated on its binary being present on `PATH` via the
`sven.requires_bins` frontmatter field, so missing tools are silently hidden.

## Usage by sven

Sven invokes the tools using the `bash` tool with `--json` for parseable output:

```bash
sven-integrations-gimp --json project new -o /tmp/test.json
sven-integrations-gimp --json layer add-from-file photo.jpg --name Background -p /tmp/test.json
sven-integrations-gimp --json export render output.png -p /tmp/test.json
```

## Development

```bash
make test          # Run all tests
make deb           # Build Debian package
make install       # Install locally to /usr/local
make release/patch # Bump patch version, tag, push
make release/minor # Bump minor version, tag, push
make release/major # Bump major version, tag, push
```

## Release workflow

1. `make release/patch` — bumps version in VERSION and pyproject.toml, commits, tags, pushes
2. Tag push triggers GitHub Actions release workflow
3. Workflow builds .deb packages for x86_64 and arm64, macOS tarball
4. Artifacts published to GitHub Releases
