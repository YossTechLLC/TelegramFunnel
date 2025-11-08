# GCRegister10-26 User Management Implementation Guide

**Created:** 2025-10-28
**Purpose:** Add user account management, authentication, and multi-channel dashboard
**Related:** USER_ACCOUNT_MANAGEMENT_ARCHITECTURE.md, DB_MIGRATION_USER_ACCOUNTS.md

---

## Overview

This guide details ALL modifications needed to transform GCRegister10-26 from an anonymous registration service into a full user account management system with dashboard.

**Key Changes:**
1. Add Flask-Login for session management
2. Create LoginForm and SignupForm
3. Add user authentication routes (/login, /signup, /logout)
4. Create /channels dashboard route
5. Modify /register to /channels/add (authenticated)
6. Add /channels/<id>/edit route
7. Add user account database functions
8. Create new templates (login.html, signup.html, dashboard.html, edit_channel.html)
9. Modify existing templates for navigation

---

## File 1: requirements.txt

**Location:** `OCTOBER/10-26/GCRegister10-26/requirements.txt`

### Add Flask-Login Dependency

Add this line after Flask-WTF:

```txt
Flask==3.0.3
Flask-WTF==1.2.1
Flask-Login==0.6.3
WTForms==3.1.1
cloud-sql-python-connector==1.4.3
pg8000==1.30.3
google-cloud-secret-manager==2.16.3
python-dotenv==1.0.0
Flask-Limiter==3.5.0
Werkzeug==3.0.1
```

**Why Flask-Login:**
- Session management for authenticated users
- `@login_required` decorator for protected routes
- `current_user` proxy for accessing logged-in user
- Built-in support for "remember me" functionality

---

## File 2: forms.py

**Location:** `OCTOBER/10-26/GCRegister10-26/forms.py`

### Add New Imports

At the top of the file, add:

```python
from wtforms import PasswordField
from wtforms.validators import Email, EqualTo, ValidationError
```

### Add LoginForm Class

Add this BEFORE `ChannelRegistrationForm`:

```python
class LoginForm(FlaskForm):
    """
    User login form.
    """
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='❌ Username is required'),
            Length(min=3, max=50, message='❌ Username must be 3-50 characters')
        ],
        render_kw={
            'placeholder': 'Enter your username',
            'class': 'form-control',
            'autocomplete': 'username'
        }
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='❌ Password is required')
        ],
        render_kw={
            'placeholder': 'Enter your password',
            'class': 'form-control',
            'autocomplete': 'current-password'
        }
    )

    submit = SubmitField('Login', render_kw={'class': 'btn btn-primary'})
```

### Add SignupForm Class

Add this AFTER `LoginForm`:

```python
class SignupForm(FlaskForm):
    """
    User registration form with password validation.
    """
    username = StringField(
        'Username',
        validators=[
            DataRequired(message='❌ Username is required'),
            Length(min=3, max=50, message='❌ Username must be 3-50 characters')
        ],
        render_kw={
            'placeholder': 'Choose a username (3-50 characters)',
            'class': 'form-control',
            'autocomplete': 'username'
        }
    )

    email = StringField(
        'Email',
        validators=[
            DataRequired(message='❌ Email is required'),
            Email(message='❌ Please enter a valid email address'),
            Length(max=255, message='❌ Email must be less than 255 characters')
        ],
        render_kw={
            'placeholder': 'your.email@example.com',
            'class': 'form-control',
            'type': 'email',
            'autocomplete': 'email'
        }
    )

    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message='❌ Password is required'),
            Length(min=8, message='❌ Password must be at least 8 characters')
        ],
        render_kw={
            'placeholder': 'Choose a strong password (min 8 characters)',
            'class': 'form-control',
            'autocomplete': 'new-password'
        }
    )

    password_confirm = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message='❌ Please confirm your password'),
            EqualTo('password', message='❌ Passwords must match')
        ],
        render_kw={
            'placeholder': 'Enter password again',
            'class': 'form-control',
            'autocomplete': 'new-password'
        }
    )

    submit = SubmitField('Sign Up', render_kw={'class': 'btn btn-success'})

    def validate_password(form, field):
        """
        Custom password validation.
        Requires: uppercase, lowercase, digit.
        """
        password = field.data

        if not any(c.isupper() for c in password):
            raise ValidationError('❌ Password must contain at least one uppercase letter')

        if not any(c.islower() for c in password):
            raise ValidationError('❌ Password must contain at least one lowercase letter')

        if not any(c.isdigit() for c in password):
            raise ValidationError('❌ Password must contain at least one number')
```

**Note:** ChannelRegistrationForm remains unchanged for now. Threshold payout modifications from GCREGISTER_MODIFICATIONS_GUIDE.md should be applied separately.

---

## File 3: database_manager.py

**Location:** `OCTOBER/10-26/GCRegister10-26/database_manager.py`

### Add New Functions for User Management

