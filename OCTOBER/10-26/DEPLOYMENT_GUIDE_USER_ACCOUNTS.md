# Deployment Guide - User Account Management System

**Created:** 2025-10-28
**Version:** 1.0
**Target Environment:** Google Cloud Run + Cloud SQL

---

## Overview

This guide provides step-by-step instructions for deploying the User Account Management System to Google Cloud Platform.

**Services to Modify:**
1. GCRegister10-26 - Add user management functionality (re-deploy)

**No New Services** - This is a modification to existing GCRegister service

**Infrastructure:**
- No new Cloud Tasks queues
- No new Cloud Scheduler jobs
- Minimal new Secret Manager entries (likely already exist)

---

## Prerequisites

- [ ] Database migration completed (`DB_MIGRATION_USER_ACCOUNTS.md`)
- [ ] Code modifications completed (`GCREGISTER_USER_MANAGEMENT_GUIDE.md`)
- [ ] Google Cloud SDK installed and configured
- [ ] Project ID: `telepay-459221`
- [ ] Region: `us-central1`
- [ ] Permissions: Cloud Run Admin, Secret Manager Admin

---

## Step 1: Verify Database Migration

Before deploying code changes, ensure database migration is complete:

```bash
# Connect to Cloud SQL
gcloud sql connect YOUR_INSTANCE_NAME --user=USERNAME --database=DATABASE_NAME

# Run verification queries from DB_MIGRATION_USER_ACCOUNTS.md
```

**Verify:**
```sql
-- Check registered_users table exists
SELECT COUNT(*) FROM registered_users;
-- Expected: 1 (legacy_system user)

-- Check main_clients_database has client_id column
SELECT column_name FROM information_schema.columns
WHERE table_name = 'main_clients_database' AND column_name = 'client_id';
-- Expected: 1 row

-- Check all existing channels linked to legacy user
SELECT COUNT(*) FROM main_clients_database
WHERE client_id = '00000000-0000-0000-0000-000000000000';
-- Expected: All existing channels
```

---

## Step 2: Verify Secret Manager Secrets

Most secrets should already exist from previous deployments. Verify:

```bash
# Check required secrets exist
gcloud secrets list | grep -E "(SECRET_KEY|DATABASE|CLOUD_SQL)"
```

**Required Secrets:**
- `SECRET_KEY` - Flask session secret (likely already exists)
- `CLOUD_SQL_CONNECTION_NAME`
- `DATABASE_NAME_SECRET`
- `DATABASE_USER_SECRET`
- `DATABASE_PASSWORD_SECRET`

**If SECRET_KEY doesn't exist**, create it:

```bash
# Generate random secret key
python3 -c "import secrets; print(secrets.token_hex(32))"

# Create secret
gcloud secrets create SECRET_KEY --data-file=- <<EOF
YOUR_GENERATED_SECRET_KEY_HERE
EOF

# Verify
gcloud secrets versions access latest --secret="SECRET_KEY"
```

---

## Step 3: Apply Code Modifications to GCRegister10-26

Follow `GCREGISTER_USER_MANAGEMENT_GUIDE.md` to modify files:

### 3.1 Update requirements.txt

```bash
cd OCTOBER/10-26/GCRegister10-26

# Add Flask-Login==0.6.3 to requirements.txt
echo "Flask-Login==0.6.3" >> requirements.txt

# Verify
cat requirements.txt | grep Flask-Login
```

### 3.2 Modify forms.py

Add `LoginForm` and `SignupForm` classes as documented in the guide.

**File:** `forms.py`
- Add imports: `PasswordField`, `Email`, `EqualTo`, `ValidationError`
- Add `LoginForm` class
- Add `SignupForm` class with password validation

### 3.3 Modify database_manager.py

Add user management functions:
- `get_user_by_username()`
- `get_user_by_id()`
- `get_user_by_email()`
- `create_user()`
- `update_last_login()`
- `get_channels_by_client()`
- `count_channels_by_client()`
- `get_channel_by_id()`
- `update_channel()`
- `delete_channel()`

### 3.4 Modify config_manager.py

Add `SECRET_KEY` secret fetch:

```python
# Add after existing secret fetches
'secret_key': self.access_secret('SECRET_KEY'),
```

### 3.5 Modify tpr10-26.py

- Add Flask-Login initialization
- Add User class (UserMixin)
- Add @login_manager.user_loader
- Add routes: `/`, `/signup`, `/login`, `/logout`
- Add `/channels` dashboard route
- Add `/channels/add` route (modify existing `/register`)
- Add `/channels/<id>/edit` route
- Add authorization checks

