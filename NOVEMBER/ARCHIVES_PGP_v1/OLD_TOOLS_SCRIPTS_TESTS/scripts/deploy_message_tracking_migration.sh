#!/bin/bash
# Deploy message tracking migration to telepaypsql
# Date: 2025-01-14
# Related: LIVETIME_BROADCAST_ONLY_CHECKLIST.md Phase 1

set -e  # Exit on error

echo "🚀 Deploying message tracking migration to telepaypsql..."

# Set database connection info
DB_HOST="/cloudsql/pgp-live:us-central1:telepaypsql"
DB_NAME="client_table"
DB_USER="postgres"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if migration file exists
if [ ! -f "$SCRIPT_DIR/add_message_tracking_columns.sql" ]; then
    echo "❌ Migration file not found: add_message_tracking_columns.sql"
    exit 1
fi

echo "📄 Migration file found: add_message_tracking_columns.sql"

# Execute migration
echo "🔧 Executing migration..."
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -f "$SCRIPT_DIR/add_message_tracking_columns.sql"

if [ $? -eq 0 ]; then
    echo "✅ Migration deployed successfully"
else
    echo "❌ Migration failed"
    exit 1
fi

# Verify columns exist
echo "🔍 Verifying new columns..."
VERIFICATION=$(PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='broadcast_manager' AND column_name LIKE 'last_%_message_%';" | wc -l)

if [ "$VERIFICATION" -eq 4 ]; then
    echo "✅ All 4 columns verified successfully"
    echo ""
    echo "📊 Column details:"
    PGPASSWORD="$DB_PASSWORD" psql \
      -h "$DB_HOST" \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -c "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='broadcast_manager' AND column_name LIKE 'last_%_message_%' ORDER BY column_name;"
else
    echo "⚠️ Expected 4 columns but found $VERIFICATION"
    exit 1
fi

echo ""
echo "✅ Migration deployment complete!"
