#!/bin/bash

# Pause Broadcast Scheduler
# This script pauses the daily broadcast scheduler job for maintenance

set -e

PROJECT_ID="telepay-459221"
LOCATION="us-central1"
JOB_NAME="broadcast-scheduler-daily"

echo "⏸️  Pausing broadcast scheduler..."
echo "📍 Project: $PROJECT_ID"
echo "🌍 Location: $LOCATION"
echo "📅 Job: $JOB_NAME"
echo ""

# Pause the scheduler job
gcloud scheduler jobs pause $JOB_NAME \
    --location=$LOCATION \
    --project=$PROJECT_ID

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Broadcast scheduler paused successfully!"
    echo ""
    echo "📝 To verify status:"
    echo "  gcloud scheduler jobs describe $JOB_NAME --location=$LOCATION --project=$PROJECT_ID"
    echo ""
    echo "▶️  To resume broadcasts, run:"
    echo "  ./resume_broadcast_scheduler.sh"
    echo ""
else
    echo ""
    echo "❌ Failed to pause broadcast scheduler!"
    exit 1
fi
