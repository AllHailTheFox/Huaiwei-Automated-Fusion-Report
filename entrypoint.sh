#!/bin/bash
set -e

if [ -z "$FUSIONSOLAR_USERNAME" ] || [ -z "$FUSIONSOLAR_PASSWORD" ] || [ -z "$EMAIL_PASSWORD" ]; then
    echo "ERROR: Missing required environment variables (FUSIONSOLAR_USERNAME, FUSIONSOLAR_PASSWORD, EMAIL_PASSWORD)"
    exit 1
fi

echo "Starting FusionSolar Email Alert System..."
python /app/extract_and_email.py
