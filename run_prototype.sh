#!/bin/bash
# Run the defrag clicker prototype.
# Works from anywhere — anchors paths to this script's directory.
# If `distrobox` and a `defrag-dev` container are available, runs inside it;
# otherwise falls back to the host python (assumes pygame is installed).
set -e
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if command -v distrobox >/dev/null 2>&1 && distrobox list 2>/dev/null | grep -q '^[[:space:]]*[^|]*|[[:space:]]*defrag-dev'; then
    echo "Entering defrag-dev container..."
    distrobox enter defrag-dev -- bash -c "cd '$ROOT' && python src/main.py"
else
    cd "$ROOT" && python src/main.py
fi