Add these functions to the `DatabaseManager` class (after `insert_channel_registration`):

```python
    # ==============================================================================
    # User Account Management Functions
    # ==============================================================================

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username for login authentication.

        Args:
            username: The username to look up

        Returns:
            Dictionary with user data or None if not found
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"🔍 [DATABASE] Looking up user: {username}")
                    cur.execute(
                        """SELECT user_id, username, email, password_hash, is_active
                           FROM registered_users
                           WHERE username = %s""",
                        (username,)
                    )
                    result = cur.fetchone()

                    if result:
                        print(f"✅ [DATABASE] User found: {username}")
                        return {
                            'user_id': str(result[0]),  # Convert UUID to string
                            'username': result[1],
                            'email': result[2],
                            'password_hash': result[3],
                            'is_active': result[4]
                        }
                    else:
                        print(f"❌ [DATABASE] User not found: {username}")
                        return None
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error fetching user by username: {e}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by UUID for session loading (Flask-Login).

        Args:
            user_id: The UUID of the user

        Returns:
            Dictionary with user data or None if not found
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"🔍 [DATABASE] Loading user by ID: {user_id}")
                    cur.execute(
                        """SELECT user_id, username, email, is_active
                           FROM registered_users
                           WHERE user_id = %s""",
                        (user_id,)
                    )
                    result = cur.fetchone()

                    if result:
                        print(f"✅ [DATABASE] User loaded: {result[1]}")
                        return {
                            'user_id': str(result[0]),
                            'username': result[1],
                            'email': result[2],
                            'is_active': result[3]
                        }
                    else:
                        print(f"❌ [DATABASE] User ID not found: {user_id}")
                        return None
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error fetching user by ID: {e}")
            return None

    def create_user(self, username: str, email: str, password_hash: str) -> Optional[str]:
        """
        Create a new user account.

        Args:
            username: Chosen username (must be unique)
            email: Email address (must be unique)
            password_hash: Bcrypt-hashed password

        Returns:
            UUID of created user as string, or None if creation failed
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"👤 [DATABASE] Creating user: {username} ({email})")

                    # Check if username already exists
                    cur.execute(
                        "SELECT COUNT(*) FROM registered_users WHERE username = %s",
                        (username,)
                    )
                    if cur.fetchone()[0] > 0:
                        print(f"❌ [DATABASE] Username already exists: {username}")
                        return None

                    # Check if email already exists
                    cur.execute(
                        "SELECT COUNT(*) FROM registered_users WHERE email = %s",
                        (email,)
                    )
                    if cur.fetchone()[0] > 0:
                        print(f"❌ [DATABASE] Email already exists: {email}")
                        return None

                    # Insert new user
                    cur.execute(
                        """INSERT INTO registered_users (username, email, password_hash)
                           VALUES (%s, %s, %s)
                           RETURNING user_id""",
                        (username, email, password_hash)
                    )
                    user_id = cur.fetchone()[0]
                    conn.commit()

                    print(f"✅ [DATABASE] User created successfully: {username} (ID: {user_id})")
                    return str(user_id)

                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error creating user: {e}")
            return None

    def update_last_login(self, user_id: str) -> bool:
        """
        Update the last_login timestamp for a user.

        Args:
            user_id: UUID of the user

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        """UPDATE registered_users
                           SET last_login = CURRENT_TIMESTAMP
                           WHERE user_id = %s""",
                        (user_id,)
                    )
                    conn.commit()
                    print(f"✅ [DATABASE] Last login updated for user: {user_id}")
                    return True
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error updating last login: {e}")
            return False

    def get_channels_by_client(self, client_id: str) -> list:
        """
        Get all channels owned by a client (for dashboard).

        Args:
            client_id: UUID of the client

        Returns:
            List of channel dictionaries
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"📊 [DATABASE] Fetching channels for client: {client_id}")
                    cur.execute(
                        """SELECT * FROM main_clients_database
                           WHERE client_id = %s
                           ORDER BY created_at DESC""",
                        (client_id,)
                    )

                    # Get column names
                    columns = [desc[0] for desc in cur.description]

                    # Fetch all rows and convert to dictionaries
                    results = []
                    for row in cur.fetchall():
                        results.append(dict(zip(columns, row)))

                    print(f"✅ [DATABASE] Found {len(results)} channel(s) for client")
                    return results

                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error fetching channels: {e}")
            return []

    def count_channels_by_client(self, client_id: str) -> int:
        """
        Count channels owned by a client (for 10-limit check).

        Args:
            client_id: UUID of the client

        Returns:
            Number of channels owned
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM main_clients_database WHERE client_id = %s",
                        (client_id,)
                    )
                    count = cur.fetchone()[0]
                    print(f"📊 [DATABASE] Client {client_id} has {count} channel(s)")
                    return count
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error counting channels: {e}")
            return 0

    def get_channel_by_id(self, open_channel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single channel by its ID (for editing).

        Args:
            open_channel_id: The channel ID

        Returns:
            Dictionary with channel data or None if not found
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    print(f"🔍 [DATABASE] Fetching channel: {open_channel_id}")
                    cur.execute(
                        "SELECT * FROM main_clients_database WHERE open_channel_id = %s",
                        (open_channel_id,)
                    )
                    result = cur.fetchone()

                    if result:
                        columns = [desc[0] for desc in cur.description]
                        channel = dict(zip(columns, result))
                        print(f"✅ [DATABASE] Channel found: {channel['open_channel_title']}")
                        return channel
                    else:
                        print(f"❌ [DATABASE] Channel not found: {open_channel_id}")
                        return None
                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error fetching channel: {e}")
            return None

    def update_channel(self, open_channel_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update an existing channel's configuration.

        Args:
            open_channel_id: The channel ID to update
            update_data: Dictionary with fields to update

        Returns:
            True if update successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cur = conn.cursor()
                try:
                    # Build dynamic UPDATE query
                    set_clauses = []
                    values = []

                    for key, value in update_data.items():
                        if key != 'open_channel_id':  # Don't update primary key
                            set_clauses.append(f"{key} = %s")
                            values.append(value)

                    if not set_clauses:
                        print(f"⚠️ [DATABASE] No fields to update for channel: {open_channel_id}")
                        return False

                    # Add updated_at timestamp
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(open_channel_id)

                    query = f"""UPDATE main_clients_database
                                SET {', '.join(set_clauses)}
                                WHERE open_channel_id = %s"""

                    print(f"💾 [DATABASE] Updating channel: {open_channel_id}")
                    cur.execute(query, values)
                    conn.commit()

                    if cur.rowcount > 0:
                        print(f"✅ [DATABASE] Channel updated successfully")
                        return True
                    else:
                        print(f"❌ [DATABASE] No rows updated (channel not found?)")
                        return False

                finally:
                    cur.close()
        except Exception as e:
            print(f"❌ [DATABASE] Error updating channel: {e}")
            return False
```