### 3.6 Create New Templates

Create these template files:

**signup.html** - User registration form
**login.html** - User login form
**dashboard.html** - Multi-channel dashboard
**edit_channel.html** - Edit existing channel
**base_authenticated.html** - Base template with navigation for logged-in users

### 3.7 Test Locally (Optional)

```bash
# Set environment variables for local testing
export CLOUD_SQL_CONNECTION_NAME="..."
export DATABASE_NAME_SECRET="..."
export DATABASE_USER_SECRET="..."
export DATABASE_PASSWORD_SECRET="..."
export SECRET_KEY="test-secret-key-local"

# Run locally
python tpr10-26.py

# Test in browser
# http://localhost:8080
```

---

## Step 4: Deploy Modified GCRegister10-26

### 4.1 Build Docker Image

```bash
cd OCTOBER/10-26/GCRegister10-26

# Build container
gcloud builds submit --tag gcr.io/telepay-459221/gcregister-10-26

# Verify build succeeded
gcloud container images list | grep gcregister-10-26
```

### 4.2 Deploy to Cloud Run

```bash
# Deploy with updated code
gcloud run deploy gcregister-10-26 \
  --image gcr.io/telepay-459221/gcregister-10-26 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "SECRET_KEY=projects/telepay-459221/secrets/SECRET_KEY/versions/latest,\
CLOUD_SQL_CONNECTION_NAME=projects/telepay-459221/secrets/CLOUD_SQL_CONNECTION_NAME/versions/latest,\
DATABASE_NAME_SECRET=projects/telepay-459221/secrets/DATABASE_NAME_SECRET/versions/latest,\
DATABASE_USER_SECRET=projects/telepay-459221/secrets/DATABASE_USER_SECRET/versions/latest,\
DATABASE_PASSWORD_SECRET=projects/telepay-459221/secrets/DATABASE_PASSWORD_SECRET/versions/latest"
```

**Note:** Add any other existing environment variables that GCRegister10-26 requires (e.g., API keys, queue URLs, etc.)

### 4.3 Verify Deployment

```bash
# Get service URL
export GCREGISTER_URL=$(gcloud run services describe gcregister-10-26 \
  --region us-central1 \
  --format='value(status.url)')

echo "GCRegister URL: $GCREGISTER_URL"

# Test health endpoint (if exists)
curl $GCREGISTER_URL/health

# Test landing page
curl $GCREGISTER_URL/
# Should redirect to /login or show landing page
```

---

## Step 5: Update Custom Domain (Optional)

If using custom domain (www.paygateprime.com):

```bash
# Verify domain mapping exists
gcloud run domain-mappings list --region us-central1

# If needed, update mapping
gcloud run domain-mappings create \
  --service gcregister-10-26 \
  --domain www.paygateprime.com \
  --region us-central1
```

---

## Step 6: Test User Account Functionality

### 6.1 Test Signup Flow

```bash
# Visit signup page
curl -L $GCREGISTER_URL/signup
# Should return signup form HTML

# Or test in browser:
# https://www.paygateprime.com/signup
```

**Manual Browser Test:**
1. Navigate to `/signup`
2. Fill form:
   - Username: `testuser123`
   - Email: `test@example.com`
   - Password: `TestPass123!`
   - Confirm Password: `TestPass123!`
3. Submit form
4. Should redirect to `/login` or `/dashboard`
5. Verify user created in database:

```sql
SELECT user_id, username, email, is_active, created_at
FROM registered_users
WHERE username = 'testuser123';
```

### 6.2 Test Login Flow

**Manual Browser Test:**
1. Navigate to `/login`
2. Enter credentials:
   - Username: `testuser123`
   - Password: `TestPass123!`
3. Submit form
4. Should redirect to `/channels` dashboard
5. Check session cookie set

### 6.3 Test Dashboard

**Manual Browser Test:**
1. Login as `testuser123`
2. Navigate to `/channels`
3. Should see:
   - "Your Channels (0/10)" heading
   - "No channels yet" empty state
   - "Add New Channel" button

### 6.4 Test Add Channel Flow

**Manual Browser Test:**
1. From dashboard, click "Add New Channel"
2. Fill channel registration form
3. Submit
4. Should redirect to `/channels`
5. New channel should appear in list
6. Verify in database:

```sql
SELECT open_channel_id, open_channel_title, client_id, created_by
FROM main_clients_database
WHERE client_id = (SELECT user_id FROM registered_users WHERE username = 'testuser123');
```

