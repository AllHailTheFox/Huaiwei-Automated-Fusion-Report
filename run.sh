#!/bin/bash
set -e

cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

python main.py "$@"