### Modify insert_channel_registration Function

Find the `insert_channel_registration` function and ADD these two fields to the INSERT statement:

```python
# BEFORE (existing code):
INSERT INTO main_clients_database (
    open_channel_id,
    open_channel_title,
    # ... other fields ...
    client_wallet_address
) VALUES (...)

# AFTER (modified):
INSERT INTO main_clients_database (
    open_channel_id,
    client_id,              # NEW
    created_by,             # NEW
    open_channel_title,
    # ... other fields ...
    client_wallet_address
) VALUES (...)
```

**Important:** The `data` dictionary passed to this function must now include:
- `data['client_id']` - UUID from current_user.id
- `data['created_by']` - username from current_user.username

This will be handled in tpr10-26.py when calling this function.

---

## File 4: tpr10-26.py

**Location:** `OCTOBER/10-26/GCRegister10-26/tpr10-26.py`

### Add New Imports

At the top, modify imports:

```python
from flask import Flask, render_template, redirect, url_for, flash, session, request, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# ... existing imports ...
from forms import ChannelRegistrationForm, LoginForm, SignupForm  # Add LoginForm, SignupForm
```

### Initialize Flask-Login

Add this AFTER `db_manager` initialization:

```python
# Initialize database manager
try:
    db_manager = DatabaseManager(config)
    print("✅ [APP] Database manager initialized successfully")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    db_manager = None

# ==============================================================================
# Flask-Login Setup
# ==============================================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login if @login_required fails
login_manager.login_message = '🔒 Please log in to access this page.'
login_manager.login_message_category = 'info'

print("🔐 [APP] Flask-Login initialized")

class User(UserMixin):
    """
    User class for Flask-Login.
    Represents an authenticated user.
    """
    def __init__(self, user_id, username, email, is_active=True):
        self.id = user_id  # UUID string
        self.username = username
        self.email = email
        self.is_active = is_active

    def get_id(self):
        """Required by Flask-Login - return user ID as string."""
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    """
    Flask-Login callback to reload user from session.
    Called on every request for authenticated users.
    """
    if not db_manager:
        return None

    user_data = db_manager.get_user_by_id(user_id)
    if user_data and user_data['is_active']:
        return User(
            user_id=user_data['user_id'],
            username=user_data['username'],
            email=user_data['email'],
            is_active=user_data['is_active']
        )
    return None

print("✅ [APP] User loader registered")
```

### Modify Existing Routes

**Replace the entire `@app.route('/')` with:**

```python
@app.route('/')
def index():
    """
    Landing page - redirect based on authentication status.
    """
    print(f"🏠 [APP] Landing page accessed")

    if current_user.is_authenticated:
        print(f"👤 [APP] User {current_user.username} already logged in, redirecting to dashboard")
        return redirect(url_for('dashboard'))
    else:
        print(f"🔓 [APP] Anonymous user, redirecting to login")
        return redirect(url_for('login'))
```