**Expected:** `client_id` should match `testuser123`'s UUID

### 6.5 Test Edit Channel Flow

**Manual Browser Test:**
1. From dashboard, click "Edit" on a channel
2. Modify a field (e.g., tier price)
3. Submit
4. Should redirect to `/channels` with success message
5. Verify changes in database:

```sql
SELECT sub_1_price, updated_at
FROM main_clients_database
WHERE open_channel_id = 'YOUR_CHANNEL_ID';
```

### 6.6 Test Authorization

**Manual Browser Test:**
1. Login as `testuser123`
2. Note a channel ID owned by this user
3. Logout
4. Create second user `testuser456`
5. Login as `testuser456`
6. Try to access `/channels/TESTUSER123_CHANNEL_ID/edit`
7. Should return 403 Forbidden or redirect

### 6.7 Test 10-Channel Limit

**Manual Browser Test:**
1. Login as test user
2. Create 10 channels via `/channels/add`
3. Try to create 11th channel
4. Should show error: "Maximum 10 channels per account"
5. Verify in database:

```sql
SELECT COUNT(*) as channel_count
FROM main_clients_database
WHERE client_id = (SELECT user_id FROM registered_users WHERE username = 'testuser123');
-- Expected: 10
```

### 6.8 Test Logout

**Manual Browser Test:**
1. Login as test user
2. Navigate to `/logout`
3. Should clear session and redirect to `/login`
4. Try to access `/channels` without logging in
5. Should redirect to `/login`

---

## Step 7: Monitor and Troubleshoot

### 7.1 Check Cloud Run Logs

```bash
# Stream logs
gcloud run services logs tail gcregister-10-26 --region us-central1

# Or view in console
# https://console.cloud.google.com/run/detail/us-central1/gcregister-10-26/logs
```

**Look for:**
- =€ Service startup logs
-  Successful user signups
-  Successful logins
- L Failed login attempts
- L Authorization errors (403)
- =¾ Database connection logs

### 7.2 Common Issues and Fixes

#### Issue 1: "SECRET_KEY not found"

**Cause:** SECRET_KEY not in Secret Manager

**Fix:**
```bash
# Create secret
gcloud secrets create SECRET_KEY --data-file=- <<EOF
$(python3 -c "import secrets; print(secrets.token_hex(32))")
EOF

# Re-deploy service
gcloud run services update gcregister-10-26 --region us-central1
```

#### Issue 2: "No module named 'flask_login'"

**Cause:** requirements.txt not updated or Docker cache

**Fix:**
```bash
# Update requirements.txt
echo "Flask-Login==0.6.3" >> requirements.txt

# Rebuild with --no-cache
gcloud builds submit --tag gcr.io/telepay-459221/gcregister-10-26 --no-cache

# Re-deploy
gcloud run deploy gcregister-10-26 ...
```

#### Issue 3: "relation 'registered_users' does not exist"

**Cause:** Database migration not run

**Fix:**
```bash
# Run migration SQL from DB_MIGRATION_USER_ACCOUNTS.md
gcloud sql connect YOUR_INSTANCE --user=USERNAME --database=DATABASE_NAME

# Execute all migration SQL
```

#### Issue 4: Login redirects to /login infinitely

**Cause:** User object not serializable or user_loader returns None

**Fix:**
Check `tpr10-26.py`:
```python
@login_manager.user_loader
def load_user(user_id):
    # Ensure this returns User object or None
    user_data = db_manager.get_user_by_id(user_id)
    if user_data:
        return User(user_data['user_id'], user_data['username'], user_data['email'])
    return None
```

#### Issue 5: 403 Forbidden when editing own channel

**Cause:** UUID comparison failing (string vs UUID type)

**Fix:**
```python
# In edit_channel route, ensure UUID comparison:
if str(channel['client_id']) != str(current_user.id):
    abort(403)
```

---

## Step 8: Cleanup Test Data (Optional)

After testing, remove test users:

```sql
-- Delete test user (channels will cascade due to FK)
DELETE FROM registered_users WHERE username = 'testuser123';
DELETE FROM registered_users WHERE username = 'testuser456';

-- Verify deletion
SELECT COUNT(*) FROM registered_users WHERE username LIKE 'testuser%';
-- Expected: 0
```

---

## Step 9: Update Documentation

Update the following files with deployment results:

### 9.1 MAIN_ARCHITECTURE_WORKFLOW.md

Mark user account steps as complete:

