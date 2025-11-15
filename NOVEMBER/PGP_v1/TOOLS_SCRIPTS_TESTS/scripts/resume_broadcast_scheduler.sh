#!/bin/bash

# Resume Broadcast Scheduler
# This script resumes the daily broadcast scheduler job after maintenance

set -e

PROJECT_ID="telepay-459221"
LOCATION="us-central1"
JOB_NAME="broadcast-scheduler-daily"

echo "▶️  Resuming broadcast scheduler..."
echo "📍 Project: $PROJECT_ID"
echo "🌍 Location: $LOCATION"
echo "📅 Job: $JOB_NAME"
echo ""

# Resume the scheduler job
gcloud scheduler jobs resume $JOB_NAME \
    --location=$LOCATION \
    --project=$PROJECT_ID

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Broadcast scheduler resumed successfully!"
    echo ""
    echo "📝 To verify status:"
    echo "  gcloud scheduler jobs describe $JOB_NAME --location=$LOCATION --project=$PROJECT_ID"
    echo ""
    echo "📊 To check next scheduled run:"
    echo "  gcloud scheduler jobs describe $JOB_NAME --location=$LOCATION --format='value(scheduleTime)' --project=$PROJECT_ID"
    echo ""
else
    echo ""
    echo "❌ Failed to resume broadcast scheduler!"
    exit 1
fi