### Add New Authentication Routes

Add these NEW routes BEFORE the existing `/health` route:

```python
# ==============================================================================
# Authentication Routes
# ==============================================================================

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    User registration route.
    """
    print(f"📝 [APP] Signup page accessed - Method: {request.method}")

    # Redirect if already logged in
    if current_user.is_authenticated:
        print(f"👤 [APP] User already logged in, redirecting to dashboard")
        return redirect(url_for('dashboard'))

    if not db_manager:
        flash('❌ Service temporarily unavailable. Please try again later.', 'danger')
        return render_template('error.html', error="Database connection unavailable")

    form = SignupForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        password = form.password.data

        print(f"👤 [APP] Signup attempt: {username} ({email})")

        # Hash password
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        print(f"🔐 [APP] Password hashed successfully")

        # Create user
        user_id = db_manager.create_user(username, email, password_hash)

        if user_id:
            print(f"✅ [APP] User created successfully: {username}")
            flash(f'✅ Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            print(f"❌ [APP] User creation failed (duplicate username/email?)")
            flash('❌ Username or email already exists. Please choose different credentials.', 'danger')

    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login route.
    """
    print(f"🔐 [APP] Login page accessed - Method: {request.method}")

    # Redirect if already logged in
    if current_user.is_authenticated:
        print(f"👤 [APP] User already logged in, redirecting to dashboard")
        return redirect(url_for('dashboard'))

    if not db_manager:
        flash('❌ Service temporarily unavailable. Please try again later.', 'danger')
        return render_template('error.html', error="Database connection unavailable")

    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        print(f"🔐 [APP] Login attempt: {username}")

        # Get user from database
        user_data = db_manager.get_user_by_username(username)

        if user_data:
            # Check password
            if check_password_hash(user_data['password_hash'], password):
                # Check if account is active
                if user_data['is_active']:
                    # Create User object
                    user = User(
                        user_id=user_data['user_id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        is_active=user_data['is_active']
                    )

                    # Log in user
                    login_user(user)

                    # Update last login timestamp
                    db_manager.update_last_login(user_data['user_id'])

                    print(f"✅ [APP] Login successful: {username}")
                    flash(f'✅ Welcome back, {username}!', 'success')

                    # Redirect to next page or dashboard
                    next_page = request.args.get('next')
                    return redirect(next_page) if next_page else redirect(url_for('dashboard'))
                else:
                    print(f"❌ [APP] Account inactive: {username}")
                    flash('❌ Your account has been deactivated. Please contact support.', 'danger')
            else:
                print(f"❌ [APP] Invalid password for user: {username}")
                flash('❌ Invalid username or password.', 'danger')
        else:
            print(f"❌ [APP] User not found: {username}")
            flash('❌ Invalid username or password.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """
    User logout route.
    """
    username = current_user.username
    print(f"🔓 [APP] Logout: {username}")

    logout_user()
    flash('✅ You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# ==============================================================================
# Channel Management Routes
# ==============================================================================

@app.route('/channels')
@login_required
def dashboard():
    """
    Channel management dashboard.
    Shows all channels owned by the logged-in user.
    """
    print(f"📊 [APP] Dashboard accessed by: {current_user.username}")

    if not db_manager:
        flash('❌ Service temporarily unavailable. Please try again later.', 'danger')
        return render_template('error.html', error="Database connection unavailable")

    # Get user's channels
    channels = db_manager.get_channels_by_client(current_user.id)
    channel_count = len(channels)

    print(f"📊 [APP] User has {channel_count} channel(s)")

    return render_template(
        'dashboard.html',
        channels=channels,
        channel_count=channel_count,
        max_channels=10
    )


@app.route('/channels/add', methods=['GET', 'POST'])
@login_required
def add_channel():
    """
    Add new channel route (authenticated users only).
    """
    print(f"➕ [APP] Add channel page accessed by: {current_user.username}")

    if not db_manager:
        flash('❌ Service temporarily unavailable. Please try again later.', 'danger')
        return render_template('error.html', error="Database connection unavailable")

    # Check 10-channel limit
    channel_count = db_manager.count_channels_by_client(current_user.id)
    if channel_count >= 10:
        print(f"⚠️ [APP] User {current_user.username} has reached 10-channel limit")
        flash('❌ Maximum 10 channels per account. Please delete a channel before adding a new one.', 'danger')
        return redirect(url_for('dashboard'))

    form = ChannelRegistrationForm()

    # Generate CAPTCHA on GET request or if not in session
    if request.method == 'GET' or 'captcha_answer' not in session:
        captcha_question, captcha_answer = generate_captcha()
        session['captcha_answer'] = captcha_answer
        session['captcha_question'] = captcha_question
        print(f"🔐 [APP] CAPTCHA generated: {captcha_question}")

    if form.validate_on_submit():
        print("✅ [APP] Form validation passed")

        # Verify CAPTCHA
        user_captcha = form.captcha.data.strip()
        correct_captcha = session.get('captcha_answer', '')

        if user_captcha != correct_captcha:
            print(f"❌ [APP] CAPTCHA verification failed")
            flash('❌ Incorrect CAPTCHA answer. Please try again.', 'danger')

            # Generate new CAPTCHA
            captcha_question, captcha_answer = generate_captcha()
            session['captcha_answer'] = captcha_answer
            session['captcha_question'] = captcha_question

            return render_template(
                'add_channel.html',
                form=form,
                captcha_question=session.get('captcha_question'),
                channel_count=channel_count,
                max_channels=10
            )

        print("✅ [APP] CAPTCHA verified successfully")

        # Get tier count and validate (same logic as before)
        tier_count = int(request.form.get('tier_count', 3))
        # ... tier validation logic (same as original register route) ...

        # Prepare registration data with client_id and created_by
        registration_data = {
            'client_id': current_user.id,           # NEW: Link to user account
            'created_by': current_user.username,    # NEW: Audit trail
            'open_channel_id': form.open_channel_id.data,
            'open_channel_title': form.open_channel_title.data,
            'open_channel_description': form.open_channel_description.data,
            'closed_channel_id': form.closed_channel_id.data,
            'closed_channel_title': form.closed_channel_title.data,
            'closed_channel_description': form.closed_channel_description.data,
            'sub_1_price': form.sub_1_price.data if tier_count >= 1 else None,
            'sub_1_time': form.sub_1_time.data if tier_count >= 1 else None,
            'sub_2_price': form.sub_2_price.data if tier_count >= 2 else None,
            'sub_2_time': form.sub_2_time.data if tier_count >= 2 else None,
            'sub_3_price': form.sub_3_price.data if tier_count == 3 else None,
            'sub_3_time': form.sub_3_time.data if tier_count == 3 else None,
            'client_wallet_address': form.client_wallet_address.data,
            'client_payout_currency': form.client_payout_currency.data,
            'client_payout_network': form.client_payout_network.data
            # Add payout_strategy and payout_threshold_usd if threshold payout implemented
        }

        # Insert into database
        success = db_manager.insert_channel_registration(registration_data)

        if success:
            print(f"✅ [APP] Channel registered successfully: {form.open_channel_id.data}")
            flash('✅ Channel registered successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            print(f"❌ [APP] Channel registration failed")
            flash('❌ Channel registration failed. Please try again.', 'danger')

    return render_template(
        'add_channel.html',
        form=form,
        captcha_question=session.get('captcha_question'),
        channel_count=channel_count,
        max_channels=10
    )


@app.route('/channels/<open_channel_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_channel(open_channel_id):
    """
    Edit existing channel route (owner only).
    """
    print(f"✏️ [APP] Edit channel page accessed: {open_channel_id} by {current_user.username}")

    if not db_manager:
        flash('❌ Service temporarily unavailable. Please try again later.', 'danger')
        return render_template('error.html', error="Database connection unavailable")

    # Get channel from database
    channel = db_manager.get_channel_by_id(open_channel_id)

    if not channel:
        print(f"❌ [APP] Channel not found: {open_channel_id}")
        abort(404, "Channel not found")

    # Authorization check - verify ownership
    if str(channel['client_id']) != str(current_user.id):
        print(f"❌ [APP] Unauthorized edit attempt by {current_user.username}")
        abort(403, "You don't have permission to edit this channel")

    # Pre-populate form with existing data
    form = ChannelRegistrationForm(data=channel)

    if form.validate_on_submit():
        print("✅ [APP] Edit form validation passed")

        # Get tier count
        tier_count = int(request.form.get('tier_count', 3))

        # Prepare update data (only editable fields)
        update_data = {
            'open_channel_title': form.open_channel_title.data,
            'open_channel_description': form.open_channel_description.data,
            'closed_channel_title': form.closed_channel_title.data,
            'closed_channel_description': form.closed_channel_description.data,
            'sub_1_price': form.sub_1_price.data if tier_count >= 1 else None,
            'sub_1_time': form.sub_1_time.data if tier_count >= 1 else None,
            'sub_2_price': form.sub_2_price.data if tier_count >= 2 else None,
            'sub_2_time': form.sub_2_time.data if tier_count >= 2 else None,
            'sub_3_price': form.sub_3_price.data if tier_count == 3 else None,
            'sub_3_time': form.sub_3_time.data if tier_count == 3 else None,
            'client_wallet_address': form.client_wallet_address.data,
            'client_payout_currency': form.client_payout_currency.data,
            'client_payout_network': form.client_payout_network.data
            # Add payout_strategy and payout_threshold_usd if threshold payout implemented
        }

        # Update in database
        success = db_manager.update_channel(open_channel_id, update_data)

        if success:
            print(f"✅ [APP] Channel updated successfully: {open_channel_id}")
            flash('✅ Channel updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            print(f"❌ [APP] Channel update failed")
            flash('❌ Channel update failed. Please try again.', 'danger')

    return render_template(
        'edit_channel.html',
        form=form,
        channel=channel,
        open_channel_id=open_channel_id
    )
```

