#!/bin/bash
# Run the test suite.
# Works from anywhere — anchors paths to this script's directory.
# If `distrobox` and a `defrag-dev` container are available, runs inside it;
# otherwise falls back to the host python (assumes pytest + pygame are installed).
set -e
ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if command -v distrobox >/dev/null 2>&1 && distrobox list 2>/dev/null | grep -q '^[[:space:]]*[^|]*|[[:space:]]*defrag-dev'; then
    echo "Entering defrag-dev container to run tests..."
    distrobox enter defrag-dev -- bash -c "cd '$ROOT' && python -m pytest tests/ -q --tb=short"
else
    cd "$ROOT" && python -m pytest tests/ -q --tb=short
fi
