#!/bin/bash
# Start the MoltX Agent

# Activate virtual environment
source venv/bin/activate

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Check for required env vars
if [ -z "$TWITTER_API_KEY" ]; then
    echo "Warning: TWITTER_API_KEY not set"
fi

if [ -z "$BANKR_API_KEY" ]; then
    echo "Warning: BANKR_API_KEY not set"
fi

# Parse arguments
DRY_RUN=""
INTERVAL="60"

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "Starting MoltX Agent..."
echo "  Dry run: ${DRY_RUN:-false}"
echo "  Interval: ${INTERVAL}s"
echo ""

python scripts/agent_cycle.py $DRY_RUN --interval "$INTERVAL"