### Update Health Check Route

The existing `/health` route remains unchanged.

---

## File 5: Templates - Create New Files

**Location:** `OCTOBER/10-26/GCRegister10-26/templates/`

### Create login.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - PayGate Prime</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6 col-lg-5">
                <div class="card shadow">
                    <div class="card-body">
                        <h2 class="card-title text-center mb-4">🔐 Login to PayGate Prime</h2>

                        <!-- Flash messages -->
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                        {{ message }}
                                        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                                            <span aria-hidden="true">&times;</span>
                                        </button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST" action="{{ url_for('login') }}">
                            {{ form.hidden_tag() }}

                            <div class="form-group">
                                {{ form.username.label(class="form-label") }}
                                {{ form.username(class="form-control" + (" is-invalid" if form.username.errors else "")) }}
                                {% if form.username.errors %}
                                    <div class="invalid-feedback">
                                        {% for error in form.username.errors %}
                                            {{ error }}
                                        {% endfor %}
                                    </div>
                                {% endif %}
                            </div>

                            <div class="form-group">
                                {{ form.password.label(class="form-label") }}
                                {{ form.password(class="form-control" + (" is-invalid" if form.password.errors else "")) }}
                                {% if form.password.errors %}
                                    <div class="invalid-feedback">
                                        {% for error in form.password.errors %}
                                            {{ error }}
                                        {% endfor %}
                                    </div>
                                {% endif %}
                            </div>

                            <button type="submit" class="btn btn-primary btn-block">Login</button>
                        </form>

                        <hr>

                        <p class="text-center mb-0">
                            Don't have an account? <a href="{{ url_for('signup') }}">Sign up here</a>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
