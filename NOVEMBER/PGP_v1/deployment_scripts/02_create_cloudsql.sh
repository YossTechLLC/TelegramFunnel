#!/bin/bash
# Create Cloud SQL PostgreSQL Instance for PayGatePrime v1
# DO NOT EXECUTE - Review and customize before running

set -e

PROJECT_ID="pgp-live"
INSTANCE_NAME="pgp-live-psql"
DATABASE_NAME="pgpdb"
REGION="us-central1"
DATABASE_VERSION="POSTGRES_14"
TIER="db-custom-2-7680"  # 2 vCPUs, 7.5 GB RAM

echo "🗄️  Creating Cloud SQL PostgreSQL Instance"
echo "============================================="
echo ""
echo "📍 Project: $PROJECT_ID"
echo "📍 Instance Name: $INSTANCE_NAME"
echo "📍 Database Name: $DATABASE_NAME"
echo "📍 Region: $REGION"
echo "📍 Database Version: $DATABASE_VERSION"
echo "📍 Tier: $TIER (2 vCPUs, 7.5 GB RAM)"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Create Cloud SQL instance
echo "⏳ Creating Cloud SQL instance (this may take 5-10 minutes)..."
gcloud sql instances create $INSTANCE_NAME \
  --database-version=$DATABASE_VERSION \
  --tier=$TIER \
  --region=$REGION \
  --network=default \
  --database-flags=max_connections=100 \
  --backup \
  --backup-start-time=03:00 \
  --enable-bin-log \
  --retained-backups-count=7 \
  --retained-transaction-log-days=7 \
  --maintenance-window-day=SUN \
  --maintenance-window-hour=4 \
  --maintenance-release-channel=production

echo ""
echo "✅ Cloud SQL instance '$INSTANCE_NAME' created successfully!"
echo ""

# Set root password (IMPORTANT: Change this to a secure password!)
echo "🔐 Setting PostgreSQL root password..."
echo ""
echo "⚠️  IMPORTANT: You must set a secure password for the postgres user!"
echo "⚠️  The following command will prompt you for a password:"
echo ""
echo "   gcloud sql users set-password postgres \\"
echo "     --instance=$INSTANCE_NAME \\"
echo "     --password=YOUR_SECURE_PASSWORD_HERE"
echo ""
echo "OR use this command to set it from an environment variable:"
echo ""
echo "   export POSTGRES_PASSWORD='your-secure-password-here'"
echo "   gcloud sql users set-password postgres \\"
echo "     --instance=$INSTANCE_NAME \\"
echo "     --password=\$POSTGRES_PASSWORD"
echo ""

# Uncomment and modify the following line after setting a secure password:
# read -sp "Enter PostgreSQL postgres password: " POSTGRES_PASSWORD
# gcloud sql users set-password postgres \
#   --instance=$INSTANCE_NAME \
#   --password="$POSTGRES_PASSWORD"

echo ""
echo "⏳ Waiting for instance to be ready..."
sleep 10

# Create database
echo ""
echo "📊 Creating database '$DATABASE_NAME'..."
gcloud sql databases create $DATABASE_NAME \
  --instance=$INSTANCE_NAME

echo ""
echo "✅ Database '$DATABASE_NAME' created successfully!"
echo ""

# Get connection name
CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format="value(connectionName)")
echo "📋 Instance Details:"
echo "   Connection Name: $CONNECTION_NAME"
echo "   Instance Name: $INSTANCE_NAME"
echo "   Database Name: $DATABASE_NAME"
echo "   Region: $REGION"
echo ""

# Display next steps
echo "📝 IMPORTANT NEXT STEPS:"
echo ""
echo "1. Save the connection string for Secret Manager:"
echo "   $CONNECTION_NAME"
echo ""
echo "2. Set the postgres user password (if not done above)"
echo ""
echo "3. Update the following secret in Secret Manager:"
echo "   CLOUD_SQL_CONNECTION_NAME=$CONNECTION_NAME"
echo ""
echo "4. Grant Cloud Run service accounts access:"
echo "   gcloud projects add-iam-policy-binding $PROJECT_ID \\"
echo "     --member='serviceAccount:SERVICE_ACCOUNT_EMAIL' \\"
echo "     --role='roles/cloudsql.client'"
echo ""
echo "⏭️  Next step: Run 03_create_secrets.sh"
