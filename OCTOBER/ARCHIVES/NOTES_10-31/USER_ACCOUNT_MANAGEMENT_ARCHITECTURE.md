# User Account Management & Multi-Channel Dashboard Architecture

**Version:** 1.0
**Date:** 2025-10-28
**Status:** Design Proposal
**Target Implementation:** Q4 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Proposed Solution](#proposed-solution)
4. [Database Architecture](#database-architecture)
5. [Security & Authentication](#security--authentication)
6. [Web Dashboard Design](#web-dashboard-design)
7. [Integration with Existing System](#integration-with-existing-system)
8. [Integration with Threshold Payout System](#integration-with-threshold-payout-system)
9. [Implementation Phases](#implementation-phases)
10. [API Endpoints Reference](#api-endpoints-reference)
11. [Security Considerations](#security-considerations)
12. [User Experience Flow](#user-experience-flow)

---

## Executive Summary

### Current State
- **GCRegister10-26** accepts anonymous channel registrations
- No user accounts or authentication
- No way to track which channels belong to which owner
- No dashboard for managing multiple channels
- One-time registration with no edit capability

### Proposed Solution
Introduce a **User Account Management System** that enables:

1. **User Registration** - Email, username, password authentication
2. **Multi-Channel Management** - One user can manage up to 10 channels
3. **Web Dashboard** - View, edit, and create channels at `/channels`
4. **Secure Mapping** - UUID-based `client_id` links users to channels
5. **Seamless Integration** - Works with both instant and threshold payout strategies

### Key Innovation
**UUID-based client_id** acts as a secure, opaque identifier:
- Not derivable from username or email
- Enables one-to-many relationship (user → channels)
- Preserves privacy (no username exposure in database queries)
- Allows username changes without breaking channel mappings

---

## Problem Statement

### Business Requirements

1. **Account Creation**
   - Users must create accounts before registering channels
   - Basic information: email, username, password
   - Email verification (optional for MVP)

2. **Multi-Channel Management**
   - One user can own and manage multiple channels (max 10)
   - Dashboard to view all channels owned by user
   - Edit channel configurations after initial registration
   - Add new channels up to limit

3. **Security & Privacy**
   - Mapping between users and channels must be secure
   - Username should not be directly stored in channel database
   - Use cryptographic hash or UUID for mapping

4. **Integration**
   - Must work with existing `main_clients_database` schema
   - Must support both instant and threshold payout strategies
   - Minimal disruption to existing services

### Technical Challenges

#### Challenge 1: User-to-Channel Mapping

**Naive Approach (REJECTED):**
```sql
-- BAD: Storing username directly
main_clients_database:
  open_channel_id | username | ...
```
**Problems:**
- Username exposed in database
- Username change breaks everything
- No clean one-to-many relationship

**Proposed Approach:**
```sql
-- GOOD: UUID-based client_id
registered_users:
  user_id (UUID) | username | email | password_hash | ...

main_clients_database:
  open_channel_id | client_id (UUID) | ...
```
**Benefits:**
- Opaque identifier (not derivable)
- Clean foreign key relationship
- Username changes don't affect channels
- Privacy-preserving

#### Challenge 2: 10-Channel Limit Enforcement

**Where to enforce:**
- Server-side validation in GCRegister (backend)
- Client-side feedback in dashboard (UX)
- Database constraint (data integrity)

**Proposed:**
```python
# Server-side check before channel creation
def check_channel_limit(client_id: str) -> bool:
    channel_count = db.count_channels_by_client(client_id)
    return channel_count < 10
```

#### Challenge 3: Edit Capability

**Current:**
- Channels registered once, never edited
- No update mechanism

**Proposed:**
- `/channels/<open_channel_id>/edit` endpoint
- Form pre-populated with existing data
- Submit updates `main_clients_database` entry

---

## Proposed Solution

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER ACCOUNT LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  www.paygateprime.com/signup   → User registration               │
│  www.paygateprime.com/login    → User authentication             │
│  www.paygateprime.com/channels → Channel management dashboard    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  registered_users (New Table)                            │    │
│  │  ├─ user_id (UUID, PK)                                   │    │
│  │  ├─ username (unique)                                    │    │
│  │  ├─ email (unique)                                       │    │
│  │  ├─ password_hash (bcrypt)                               │    │
│  │  ├─ created_at, updated_at                               │    │
│  │  └─ is_active, email_verified                            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                          │                                        │
│                          │ One-to-Many (user → channels)         │
│                          ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  main_clients_database (Modified)                        │    │
│  │  ├─ open_channel_id (PK)                                 │    │
│  │  ├─ client_id (UUID, FK → registered_users.user_id)     │    │
│  │  ├─ open_channel_title, description                      │    │
│  │  ├─ closed_channel_id, title, description                │    │
│  │  ├─ sub_1/2/3_price, sub_1/2/3_time                      │    │
│  │  ├─ client_wallet_address                                │    │
│  │  ├─ client_payout_currency, network                      │    │
│  │  ├─ payout_strategy (instant/threshold)                  │    │
│  │  └─ payout_threshold_usd                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### User Journey

**1. Sign Up**
```
User visits www.paygateprime.com/signup
  → Fills form: email, username, password
  → Server generates user_id (UUID)
  → Stores in registered_users table
  → Sends confirmation email (optional)
  → Redirects to login
```

**2. Log In**
```
User visits www.paygateprime.com/login
  → Enters username + password
  → Server validates credentials
  → Creates session (Flask session or JWT)
  → Redirects to /channels dashboard
```

**3. Dashboard View**
```
User at www.paygateprime.com/channels (authenticated)
  → Server queries: SELECT * FROM main_clients_database WHERE client_id = {user_id}
  → Returns list of user's channels (0-10)
  → Displays:
      ├─ Active Channel 1 (Gold Tier) - open_channel_title
      ├─ Active Channel 2 (Silver Tier) - open_channel_title
      └─ [Add New Channel] button (if < 10)
```

**4. Edit Channel**
```
User clicks "Edit" on Channel 1
  → Navigates to /channels/{open_channel_id}/edit
  → Form pre-populated with current values
  → User modifies:
      ├─ Tier prices/times
      ├─ Wallet address
      ├─ Payout strategy (instant → threshold)
      └─ Threshold amount
  → Submit → UPDATE main_clients_database WHERE open_channel_id = ...
  → Redirect to /channels with success message
```

**5. Add Channel**
```
User clicks "Add New Channel"
  → Server checks: count(channels) < 10
  → If yes: Shows registration form (same as current GCRegister)
  → Auto-populates client_id from session
  → Submit → INSERT INTO main_clients_database
  → Redirect to /channels
```

---

## Database Architecture

### New Table: `registered_users`

**Purpose:** Store user account information for authentication and multi-channel management

```sql
CREATE TABLE registered_users (
    -- Primary Key
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Authentication
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash

    -- Account Status
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,

    -- Password Reset
    reset_token VARCHAR(255),
    reset_token_expires TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,

    -- Indexes
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_verification_token (verification_token),
    INDEX idx_reset_token (reset_token)
);
```

**Key Fields:**

- **`user_id`**: UUID automatically generated, serves as opaque identifier
- **`password_hash`**: bcrypt hash with salt (never store plaintext)
- **`email_verified`**: Email confirmation status
- **`verification_token`**: One-time token for email verification
- **`reset_token`**: One-time token for password reset

### Modified Table: `main_clients_database`

**Changes:**
1. Add `client_id` column (foreign key to `registered_users.user_id`)
2. Add `created_by` column (username for audit trail, optional)
3. Keep `payout_strategy` and `payout_threshold_usd` (from threshold architecture)

```sql
ALTER TABLE main_clients_database
-- Add client_id foreign key
ADD COLUMN client_id UUID NOT NULL,
ADD COLUMN created_by VARCHAR(50),  -- Username at creation time (audit)
ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

-- Add foreign key constraint
ADD CONSTRAINT fk_client_id
    FOREIGN KEY (client_id)
    REFERENCES registered_users(user_id)
    ON DELETE CASCADE;  -- Delete channels when user deleted

-- Add index for efficient queries
CREATE INDEX idx_client_id ON main_clients_database(client_id);

-- Add constraint: each user max 10 channels (enforced in application logic)
-- Cannot enforce in database without complex trigger
```

**Updated Schema:**
```sql
main_clients_database (
    open_channel_id VARCHAR(14) PRIMARY KEY,
    client_id UUID NOT NULL,  -- NEW: Links to registered_users
    created_by VARCHAR(50),    -- NEW: Audit trail

    open_channel_title VARCHAR(100) NOT NULL,
    open_channel_description VARCHAR(500),
    closed_channel_id VARCHAR(14) NOT NULL,
    closed_channel_title VARCHAR(100) NOT NULL,
    closed_channel_description VARCHAR(500),

    sub_1_price NUMERIC(10, 2),
    sub_1_time INTEGER,
    sub_2_price NUMERIC(10, 2),
    sub_2_time INTEGER,
    sub_3_price NUMERIC(10, 2),
    sub_3_time INTEGER,

    client_wallet_address VARCHAR(200) NOT NULL,
    client_payout_currency VARCHAR(10) NOT NULL,
    client_payout_network VARCHAR(50) NOT NULL,

    payout_strategy VARCHAR(20) DEFAULT 'instant',        -- From threshold architecture
    payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,        -- From threshold architecture
    payout_threshold_updated_at TIMESTAMP,                -- From threshold architecture

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (client_id) REFERENCES registered_users(user_id) ON DELETE CASCADE
);
```

### Migration Strategy

**For Existing Channels (Already Registered):**

1. **Create temporary client_id for existing channels:**
```sql
-- Step 1: Create a default "legacy" user
INSERT INTO registered_users (user_id, username, email, password_hash, is_active)
VALUES (
    '00000000-0000-0000-0000-000000000000',  -- Reserved UUID
    'legacy_system',
    'legacy@paygateprime.com',
    '$2b$12$...',  -- Random hash, login disabled
    FALSE
);

-- Step 2: Update existing channels to use legacy client_id
UPDATE main_clients_database
SET client_id = '00000000-0000-0000-0000-000000000000'
WHERE client_id IS NULL;

-- Step 3: Make client_id NOT NULL
ALTER TABLE main_clients_database
ALTER COLUMN client_id SET NOT NULL;
```

2. **Allow users to claim legacy channels:**
   - Admin panel to assign legacy channels to real users
   - Or: Email legacy channel owners to create accounts and claim

---

## Security & Authentication

### Password Hashing

**Use bcrypt with salt:**
```python
from werkzeug.security import generate_password_hash, check_password_hash

# Registration
password_hash = generate_password_hash(password, method='bcrypt')

# Login
if check_password_hash(stored_hash, provided_password):
    # Valid
```

**Why bcrypt:**
- Automatic salt generation
- Configurable work factor (slow by design)
- Industry standard
- Built into Werkzeug (Flask dependency)

### Session Management

**Flask-Login Integration:**
```python
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required

class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = user_id  # UUID
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    # Load user from database by UUID
    return db_manager.get_user_by_id(user_id)
```

**Session Configuration:**
```python
app.config['SECRET_KEY'] = config['secret_key']  # Already exists
app.config['SESSION_COOKIE_SECURE'] = True       # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True     # No JS access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'    # CSRF protection
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
```

### CSRF Protection

**Already implemented via WTForms:**
```python
# forms.py
from flask_wtf import FlaskForm

class ChannelEditForm(FlaskForm):
    # CSRF token automatically included
    # WTF_CSRF_ENABLED = True (already set)
```

### Authorization Checks

**Ensure users can only edit their own channels:**
```python
@app.route('/channels/<open_channel_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_channel(open_channel_id):
    # Get channel from database
    channel = db_manager.get_channel_by_id(open_channel_id)

    # Check ownership
    if channel['client_id'] != current_user.id:
        abort(403, "Unauthorized: You don't own this channel")

    # Proceed with edit
    ...
```

### UUID Security Properties

**Why UUIDs are secure for client_id:**

1. **Not Enumerable**: Cannot guess other users' UUIDs
   - Example: `7f3e9a2b-4c1d-4e5f-8a9b-1c2d3e4f5a6b`
   - vs. Integer: `1`, `2`, `3` (easy to enumerate)

2. **Opaque**: No information leakage
   - Cannot derive from username or email
   - No sequential patterns

3. **Collision-Resistant**: 2^122 possible values (UUID v4)
   - Effectively zero collision probability

4. **Database-Generated**: Server controls generation
   - `gen_random_uuid()` in PostgreSQL
   - No client input

---

## Web Dashboard Design

### Dashboard Page: `/channels`

**Layout:**

```html
┌────────────────────────────────────────────────────────────┐
│  PayGate Prime - Channel Management                        │
│  Logged in as: @username                    [Logout]       │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  Your Channels (3/10)                                       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 📢 Active Channel: Premium Crypto Signals            │  │
│  │ 🔒 Private Channel: Premium Signals VIP              │  │
│  │                                                        │  │
│  │ ▼ Details                                             │  │
│  │   Open Channel ID: -1001234567890                     │  │
│  │   Closed Channel ID: -1009876543210                   │  │
│  │                                                        │  │
│  │   💰 Tier 1 (Gold): $50 for 30 days                  │  │
│  │   💰 Tier 2 (Silver): $30 for 30 days                │  │
│  │   💰 Tier 3 (Bronze): $15 for 30 days                │  │
│  │                                                        │  │
│  │   Payout: INSTANT to BTC (bc1q...)                    │  │
│  │                                                        │  │
│  │   [Edit Channel] [View Analytics] [Generate Link]    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 📢 Active Channel: NFT Alpha Alerts                  │  │
│  │ 🔒 Private Channel: NFT Alpha VIP                    │  │
│  │                                                        │  │
│  │ ▼ Details                                             │  │
│  │   [Collapsed - click to expand]                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 📢 Active Channel: DeFi Research                     │  │
│  │ 🔒 Private Channel: DeFi Research Pro                │  │
│  │                                                        │  │
│  │ ▼ Details                                             │  │
│  │   Payout: THRESHOLD ($500) to XMR                     │  │
│  │   Accumulated: $340.50 / $500.00 (68%)                │  │
│  │   [Collapsed - click to expand]                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  [➕ Add New Channel]  (7 slots remaining)                 │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

### Edit Channel Page: `/channels/<id>/edit`

**Form (Pre-populated with current values):**

```html
┌────────────────────────────────────────────────────────────┐
│  Edit Channel: Premium Crypto Signals                      │
│  [Back to Dashboard]                                        │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  📢 Open Channel Configuration                             │
│    Channel ID: -1001234567890 [Read-only]                  │
│    Title: [Premium Crypto Signals            ]             │
│    Description: [Get exclusive crypto signals...]          │
│                                                              │
│  🔒 Private Channel Configuration                          │
│    Channel ID: -1009876543210 [Read-only]                  │
│    Title: [Premium Signals VIP              ]             │
│    Description: [VIP access to premium...]                 │
│                                                              │
│  💰 Subscription Tiers                                     │
│    Number of Tiers: ○ 1  ● 2  ○ 3                         │
│                                                              │
│    Tier 1 (Gold):                                          │
│      Price: [$50.00] Duration: [30] days                   │
│                                                              │
│    Tier 2 (Silver):                                        │
│      Price: [$30.00] Duration: [30] days                   │
│                                                              │
│  💳 Payout Configuration                                   │
│    Wallet Address: [bc1q...]                               │
│    Currency: [BTC ▼]  Network: [BTC ▼]                     │
│                                                              │
│    Payout Strategy:                                        │
│      ● Instant Payout (Recommended for BTC, LTC, DOGE)     │
│      ○ Threshold Payout (For XMR - minimizes fees)         │
│                                                              │
│    [Threshold Amount field - hidden unless Threshold]      │
│                                                              │
│  [Save Changes] [Cancel]                                   │
│                                                              │
└────────────────────────────────────────────────────────────┘
```

### Add Channel Page: `/channels/add`

**Identical form to Edit, but:**
- All fields empty (no pre-population)
- Channel IDs are input fields (not read-only)
- Shows "You can create X more channels" message

---

## Integration with Existing System

### GCRegister10-26 Modifications

**Current Flow (Anonymous):**
```
User visits www.paygateprime.com
  → Fills registration form
  → Submits
  → Channel created in main_clients_database
```

**New Flow (Authenticated):**
```
User visits www.paygateprime.com
  → Redirects to /login (if not authenticated)
  → After login, redirects to /channels
  → User clicks "Add Channel"
  → Fills form
  → Submit includes client_id from session
  → Channel created with client_id
```

**Code Changes:**

```python
# tpr10-26.py - BEFORE
@app.route('/', methods=['GET', 'POST'])
def register():
    form = ChannelRegistrationForm()

    if form.validate_on_submit():
        registration_data = {
            'open_channel_id': form.open_channel_id.data,
            # ... other fields
        }
        db_manager.insert_channel_registration(registration_data)
        return redirect(url_for('success'))

    return render_template('register.html', form=form)

# tpr10-26.py - AFTER
from flask_login import login_required, current_user

@app.route('/')
def index():
    """Landing page - redirect to login or dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/channels')
@login_required
def dashboard():
    """Channel management dashboard"""
    # Get user's channels
    channels = db_manager.get_channels_by_client(current_user.id)
    return render_template('dashboard.html', channels=channels)

@app.route('/channels/add', methods=['GET', 'POST'])
@login_required
def add_channel():
    """Add new channel (authenticated)"""
    # Check 10-channel limit
    channel_count = db_manager.count_channels_by_client(current_user.id)
    if channel_count >= 10:
        flash('Maximum 10 channels per account', 'danger')
        return redirect(url_for('dashboard'))

    form = ChannelRegistrationForm()

    if form.validate_on_submit():
        registration_data = {
            'client_id': current_user.id,  # NEW: Auto-populate from session
            'created_by': current_user.username,  # NEW: Audit trail
            'open_channel_id': form.open_channel_id.data,
            # ... other fields
        }
        db_manager.insert_channel_registration(registration_data)
        flash('Channel created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('add_channel.html', form=form)

@app.route('/channels/<open_channel_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_channel(open_channel_id):
    """Edit existing channel (authenticated + authorized)"""
    # Get channel
    channel = db_manager.get_channel_by_id(open_channel_id)

    # Authorization check
    if not channel or channel['client_id'] != current_user.id:
        abort(403, "Unauthorized")

    form = ChannelRegistrationForm(data=channel)  # Pre-populate

    if form.validate_on_submit():
        update_data = {
            'open_channel_title': form.open_channel_title.data,
            'closed_channel_title': form.closed_channel_title.data,
            # ... other fields
            'updated_at': datetime.now()
        }
        db_manager.update_channel(open_channel_id, update_data)
        flash('Channel updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_channel.html', form=form, channel=channel)
```

### Database Manager Updates

**New Functions:**

```python
# database_manager.py

def get_user_by_username(self, username: str) -> Optional[Dict]:
    """Get user by username for login."""
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT user_id, username, email, password_hash, is_active
               FROM registered_users
               WHERE username = %s""",
            (username,)
        )
        result = cur.fetchone()
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'email': result[2],
                'password_hash': result[3],
                'is_active': result[4]
            }
        return None

def get_user_by_id(self, user_id: str) -> Optional[Dict]:
    """Get user by UUID for session loading."""
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT user_id, username, email, is_active
               FROM registered_users
               WHERE user_id = %s""",
            (user_id,)
        )
        result = cur.fetchone()
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'email': result[2],
                'is_active': result[3]
            }
        return None

def create_user(self, username: str, email: str, password_hash: str) -> str:
    """Create new user account, returns user_id (UUID)."""
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO registered_users (username, email, password_hash)
               VALUES (%s, %s, %s)
               RETURNING user_id""",
            (username, email, password_hash)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        return str(user_id)

def get_channels_by_client(self, client_id: str) -> List[Dict]:
    """Get all channels owned by a client."""
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM main_clients_database
               WHERE client_id = %s
               ORDER BY created_at DESC""",
            (client_id,)
        )
        columns = [desc[0] for desc in cur.description]
        results = []
        for row in cur.fetchall():
            results.append(dict(zip(columns, row)))
        return results

def count_channels_by_client(self, client_id: str) -> int:
    """Count channels owned by a client (for 10-limit check)."""
    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT COUNT(*) FROM main_clients_database
               WHERE client_id = %s""",
            (client_id,)
        )
        return cur.fetchone()[0]

def update_channel(self, open_channel_id: str, update_data: Dict) -> bool:
    """Update channel configuration."""
    # Build dynamic UPDATE query based on provided fields
    set_clauses = []
    values = []

    for key, value in update_data.items():
        if key != 'open_channel_id':  # Don't update PK
            set_clauses.append(f"{key} = %s")
            values.append(value)

    if not set_clauses:
        return False

    values.append(open_channel_id)

    query = f"""UPDATE main_clients_database
                SET {', '.join(set_clauses)}
                WHERE open_channel_id = %s"""

    with self.get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, values)
        conn.commit()
        return cur.rowcount > 0
```

### TelePay10-26 Impact

**No changes required** - Bot operates at channel level:
- Subscription links still use `open_channel_id`
- Database queries still work (queries by `open_channel_id`, not `client_id`)
- Bot doesn't need to know about user accounts

**Optional Enhancement:**
- Admin commands for user account info
- Example: `/admin user_channels @username` → List all channels owned by user

### GCWebhook1/2 Impact

**No changes required** - Webhooks operate at channel level:
- Token contains `open_channel_id`
- Database writes to `private_channel_users_database` (unchanged)
- No awareness of `client_id` needed

### GCSplit1/2/3 Impact

**No changes required** - Payment splitting operates at channel/wallet level:
- Uses `wallet_address` from channel configuration
- No awareness of user accounts

### GCHostPay1/2/3 Impact

**No changes required** - Payment execution operates at transaction level:
- Uses `payin_address` and amounts
- No awareness of user accounts

---

## Integration with Threshold Payout System

### Database Schema Alignment

**Both architectures modify `main_clients_database`:**

**User Account Architecture adds:**
```sql
client_id UUID NOT NULL,
created_by VARCHAR(50),
updated_at TIMESTAMP
```

**Threshold Payout Architecture adds:**
```sql
payout_strategy VARCHAR(20) DEFAULT 'instant',
payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
payout_threshold_updated_at TIMESTAMP
```

**Combined Schema (Both Systems):**
```sql
ALTER TABLE main_clients_database
-- User Account Management
ADD COLUMN client_id UUID NOT NULL,
ADD COLUMN created_by VARCHAR(50),
ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

-- Threshold Payout
ADD COLUMN payout_strategy VARCHAR(20) DEFAULT 'instant',
ADD COLUMN payout_threshold_usd NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN payout_threshold_updated_at TIMESTAMP,

-- Foreign Key
ADD CONSTRAINT fk_client_id
    FOREIGN KEY (client_id)
    REFERENCES registered_users(user_id)
    ON DELETE CASCADE;
```

### Dashboard Integration

**Channel Edit Form includes threshold payout settings:**

```html
💳 Payout Configuration

  Wallet Address: [bc1q...]
  Currency: [XMR ▼]  Network: [XMR ▼]

  Payout Strategy:
    ○ Instant Payout (Recommended for BTC, LTC, DOGE)
    ● Threshold Payout (For XMR - minimizes fees)

  ↳ Threshold Amount (USD): [$500.00]
    💡 Payments will accumulate until this amount is reached.
    💡 Recommended: $100-500 for Monero to minimize fees.

  Accumulated (if threshold): $340.50 / $500.00 (68%)
    ⏱️ Estimated payout: 5-10 days
```

**Dashboard shows accumulation status:**
- For threshold channels: Display accumulated amount
- Progress bar showing % toward threshold
- Estimated payout time (based on payment frequency)

### User Experience Benefits

**Per-Channel Configuration:**
- User can have some channels on instant payout (BTC)
- Other channels on threshold payout (XMR)
- Edit payout strategy anytime via dashboard

**Example Use Case:**
```
User manages 3 channels:

Channel 1: Crypto Signals
  ├─ Payout: INSTANT to BTC
  └─ Receives $50 → BTC sent immediately

Channel 2: NFT Alpha
  ├─ Payout: THRESHOLD ($500) to XMR
  └─ Accumulates $340 → Waiting for $160 more

Channel 3: DeFi Research
  ├─ Payout: INSTANT to LTC
  └─ Receives $30 → LTC sent immediately
```

### GCAccumulator Integration

**When threshold payout triggered:**

1. **GCWebhook1** checks `payout_strategy` from `main_clients_database`
2. If `threshold`: Enqueues to **GCAccumulator**
3. **GCAccumulator** converts to USDT, stores in `payout_accumulation`
4. `payout_accumulation.client_id` = `main_clients_database.client_id`
5. User can view accumulation in dashboard grouped by channel

**Dashboard Query:**
```sql
-- Get accumulation total for a specific channel
SELECT SUM(accumulated_amount_usdt) as total_accumulated
FROM payout_accumulation
WHERE client_id = %s
  AND closed_channel_id = %s
  AND is_paid_out = FALSE;
```

### Batch Payout Notifications

**Optional Enhancement:**
```python
# When GCBatchProcessor creates payout batch, notify user

def notify_user_of_payout(client_id: str, channel_id: str, amount_usdt: Decimal):
    """Send email notification when threshold payout triggered."""
    user = db_manager.get_user_by_id(client_id)
    channel = db_manager.get_channel_by_id(channel_id)

    send_email(
        to=user['email'],
        subject=f"Payout Processed: {channel['open_channel_title']}",
        body=f"""
        Your threshold payout has been processed!

        Channel: {channel['open_channel_title']}
        Amount: ${amount_usdt} USD
        Currency: {channel['client_payout_currency']}

        The funds should arrive in your wallet within 24 hours.

        View details: www.paygateprime.com/channels
        """
    )
```

---

## Implementation Phases

### Phase 1: User Management Foundation (Week 1-2)

**Objectives:**
- Database schema ready
- User authentication working
- Basic login/signup flow

**Tasks:**
1. Create `registered_users` table
2. Add `client_id` column to `main_clients_database`
3. Implement signup endpoint (`/signup`)
4. Implement login endpoint (`/login`)
5. Implement logout endpoint (`/logout`)
6. Set up Flask-Login
7. Password hashing with bcrypt
8. Session management
9. Write unit tests

**Deliverables:**
- ✅ Users can create accounts
- ✅ Users can log in/out
- ✅ Sessions persist correctly
- ✅ Passwords securely hashed

**Testing:**
- Manual signup/login flow
- Test password validation
- Test session expiration
- Security audit (CSRF, XSS)

### Phase 2: Channel Dashboard (Week 3-4)

**Objectives:**
- Dashboard displays user's channels
- Basic navigation

**Tasks:**
1. Create `/channels` dashboard route
2. Implement `get_channels_by_client()` database function
3. Design dashboard template (HTML/CSS)
4. Show channel list with details
5. Implement accordion/collapse for details
6. Add "Add Channel" button (routes to existing form)
7. Add "Edit Channel" button (placeholder)
8. Write integration tests

**Deliverables:**
- ✅ Dashboard shows user's channels
- ✅ Channels display all configuration data
- ✅ Navigation works correctly

**Testing:**
- Test with 0 channels (empty state)
- Test with 1 channel
- Test with 10 channels (max limit)
- Test channel data display accuracy

### Phase 3: Add Channel Flow (Week 5)

**Objectives:**
- Users can add new channels via dashboard

**Tasks:**
1. Create `/channels/add` route
2. Modify registration form to accept `client_id`
3. Implement 10-channel limit check
4. Auto-populate `client_id` from session
5. Redirect to dashboard after success
6. Flash success/error messages
7. Write integration tests

**Deliverables:**
- ✅ Users can add channels (up to 10)
- ✅ Limit enforced (403 if ≥10)
- ✅ `client_id` correctly stored
- ✅ Success feedback shown

**Testing:**
- Add 1st channel
- Add 10th channel
- Try to add 11th (should fail)
- Verify `client_id` in database

### Phase 4: Edit Channel Flow (Week 6)

**Objectives:**
- Users can edit existing channel configurations

**Tasks:**
1. Create `/channels/<id>/edit` route
2. Implement authorization check (owner verification)
3. Pre-populate form with current values
4. Implement `update_channel()` database function
5. Handle tier changes (enable/disable tiers)
6. Update threshold payout settings
7. Add "Delete Channel" button (optional)
8. Write integration tests

**Deliverables:**
- ✅ Users can edit their own channels only
- ✅ Form pre-populated correctly
- ✅ Updates save to database
- ✅ 403 error for unauthorized access

**Testing:**
- Edit channel owned by user (should work)
- Try to edit another user's channel (should 403)
- Verify database updates
- Test threshold payout toggle

### Phase 5: Threshold Payout Integration (Week 7)

**Objectives:**
- Dashboard shows accumulation status for threshold channels

**Tasks:**
1. Add accumulation query to dashboard
2. Display progress bars for threshold channels
3. Show accumulated amount vs threshold
4. Estimate payout time (optional)
5. Add threshold payout section to edit form
6. Test end-to-end with GCAccumulator
7. Implement email notifications (optional)

**Deliverables:**
- ✅ Dashboard shows accumulation for threshold channels
- ✅ Users can switch between instant/threshold
- ✅ Accumulation tracked correctly

**Testing:**
- Create threshold channel
- Trigger payments
- Verify accumulation display
- Test threshold reached → payout

### Phase 6: Migration & Production (Week 8)

**Objectives:**
- Migrate existing channels
- Deploy to production

**Tasks:**
1. Create migration script for existing channels
2. Assign legacy channels to default user
3. Run migration on staging
4. Verify data integrity
5. Deploy user management services
6. Update GCRegister routes
7. Monitor for errors
8. Create admin panel for user management (optional)

**Deliverables:**
- ✅ Existing channels migrated
- ✅ New user accounts functional
- ✅ Production deployment successful
- ✅ Monitoring in place

**Testing:**
- Smoke tests in production
- Test new user signup
- Test existing user login
- Verify channel creation/editing

---

## API Endpoints Reference

### Public Endpoints (No Authentication)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Landing page (redirects to login/dashboard) |
| GET/POST | `/signup` | User registration form |
| GET/POST | `/login` | User login form |
| GET | `/logout` | User logout (clears session) |
| GET | `/health` | Health check |

### Authenticated Endpoints (Login Required)

| Method | Endpoint | Description | Authorization |
|--------|----------|-------------|---------------|
| GET | `/channels` | Channel management dashboard | Current user only |
| GET/POST | `/channels/add` | Add new channel form | Current user only |
| GET/POST | `/channels/<id>/edit` | Edit channel form | Owner only |
| DELETE | `/channels/<id>` | Delete channel (optional) | Owner only |
| GET | `/profile` | User profile page (optional) | Current user only |
| POST | `/profile/password` | Change password (optional) | Current user only |

### API Endpoints (JSON) - Optional

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/channels` | List user's channels (JSON) |
| GET | `/api/channels/<id>` | Get channel details (JSON) |
| PUT | `/api/channels/<id>` | Update channel (JSON) |
| GET | `/api/accumulation/<channel_id>` | Get accumulation status (JSON) |

---

## Security Considerations

### Threat Model

**Threat 1: Account Takeover**
- **Attack:** Credential stuffing, password guessing
- **Mitigation:**
  - Strong password requirements (min 8 chars, mixed case, numbers)
  - Rate limiting on login endpoint (5 attempts per IP per hour)
  - Optional: 2FA (future enhancement)
  - Optional: Email verification required

**Threat 2: Unauthorized Channel Access**
- **Attack:** User tries to edit another user's channel
- **Mitigation:**
  - Authorization check: `channel.client_id == current_user.id`
  - 403 Forbidden if mismatch
  - No channel data leaked in error message

**Threat 3: Channel Enumeration**
- **Attack:** Brute-force channel IDs to discover channels
- **Mitigation:**
  - Channel IDs already opaque (Telegram channel IDs)
  - Authorization check prevents data leak
  - Rate limiting on API endpoints

**Threat 4: Session Hijacking**
- **Attack:** Steal session cookie, impersonate user
- **Mitigation:**
  - HTTPS only (`SESSION_COOKIE_SECURE = True`)
  - HttpOnly cookies (`SESSION_COOKIE_HTTPONLY = True`)
  - SameSite attribute (`SESSION_COOKIE_SAMESITE = 'Lax'`)
  - Short session lifetime (7 days, configurable)

**Threat 5: SQL Injection**
- **Attack:** Inject SQL via form inputs
- **Mitigation:**
  - Parameterized queries (already implemented)
  - WTForms validation
  - No raw SQL with user input

**Threat 6: CSRF**
- **Attack:** Cross-site request forgery on state-changing operations
- **Mitigation:**
  - WTForms CSRF protection (already enabled)
  - SameSite cookies

### Password Policy

**Requirements:**
```python
def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password meets requirements."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if not any(c.isupper() for c in password):
        return False, "Password must contain uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain number"

    # Optional: Check against common passwords list
    if password in COMMON_PASSWORDS:
        return False, "Password is too common"

    return True, "Password valid"
```

### Rate Limiting

**Apply to sensitive endpoints:**
```python
from flask_limiter import Limiter

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://"  # Or Redis for production
)

# Login endpoint: 5 attempts per hour
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def login():
    ...

# Signup endpoint: 3 signups per day per IP
@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("3 per day")
def signup():
    ...
```

### Audit Logging

**Log security-relevant events:**
```python
def log_security_event(event_type: str, user_id: str, details: Dict):
    """Log security events for audit trail."""
    print(f"🔐 [SECURITY] Event: {event_type}")
    print(f"👤 [SECURITY] User: {user_id}")
    print(f"📊 [SECURITY] Details: {details}")

    # Also write to database (optional)
    # db_manager.log_security_event(event_type, user_id, details)

# Usage examples:
log_security_event("LOGIN_SUCCESS", user.id, {"ip": request.remote_addr})
log_security_event("LOGIN_FAILED", username, {"ip": request.remote_addr, "reason": "Invalid password"})
log_security_event("CHANNEL_EDIT", user.id, {"channel_id": channel_id})
log_security_event("UNAUTHORIZED_ACCESS", user.id, {"attempted_channel": channel_id})
```

---

## User Experience Flow

### Complete User Journey

**1. New User Registration**
```
Step 1: Visit www.paygateprime.com
  → Sees landing page
  → Clicks "Sign Up"

Step 2: Fill signup form
  → Email: user@example.com
  → Username: crypto_signals_pro
  → Password: SecurePass123!
  → Confirm Password: SecurePass123!
  → Submit

Step 3: Email verification (optional)
  → Receives email with verification link
  → Clicks link → Account activated

Step 4: Login
  → Redirected to /login
  → Enters username + password
  → Clicks "Login"
  → Session created

Step 5: Dashboard
  → Redirected to /channels
  → Sees empty state: "No channels yet"
  → Clicks "Add New Channel"
```

**2. Adding First Channel**
```
Step 1: Fill channel form
  → Open Channel: -1001234567890
  → Open Title: "Premium Crypto Signals"
  → Closed Channel: -1009876543210
  → Closed Title: "Premium Signals VIP"
  → Tier 1: $50 for 30 days
  → Tier 2: $30 for 30 days
  → Wallet: bc1q...
  → Currency: BTC
  → Strategy: Instant
  → Submit

Step 2: Server processing
  → Validates form
  → Checks channel limit (1/10 - OK)
  → Inserts with client_id from session
  → Flash: "Channel created successfully!"

Step 3: Dashboard redirect
  → Shows channel in list
  → Displays all configuration
  → "Generate Link" button available
```

**3. Managing Multiple Channels**
```
Step 1: Add second channel (NFT project)
  → Click "Add New Channel"
  → Fill form with NFT channel details
  → Use XMR with threshold payout ($500)
  → Submit

Step 2: Dashboard now shows 2 channels
  ┌─ Channel 1: Crypto Signals (BTC, Instant)
  └─ Channel 2: NFT Alpha (XMR, Threshold)

Step 3: Edit existing channel
  → Click "Edit" on Channel 1
  → Change Tier 1 price: $50 → $60
  → Submit
  → Flash: "Channel updated!"
  → Dashboard reflects new price
```

**4. Threshold Payout Experience**
```
Step 1: User's Channel 2 receives payments
  → Payment 1: $50 → Accumulates to $50
  → Payment 2: $50 → Accumulates to $100
  → Dashboard shows: $100 / $500 (20%)

Step 2: More payments over time
  → Payment 10: $50 → Accumulates to $520
  → Threshold reached! (≥ $500)

Step 3: GCBatchProcessor triggers payout
  → Detects threshold crossed
  → Initiates USDT→XMR swap
  → Sends XMR to user's wallet

Step 4: User notified (optional)
  → Email: "Payout processed: $520 XMR sent"
  → Dashboard shows: "Last payout: $520 on 2025-10-28"
```

---

## Conclusion

### Summary

This architecture enables **secure, scalable multi-channel management** through:

1. **UUID-based client_id** - Opaque, secure identifier for user-to-channel mapping
2. **One-to-Many Relationship** - Single user → up to 10 channels
3. **Session-Based Authentication** - Flask-Login with bcrypt password hashing
4. **Web Dashboard** - Intuitive UI for channel creation and editing
5. **Seamless Integration** - Works with existing services (TelePay, GCSplit, GCHostPay)
6. **Threshold Payout Support** - Dashboard shows accumulation status

### Key Benefits

✅ **Security**
- No username exposure in database
- Strong password hashing (bcrypt)
- Authorization checks on all operations
- CSRF protection built-in

✅ **Scalability**
- Clean database schema with foreign keys
- Efficient queries (indexed on client_id)
- Supports thousands of users with 10 channels each

✅ **User Experience**
- Single dashboard for all channels
- Edit configurations anytime
- Real-time accumulation tracking (threshold)
- Clear feedback and error messages

✅ **Maintainability**
- Minimal changes to existing services
- Clean separation of concerns
- Well-defined API boundaries

### Integration with Threshold Payout

**Combined Benefits:**
- User can configure payout strategy per channel
- Dashboard shows accumulation progress
- Edit threshold amounts anytime
- Email notifications on payout

**Database Compatibility:**
- Both architectures extend `main_clients_database`
- No conflicts between columns
- Can deploy independently or together

### Next Steps

1. **Review & Approve** this architecture design
2. **Phase 1: User Management** - Create user accounts, authentication
3. **Phase 2: Dashboard** - Build channel listing interface
4. **Phase 3-4: CRUD Operations** - Add/Edit channel flows
5. **Phase 5: Threshold Integration** - Connect accumulation display
6. **Phase 6: Production** - Migrate and deploy

### Timeline

**Total Implementation: 8 weeks**
- Week 1-2: User management foundation
- Week 3-4: Dashboard
- Week 5: Add channel flow
- Week 6: Edit channel flow
- Week 7: Threshold payout integration
- Week 8: Migration and production deployment

**Can run in parallel with threshold payout development** - Both architectures are independent and can be deployed separately or together.

---

**Document Version:** 1.0
**Author:** Claude (Anthropic)
**Date:** 2025-10-28
**Status:** Proposal - Awaiting Review
**Related:** THRESHOLD_PAYOUT_ARCHITECTURE.md