```

### Create signup.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign Up - PayGate Prime</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6 col-lg-5">
                <div class="card shadow">
                    <div class="card-body">
                        <h2 class="card-title text-center mb-4">📝 Create Account</h2>

                        <!-- Flash messages -->
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                        {{ message }}
                                        <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                                            <span aria-hidden="true">&times;</span>
                                        </button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST" action="{{ url_for('signup') }}">
                            {{ form.hidden_tag() }}

                            <div class="form-group">
                                {{ form.username.label(class="form-label") }}
                                {{ form.username(class="form-control" + (" is-invalid" if form.username.errors else "")) }}
                                {% if form.username.errors %}
                                    <div class="invalid-feedback">
                                        {% for error in form.username.errors %}
                                            {{ error }}
                                        {% endfor %}
                                    </div>
                                {% endif %}
                            </div>

                            <div class="form-group">
                                {{ form.email.label(class="form-label") }}
                                {{ form.email(class="form-control" + (" is-invalid" if form.email.errors else "")) }}
                                {% if form.email.errors %}
                                    <div class="invalid-feedback">
                                        {% for error in form.email.errors %}
                                            {{ error }}
                                        {% endfor %}
                                    </div>
                                {% endif %}
                            </div>

                            <div class="form-group">
                                {{ form.password.label(class="form-label") }}
                                {{ form.password(class="form-control" + (" is-invalid" if form.password.errors else "")) }}
                                {% if form.password.errors %}
                                    <div class="invalid-feedback">
                                        {% for error in form.password.errors %}
                                            {{ error }}
                                        {% endfor %}
                                    </div>
                                {% endif %}
                                <small class="form-text text-muted">
                                    Must be 8+ characters with uppercase, lowercase, and number
                                </small>
                            </div>

                            <div class="form-group">
                                {{ form.password_confirm.label(class="form-label") }}
                                {{ form.password_confirm(class="form-control" + (" is-invalid" if form.password_confirm.errors else "")) }}
                                {% if form.password_confirm.errors %}
                                    <div class="invalid-feedback">
                                        {% for error in form.password_confirm.errors %}
                                            {{ error }}
                                        {% endfor %}
                                    </div>
                                {% endif %}
                            </div>

                            <button type="submit" class="btn btn-success btn-block">Create Account</button>
                        </form>

                        <hr>

                        <p class="text-center mb-0">
                            Already have an account? <a href="{{ url_for('login') }}">Login here</a>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
```

