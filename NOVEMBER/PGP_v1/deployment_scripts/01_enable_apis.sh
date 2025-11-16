#!/bin/bash
# Enable Required GCP APIs for PayGatePrime v1
# DO NOT EXECUTE - Review and customize before running

set -e

PROJECT_ID="pgp-live"
echo "🔧 Enabling required GCP APIs for project: $PROJECT_ID"
echo "=================================================="

# Set the project
echo ""
echo "📍 Setting active project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# Enable all required APIs
echo ""
echo "🔌 Enabling Cloud Run API..."
gcloud services enable run.googleapis.com

echo ""
echo "🔌 Enabling Cloud SQL Admin API..."
gcloud services enable sqladmin.googleapis.com

echo ""
echo "🔌 Enabling Cloud SQL API..."
gcloud services enable sql-component.googleapis.com

echo ""
echo "🔌 Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com

echo ""
echo "🔌 Enabling Cloud Tasks API..."
gcloud services enable cloudtasks.googleapis.com

echo ""
echo "🔌 Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com

echo ""
echo "🔌 Enabling Cloud Build API..."
gcloud services enable cloudbuild.googleapis.com

echo ""
echo "🔌 Enabling Artifact Registry API..."
gcloud services enable artifactregistry.googleapis.com

echo ""
echo "🔌 Enabling Compute Engine API (for networking)..."
gcloud services enable compute.googleapis.com

echo ""
echo "🔌 Enabling Cloud Resource Manager API..."
gcloud services enable cloudresourcemanager.googleapis.com

echo ""
echo "🔌 Enabling IAM API..."
gcloud services enable iam.googleapis.com

echo ""
echo "🔌 Enabling Cloud Logging API..."
gcloud services enable logging.googleapis.com

echo ""
echo "🔌 Enabling Cloud Monitoring API..."
gcloud services enable monitoring.googleapis.com

echo ""
echo "✅ All required APIs enabled successfully!"
echo ""
echo "📋 Enabled APIs:"
echo "   - Cloud Run (run.googleapis.com)"
echo "   - Cloud SQL Admin (sqladmin.googleapis.com)"
echo "   - Cloud SQL (sql-component.googleapis.com)"
echo "   - Secret Manager (secretmanager.googleapis.com)"
echo "   - Cloud Tasks (cloudtasks.googleapis.com)"
echo "   - Cloud Scheduler (cloudscheduler.googleapis.com)"
echo "   - Cloud Build (cloudbuild.googleapis.com)"
echo "   - Artifact Registry (artifactregistry.googleapis.com)"
echo "   - Compute Engine (compute.googleapis.com)"
echo "   - Cloud Resource Manager (cloudresourcemanager.googleapis.com)"
echo "   - IAM (iam.googleapis.com)"
echo "   - Cloud Logging (logging.googleapis.com)"
echo "   - Cloud Monitoring (monitoring.googleapis.com)"
echo ""
echo "⏭️  Next step: Run 02_create_cloudsql.sh"