```markdown
####  Step 10: Create `registered_users` Table
- **Status:**  COMPLETED (2025-10-28)
- **File:** DB_MIGRATION_USER_ACCOUNTS.md executed
...

####  Step 12: Add User Management to GCRegister10-26
- **Status:**  COMPLETED (2025-10-28)
- **Files Modified:**
  - forms.py - Added LoginForm, SignupForm
  - database_manager.py - Added user management functions
  - tpr10-26.py - Added authentication routes
...
```

### 9.2 PROGRESS.md

Add entry:

```markdown
### October 28, 2025
-  User Account Management implemented
  - Database migration executed
  - GCRegister10-26 modified with Flask-Login
  - User signup/login/logout working
  - Multi-channel dashboard functional
  - Authorization checks in place
  - 10-channel limit enforced
```

### 9.3 DECISIONS.md

Document decisions:

```markdown
### Decision: Flask-Login for Session Management
- **Date:** October 28, 2025
- **Status:**  Implemented
- **Context:** Need session management for user authentication
- **Decision:** Use Flask-Login library
- **Rationale:**
  - Industry standard for Flask applications
  - Provides @login_required decorator
  - Built-in remember-me functionality
  - Minimal configuration required
```

---

## Step 10: Post-Deployment Monitoring

### 10.1 Set Up Alerts (Optional)

```bash
# Create alert for high error rate
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="GCRegister High Error Rate" \
  --condition-display-name="Error rate > 5%" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=300s
```

### 10.2 Monitor User Signups

```sql
-- Daily signup count
SELECT DATE(created_at) as signup_date, COUNT(*) as new_users
FROM registered_users
WHERE user_id != '00000000-0000-0000-0000-000000000000'
GROUP BY DATE(created_at)
ORDER BY signup_date DESC
LIMIT 30;
```

### 10.3 Monitor Channel Creation

```sql
-- Channels per user
SELECT u.username, COUNT(c.open_channel_id) as channel_count
FROM registered_users u
LEFT JOIN main_clients_database c ON u.user_id = c.client_id
WHERE u.user_id != '00000000-0000-0000-0000-000000000000'
GROUP BY u.username
ORDER BY channel_count DESC;
```

---

## Rollback Plan

If deployment fails and rollback is needed:

### Option 1: Revert to Previous Cloud Run Revision

```bash
# List revisions
gcloud run revisions list --service gcregister-10-26 --region us-central1

# Revert to previous revision
gcloud run services update-traffic gcregister-10-26 \
  --region us-central1 \
  --to-revisions PREVIOUS_REVISION=100
```

### Option 2: Rollback Database Changes

Follow rollback procedure in `DB_MIGRATION_USER_ACCOUNTS.md`:

```sql
-- ROLLBACK: Remove user account tables and columns
ALTER TABLE main_clients_database DROP CONSTRAINT IF EXISTS fk_client_id;
ALTER TABLE main_clients_database DROP COLUMN IF EXISTS client_id;
ALTER TABLE main_clients_database DROP COLUMN IF EXISTS created_by;
ALTER TABLE main_clients_database DROP COLUMN IF EXISTS updated_at;
DROP TABLE IF EXISTS registered_users CASCADE;
```

**  WARNING:** Rollback will delete all user accounts and lose client_id relationships.

---

## Success Criteria

Deployment is successful when:

- [ ] Database migration completed without errors
- [ ] GCRegister10-26 deployed successfully to Cloud Run
- [ ] Health endpoint returns 200 OK
- [ ] Signup flow creates users in database
- [ ] Login flow authenticates users and creates session
- [ ] Dashboard displays user's channels
- [ ] Add channel flow creates channel with correct client_id
- [ ] Edit channel flow updates channel (authorization enforced)
- [ ] 10-channel limit prevents creating 11th channel
- [ ] Logout clears session
- [ ] No errors in Cloud Run logs
- [ ] Legacy channels still accessible (linked to legacy_system user)

---

## Related Documentation

- `USER_ACCOUNT_MANAGEMENT_ARCHITECTURE.md` - Architecture design
- `DB_MIGRATION_USER_ACCOUNTS.md` - Database migration SQL
- `GCREGISTER_USER_MANAGEMENT_GUIDE.md` - Code modification guide
- `MAIN_ARCHITECTURE_WORKFLOW.md` - Implementation tracker

---

**Deployment Status:** ó Ready for Execution
**Estimated Time:** 2-3 hours (including testing)
**Risk Level:** Medium (modifies existing service)
**Reversible:** Yes (rollback procedure provided)

---

**Document Version:** 1.0
**Author:** Claude (Anthropic)
**Last Updated:** 2025-10-28