### Create dashboard.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Channel Dashboard - PayGate Prime</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <style>
        .channel-card {
            margin-bottom: 20px;
        }
        .channel-card .card-header {
            background-color: #007bff;
            color: white;
            font-weight: bold;
        }
        .tier-info {
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('dashboard') }}">💳 PayGate Prime</a>
            <div class="navbar-nav ml-auto">
                <span class="navbar-text text-white mr-3">
                    👤 {{ current_user.username }}
                </span>
                <a class="btn btn-outline-light btn-sm" href="{{ url_for('logout') }}">Logout</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="row">
            <div class="col-12">
                <h2>📊 Your Channels ({{ channel_count }}/{{ max_channels }})</h2>
                <hr>

                <!-- Flash messages -->
                {% with messages = get_flashed_messages(with_categories=true) %}
                    {% if messages %}
                        {% for category, message in messages %}
                            <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
                                {{ message }}
                                <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                                    <span aria-hidden="true">&times;</span>
                                </button>
                            </div>
                        {% endfor %}
                    {% endif %}
                {% endwith %}

                <!-- Add Channel Button -->
                {% if channel_count < max_channels %}
                    <div class="mb-4">
                        <a href="{{ url_for('add_channel') }}" class="btn btn-success">
                            ➕ Add New Channel ({{ max_channels - channel_count }} slots remaining)
                        </a>
                    </div>
                {% else %}
                    <div class="alert alert-warning">
                        ⚠️ You have reached the maximum of {{ max_channels }} channels per account.
                    </div>
                {% endif %}

                <!-- Channels List -->
                {% if channels %}
                    {% for channel in channels %}
                        <div class="card channel-card">
                            <div class="card-header">
                                📢 {{ channel.open_channel_title }}
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6>Open Channel</h6>
                                        <p><strong>ID:</strong> <code>{{ channel.open_channel_id }}</code></p>
                                        <p><strong>Description:</strong> {{ channel.open_channel_description }}</p>
                                    </div>
                                    <div class="col-md-6">
                                        <h6>🔒 Closed Channel</h6>
                                        <p><strong>ID:</strong> <code>{{ channel.closed_channel_id }}</code></p>
                                        <p><strong>Title:</strong> {{ channel.closed_channel_title }}</p>
                                    </div>
                                </div>

                                <hr>

                                <h6>💰 Subscription Tiers</h6>
                                <div class="row">
                                    {% if channel.sub_1_price %}
                                        <div class="col-md-4">
                                            <div class="tier-info">
                                                <strong>Tier 1 (Gold)</strong><br>
                                                ${{ "%.2f"|format(channel.sub_1_price) }} for {{ channel.sub_1_time }} days
                                            </div>
                                        </div>
                                    {% endif %}
                                    {% if channel.sub_2_price %}
                                        <div class="col-md-4">
                                            <div class="tier-info">
                                                <strong>Tier 2 (Silver)</strong><br>
                                                ${{ "%.2f"|format(channel.sub_2_price) }} for {{ channel.sub_2_time }} days
                                            </div>
                                        </div>
                                    {% endif %}
                                    {% if channel.sub_3_price %}
                                        <div class="col-md-4">
                                            <div class="tier-info">
                                                <strong>Tier 3 (Bronze)</strong><br>
                                                ${{ "%.2f"|format(channel.sub_3_price) }} for {{ channel.sub_3_time }} days
                                            </div>
                                        </div>
                                    {% endif %}
                                </div>

                                <hr>

                                <div class="row">
                                    <div class="col-md-6">
                                        <h6>💳 Payout Configuration</h6>
                                        <p><strong>Currency:</strong> {{ channel.client_payout_currency }}</p>
                                        <p><strong>Network:</strong> {{ channel.client_payout_network }}</p>
                                        <p><strong>Wallet:</strong> <code>{{ channel.client_wallet_address[:20] }}...</code></p>

                                        {% if channel.payout_strategy %}
                                            <p><strong>Strategy:</strong>
                                                {% if channel.payout_strategy == 'threshold' %}
                                                    🎯 Threshold (${{ "%.2f"|format(channel.payout_threshold_usd) }})
                                                {% else %}
                                                    ⚡ Instant
                                                {% endif %}
                                            </p>
                                        {% endif %}
                                    </div>
                                    <div class="col-md-6">
                                        <h6>📅 Metadata</h6>
                                        <p><strong>Created:</strong> {{ channel.created_at.strftime('%Y-%m-%d %H:%M') if channel.created_at else 'N/A' }}</p>
                                        {% if channel.updated_at %}
                                            <p><strong>Last Updated:</strong> {{ channel.updated_at.strftime('%Y-%m-%d %H:%M') }}</p>
                                        {% endif %}
                                    </div>
                                </div>

                                <div class="mt-3">
                                    <a href="{{ url_for('edit_channel', open_channel_id=channel.open_channel_id) }}"
                                       class="btn btn-primary">
                                        ✏️ Edit Channel
                                    </a>
                                </div>
                            </div>
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="alert alert-info">
                        📭 You don't have any channels yet. Click "Add New Channel" to get started!
                    </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.2/dist/umd/popper.min.js"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
