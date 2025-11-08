#!/usr/bin/env python
"""
GCRegister10-5: Channel Registration Service
Flask web application for registering Telegram channels into the payment system.
"""
from flask import Flask, render_template, redirect, url_for, flash, session, request
# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
import random
from config_manager import ConfigManager
from database_manager import DatabaseManager
from forms import ChannelRegistrationForm

# Initialize Flask app
app = Flask(__name__)

# Initialize configuration
print("🚀 [APP] Initializing GCRegister10-5 Channel Registration Service")
config_manager = ConfigManager()
config = config_manager.initialize_config()

# Configure Flask app
app.config['SECRET_KEY'] = config['secret_key']
app.config['WTF_CSRF_ENABLED'] = True

# Initialize database manager
try:
    db_manager = DatabaseManager(config)
    print("✅ [APP] Database manager initialized successfully")
except Exception as e:
    print(f"❌ [APP] Failed to initialize database manager: {e}")
    db_manager = None

# ============================================================================
# RATE LIMITING - TEMPORARILY DISABLED FOR TESTING
# ============================================================================
# NOTE: Rate limiting is commented out to allow unlimited testing.
# Uncomment the code below to re-enable rate limiting in production.
#
# Initialize rate limiter (5 registrations per hour per IP)
# limiter = Limiter(
#     app=app,
#     key_func=get_remote_address,
#     default_limits=["200 per day", "50 per hour"],
#     storage_uri="memory://"
# )
# print("🔒 [APP] Rate limiter initialized")
# ============================================================================

print("⚠️ [APP] Rate limiting is DISABLED for testing purposes")


def generate_captcha():
    """
    Generate a simple math-based CAPTCHA.

    Returns:
        Tuple of (question, answer)
    """
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    question = f"What is {num1} + {num2}?"
    answer = str(num1 + num2)
    return question, answer


@app.route('/', methods=['GET', 'POST'])
# @limiter.limit("5 per hour")  # DISABLED FOR TESTING
def register():
    """
    Main registration page route.
    Handles both GET (display form) and POST (process form) requests.
    """
    print(f"📝 [APP] Registration page accessed - Method: {request.method}")

    # Check if database manager is available
    if not db_manager:
        flash('❌ Service temporarily unavailable. Please try again later.', 'danger')
        return render_template('error.html', error="Database connection unavailable")

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
            print(f"❌ [APP] CAPTCHA verification failed: {user_captcha} != {correct_captcha}")
            flash('❌ Incorrect CAPTCHA answer. Please try again.', 'danger')

            # Generate new CAPTCHA
            captcha_question, captcha_answer = generate_captcha()
            session['captcha_answer'] = captcha_answer
            session['captcha_question'] = captcha_question

            return render_template(
                'register.html',
                form=form,
                captcha_question=session.get('captcha_question')
            )

        print("✅ [APP] CAPTCHA verified successfully")

        # Prepare data for database insertion
        registration_data = {
            'open_channel_id': form.open_channel_id.data.strip(),
            'open_channel_title': form.open_channel_title.data.strip(),
            'open_channel_description': form.open_channel_description.data.strip(),
            'closed_channel_id': form.closed_channel_id.data.strip(),
            'closed_channel_title': form.closed_channel_title.data.strip(),
            'closed_channel_description': form.closed_channel_description.data.strip(),
            'sub_1_price': float(form.sub_1_price.data),
            'sub_1_time': int(form.sub_1_time.data),
            'sub_2_price': float(form.sub_2_price.data),
            'sub_2_time': int(form.sub_2_time.data),
            'sub_3_price': float(form.sub_3_price.data),
            'sub_3_time': int(form.sub_3_time.data),
            'client_wallet_address': form.client_wallet_address.data.strip(),
            'client_payout_currency': form.client_payout_currency.data.upper()
        }

        print(f"📦 [APP] Prepared registration data for channel: {registration_data['open_channel_id']}")

        # Insert into database
        try:
            success = db_manager.insert_channel_registration(registration_data)

            if success:
                print(f"🎉 [APP] Registration successful for channel: {registration_data['open_channel_id']}")

                # Clear CAPTCHA from session
                session.pop('captcha_answer', None)
                session.pop('captcha_question', None)

                # Store registration details in session for success page
                session['registered_channel_id'] = registration_data['open_channel_id']
                session['registered_channel_title'] = registration_data['open_channel_title']

                return redirect(url_for('success'))
            else:
                print(f"❌ [APP] Registration failed for channel: {registration_data['open_channel_id']}")
                flash('❌ Registration failed. The channel ID may already be registered.', 'danger')

                # Generate new CAPTCHA
                captcha_question, captcha_answer = generate_captcha()
                session['captcha_answer'] = captcha_answer
                session['captcha_question'] = captcha_question

        except Exception as e:
            print(f"❌ [APP] Unexpected error during registration: {e}")
            flash('❌ An unexpected error occurred. Please try again.', 'danger')

            # Generate new CAPTCHA
            captcha_question, captcha_answer = generate_captcha()
            session['captcha_answer'] = captcha_answer
            session['captcha_question'] = captcha_question

    else:
        # Form validation failed
        if request.method == 'POST':
            print(f"❌ [APP] Form validation failed: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{error}', 'danger')

    return render_template(
        'register.html',
        form=form,
        captcha_question=session.get('captcha_question')
    )


@app.route('/success')
def success():
    """
    Success page after successful registration.
    """
    channel_id = session.get('registered_channel_id', 'Unknown')
    channel_title = session.get('registered_channel_title', 'Unknown')

    print(f"✅ [APP] Success page displayed for channel: {channel_id}")

    # Clear registration data from session
    session.pop('registered_channel_id', None)
    session.pop('registered_channel_title', None)

    return render_template(
        'success.html',
        channel_id=channel_id,
        channel_title=channel_title
    )


@app.route('/health')
def health():
    """
    Health check endpoint for monitoring.
    """
    try:
        # Test database connection
        if db_manager and db_manager.test_connection():
            return {
                'status': 'healthy',
                'service': 'GCRegister10-5 Channel Registration',
                'database': 'connected'
            }, 200
        else:
            return {
                'status': 'unhealthy',
                'service': 'GCRegister10-5 Channel Registration',
                'database': 'disconnected'
            }, 503
    except Exception as e:
        print(f"❌ [APP] Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'service': 'GCRegister10-5 Channel Registration',
            'error': str(e)
        }, 503


# ============================================================================
# RATE LIMIT ERROR HANDLER - DISABLED FOR TESTING
# ============================================================================
# @app.errorhandler(429)
# def ratelimit_handler(e):
#     """
#     Handle rate limit exceeded errors.
#     """
#     print(f"⚠️ [APP] Rate limit exceeded: {get_remote_address()}")
#     flash('⚠️ Too many registration attempts. Please try again later.', 'warning')
#     return render_template('error.html', error="Rate limit exceeded"), 429
# ============================================================================


@app.errorhandler(500)
def internal_error(e):
    """
    Handle internal server errors.
    """
    print(f"❌ [APP] Internal server error: {e}")
    return render_template('error.html', error="Internal server error"), 500


# --- Flask entrypoint for deployment ---
if __name__ == "__main__":
    print("🚀 [APP] Starting GCRegister10-5 on port 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
