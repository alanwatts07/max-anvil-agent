#!/bin/bash
# Railway startup script
# Handles persistent volume for config state

CONFIG_DIR="/app/config"
INITIAL_CONFIG="/app/config_initial"

# If volume is empty (first deploy), seed it with current state
if [ -d "$CONFIG_DIR" ] && [ -z "$(ls -A $CONFIG_DIR 2>/dev/null)" ]; then
    echo "First deploy - seeding config volume with initial state..."
    if [ -d "$INITIAL_CONFIG" ]; then
        cp -r $INITIAL_CONFIG/* $CONFIG_DIR/
        echo "Config seeded successfully"
    fi
elif [ ! -d "$CONFIG_DIR" ]; then
    echo "No volume mounted - using local config"
fi

echo "Starting Max..."

# Check which platform to run
if [ "$ACTIVE_PLATFORM" = "pinch" ]; then
    echo "Platform: PINCH SOCIAL"
    python scripts/agents/pinch/brain.py
else
    echo "Platform: MOLTX"
    python scripts/max_brain.py
fi