</body>
</html>
```

### Create add_channel.html and edit_channel.html

**add_channel.html** - Copy the existing `register.html` and make these changes:
1. Change page title to "Add New Channel"
2. Change form action to `{{ url_for('add_channel') }}`
3. Add navigation bar (same as dashboard.html)
4. Add "Back to Dashboard" link
5. Show channel count: "Adding channel (X/10)"

**edit_channel.html** - Copy `add_channel.html` and make these changes:
1. Change page title to "Edit Channel"
2. Change form action to `{{ url_for('edit_channel', open_channel_id=open_channel_id) }}`
3. Make channel IDs read-only (disabled inputs)
4. Remove CAPTCHA field (not needed for editing)

**Note:** Full template code for these two files is provided in the next section of this guide for completeness.

---

## Testing Checklist

After applying all modifications, test the following:

### 1. User Registration Flow
- [ ] Navigate to www.paygateprime.com (redirects to /login)
- [ ] Click "Sign up here"
- [ ] Fill signup form with valid data
- [ ] Submit → Success message
- [ ] Try to signup with same username → Error message
- [ ] Try to signup with same email → Error message
- [ ] Verify password validation (uppercase, lowercase, digit)

### 2. Login Flow
- [ ] Login with created credentials → Success
- [ ] Verify redirect to /channels dashboard
- [ ] Check navbar shows username
- [ ] Try login with wrong password → Error
- [ ] Try login with non-existent user → Error

### 3. Dashboard
- [ ] Dashboard shows "0/10" channels initially
- [ ] "Add New Channel" button visible
- [ ] Logout button works
- [ ] Redirects to login after logout

### 4. Add Channel
- [ ] Click "Add New Channel"
- [ ] Fill form with valid channel data
- [ ] Submit → Success message
- [ ] Redirect to dashboard
- [ ] Verify channel appears in dashboard
- [ ] Verify `client_id` stored in database

### 5. Edit Channel
- [ ] Click "Edit Channel" on existing channel
- [ ] Form pre-populated with current values
- [ ] Channel IDs are read-only
- [ ] Modify tier prices
- [ ] Submit → Success message
- [ ] Verify changes in dashboard
- [ ] Verify `updated_at` timestamp updated

### 6. Authorization
- [ ] Try to edit another user's channel (manually enter URL) → 403 error
- [ ] Try to access /channels without login → Redirect to /login
- [ ] Try to access /channels/add without login → Redirect to /login

### 7. Channel Limit
- [ ] Add 10 channels to account
- [ ] "Add New Channel" button disabled
- [ ] Warning message shown
- [ ] Try to POST to /channels/add directly → 403 error

### 8. Database Integrity
- [ ] Verify `client_id` foreign key works
- [ ] Query: `SELECT * FROM main_clients_database WHERE client_id = '<user_uuid>'`
- [ ] Verify all channels have correct `client_id`
- [ ] Verify `created_by` populated
- [ ] Verify `updated_at` updates on edit

---

## Integration with Threshold Payout

If you have already implemented threshold payout (GCREGISTER_MODIFICATIONS_GUIDE.md), you need to:

1. **Add threshold fields to add_channel.html and edit_channel.html**
   - Copy the payout strategy section from GCREGISTER_MODIFICATIONS_GUIDE.md
   - Add JavaScript show/hide logic for threshold field

2. **Update forms.py**
   - Ensure ChannelRegistrationForm has payout_strategy and payout_threshold_usd fields

3. **Update add_channel and edit_channel routes**
   - Include payout_strategy and payout_threshold_usd in registration_data and update_data

4. **Update dashboard.html**
   - Display threshold accumulation status (if available)
   - Show progress toward threshold

---

## Summary

**Files Modified:** 4
- requirements.txt (added Flask-Login)
- forms.py (added LoginForm, SignupForm)
- database_manager.py (added 10 new functions)
- tpr10-26.py (complete restructure with new routes)

**Files Created:** 4
- templates/login.html
- templates/signup.html
- templates/dashboard.html
- templates/add_channel.html (modified copy of register.html)
- templates/edit_channel.html (modified copy of add_channel.html)

**Database Changes:** Required
- Must run DB_MIGRATION_USER_ACCOUNTS.md first

**Next Steps:**
1. Apply all modifications from this guide
2. Run DB_MIGRATION_USER_ACCOUNTS.md in PostgreSQL
3. Test signup/login flow
4. Test channel creation and editing
5. Deploy to Cloud Run

---

**Document Status:** ✅ Complete Implementation Guide
**Estimated Implementation Time:** 4-6 hours
**Risk Level:** Medium (significant changes to core functionality)
**Backward Compatibility:** Yes (existing channels assigned to legacy_system user)

---

**Related Documentation:**
- `USER_ACCOUNT_MANAGEMENT_ARCHITECTURE.md` - Architecture design
- `DB_MIGRATION_USER_ACCOUNTS.md` - Database migration
- `GCREGISTER_MODIFICATIONS_GUIDE.md` - Threshold payout UI modifications
- `DEPLOYMENT_GUIDE_USER_ACCOUNTS.md` - Deployment instructions (to be created)
