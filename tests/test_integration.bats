#!/usr/bin/env bats
# Integration smoke tests for sven-integrations CLI tools.
#
# Tests that each installed binary:
# - Exists and is executable
# - Responds to --help
# - Returns valid JSON with --json flag
# - Has a working --version or version subcommand
#
# Prerequisites: sven-integrations installed (pip install -e .)
# Run: bats tests/test_integration.bats

TOOLS=(
    gimp
    blender
    inkscape
    audacity
    libreoffice
    obs-studio
    kdenlive
    shotcut
    zoom
    drawio
    mermaid
    anygen
    comfyui
)

# ── Helper: check if a binary is on PATH ──────────────────────────────────

@test "all sven-integrations binaries are on PATH" {
    for tool in "${TOOLS[@]}"; do
        run command -v "sven-integrations-${tool}"
        [ "$status" -eq 0 ] || {
            echo "MISSING: sven-integrations-${tool} not found on PATH"
            false
        }
    done
}

# ── --help for each binary ────────────────────────────────────────────────

@test "sven-integrations-gimp --help exits 0" {
    run sven-integrations-gimp --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"project"* ]] || [[ "$output" == *"Usage"* ]]
}

@test "sven-integrations-blender --help exits 0" {
    run sven-integrations-blender --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-inkscape --help exits 0" {
    run sven-integrations-inkscape --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-audacity --help exits 0" {
    run sven-integrations-audacity --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-libreoffice --help exits 0" {
    run sven-integrations-libreoffice --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-obs-studio --help exits 0" {
    run sven-integrations-obs-studio --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-kdenlive --help exits 0" {
    run sven-integrations-kdenlive --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-shotcut --help exits 0" {
    run sven-integrations-shotcut --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-zoom --help exits 0" {
    run sven-integrations-zoom --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-drawio --help exits 0" {
    run sven-integrations-drawio --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-mermaid --help exits 0" {
    run sven-integrations-mermaid --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-anygen --help exits 0" {
    run sven-integrations-anygen --help
    [ "$status" -eq 0 ]
}

@test "sven-integrations-comfyui --help exits 0" {
    run sven-integrations-comfyui --help
    [ "$status" -eq 0 ]
}

# ── JSON output ────────────────────────────────────────────────────────────

@test "sven-integrations-zoom --json auth status creates valid JSON" {
    run sven-integrations-zoom --json auth status
    [ "$status" -eq 0 ]
    echo "$output" | python3 -c "import sys,json; json.load(sys.stdin)"
}

@test "sven-integrations-gimp --json project new creates valid JSON project" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-gimp --json project new -o "$tmpfile"
    [ "$status" -eq 0 ]
    # Validate JSON by piping to python
    echo "$output" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null || \
        python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

@test "sven-integrations-blender --json scene new creates valid JSON" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-blender --json scene new -o "$tmpfile"
    [ "$status" -eq 0 ]
    python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

@test "sven-integrations-audacity --json project new creates valid JSON" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-audacity --json project new -o "$tmpfile"
    [ "$status" -eq 0 ]
    python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

@test "sven-integrations-audacity connect exits 1 when pipe does not exist" {
    run sven-integrations-audacity --json connect
    [ "$status" -eq 1 ]
    [[ "$output" == *"pipe not found"* ]] || [[ "$output" == *"Error:"* ]]
}

@test "sven-integrations-libreoffice --json document new (writer) creates valid JSON" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-libreoffice --json document new -o "$tmpfile" --type writer
    [ "$status" -eq 0 ]
    python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

@test "sven-integrations-obs-studio --json project new creates valid JSON" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-obs-studio --json project new -o "$tmpfile"
    [ "$status" -eq 0 ]
    python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

@test "sven-integrations-kdenlive --json project new creates valid JSON" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-kdenlive --json project new -o "$tmpfile"
    [ "$status" -eq 0 ]
    python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

@test "sven-integrations-drawio --json project new creates valid drawio file" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.drawio)"
    run sven-integrations-drawio --json project new -o "$tmpfile"
    [ "$status" -eq 0 ]
    [ -f "$tmpfile" ]
    rm -f "$tmpfile"
}

@test "sven-integrations-mermaid --json project new creates valid JSON" {
    local tmpfile
    tmpfile="$(mktemp /tmp/sven-integrations-test-XXXXXX.json)"
    run sven-integrations-mermaid --json project new -o "$tmpfile"
    [ "$status" -eq 0 ]
    python3 -c "import json; json.load(open('$tmpfile'))"
    rm -f "$tmpfile"
}

# ── Skills are installed ───────────────────────────────────────────────────

@test "sven-integrations skills are installed in system path" {
    # Check at least one of the possible install locations
    local found=false
    for dir in \
        /usr/share/sven/skills/integrations \
        /usr/local/share/sven/skills/integrations \
        "$(python3 -c "import sven_integrations, os; print(os.path.dirname(sven_integrations.__file__))" 2>/dev/null)/../../../share/sven/skills/integrations"; do
        if [ -d "$dir" ] && [ -f "$dir/SKILL.md" ]; then
            found=true
            break
        fi
    done

    if [ "$found" = "false" ]; then
        # Also check if running from source (skills/ directory exists)
        if [ -f "$(dirname "$BATS_TEST_FILENAME")/../skills/integrations/SKILL.md" ]; then
            found=true
        fi
    fi

    [ "$found" = "true" ] || {
        echo "Skills not found in any expected location"
        false
    }
}

# ── No forbidden project references ───────────────────────────────────────

@test "installed binaries contain no forbidden project references" {
    skip "Source-level check done in test_skills.py"
}
