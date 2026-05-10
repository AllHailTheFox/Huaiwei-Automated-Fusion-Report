#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -f .env ]; then
    while IFS='=' read -r key value; do
        if [[ -n $key && ! $key =~ ^# ]]; then
            export "$key=$value"
        fi
    done < .env
fi

PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found. Install Python 3.11+."
    exit 1
fi
"$PYTHON" main.py "$@"
