#!/usr/bin/env python
"""
Form definitions for GCRegister10-5 Channel Registration Service.
Uses Flask-WTF for form handling and validation.
"""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from validators import (
    validate_channel_id,
    validate_price,
    validate_time,
    validate_wallet_address,
    validate_title,
    validate_description
)

class ChannelRegistrationForm(FlaskForm):
    """
    Form for channel registration with comprehensive validation.
    """

    # Open Channel Information
    open_channel_id = StringField(
        'Open Channel ID',
        validators=[
            DataRequired(message='❌ Open Channel ID is required'),
            Length(max=14, message='❌ Open Channel ID must be 14 characters or less'),
            validate_channel_id
        ],
        render_kw={
            'placeholder': 'e.g., -1001234567890',
            'class': 'form-control',
            'maxlength': '14'
        }
    )

    open_channel_title = StringField(
        'Open Channel Title',
        validators=[
            DataRequired(message='❌ Open Channel Title is required'),
            Length(min=1, max=100, message='❌ Title must be between 1 and 100 characters'),
            validate_title
        ],
        render_kw={
            'placeholder': 'e.g., Crypto Trading Signals',
            'class': 'form-control',
            'maxlength': '100'
        }
    )

    open_channel_description = TextAreaField(
        'Open Channel Description',
        validators=[
            DataRequired(message='❌ Open Channel Description is required'),
            Length(min=1, max=500, message='❌ Description must be between 1 and 500 characters'),
            validate_description
        ],
        render_kw={
            'placeholder': 'Brief description of your open channel content...',
            'class': 'form-control',
            'rows': '3',
            'maxlength': '500'
        }
    )

    # Closed Channel Information
    closed_channel_id = StringField(
        'Closed Channel ID',
        validators=[
            DataRequired(message='❌ Closed Channel ID is required'),
            Length(max=14, message='❌ Closed Channel ID must be 14 characters or less'),
            validate_channel_id
        ],
        render_kw={
            'placeholder': 'e.g., -1001234567891',
            'class': 'form-control',
            'maxlength': '14'
        }
    )

    closed_channel_title = StringField(
        'Closed Channel Title',
        validators=[
            DataRequired(message='❌ Closed Channel Title is required'),
            Length(min=1, max=100, message='❌ Title must be between 1 and 100 characters'),
            validate_title
        ],
        render_kw={
            'placeholder': 'e.g., Premium Trading Signals',
            'class': 'form-control',
            'maxlength': '100'
        }
    )

    closed_channel_description = TextAreaField(
        'Closed Channel Description',
        validators=[
            DataRequired(message='❌ Closed Channel Description is required'),
            Length(min=1, max=500, message='❌ Description must be between 1 and 500 characters'),
            validate_description
        ],
        render_kw={
            'placeholder': 'Brief description of your premium content...',
            'class': 'form-control',
            'rows': '3',
            'maxlength': '500'
        }
    )

    # Subscription Tier 1 (Gold - Premium)
    # NOTE: Fields are optional - validation occurs based on selected tier count
    sub_1_price = DecimalField(
        'Tier 1 Price (USD)',
        validators=[
            Optional(),
            NumberRange(min=0, max=9999.99, message='❌ Price must be between $0.00 and $9999.99'),
            validate_price
        ],
        places=2,
        render_kw={
            'placeholder': 'e.g., 49.99',
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'max': '9999.99'
        }
    )

    sub_1_time = IntegerField(
        'Tier 1 Duration (Days)',
        validators=[
            Optional(),
            NumberRange(min=1, max=999, message='❌ Duration must be between 1 and 999 days'),
            validate_time
        ],
        render_kw={
            'placeholder': 'e.g., 365',
            'class': 'form-control',
            'min': '1',
            'max': '999'
        }
    )

    # Subscription Tier 2 (Silver - Mid-tier)
    # NOTE: Fields are optional - validation occurs based on selected tier count
    sub_2_price = DecimalField(
        'Tier 2 Price (USD)',
        validators=[
            Optional(),
            NumberRange(min=0, max=9999.99, message='❌ Price must be between $0.00 and $9999.99'),
            validate_price
        ],
        places=2,
        render_kw={
            'placeholder': 'e.g., 24.99',
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'max': '9999.99'
        }
    )

    sub_2_time = IntegerField(
        'Tier 2 Duration (Days)',
        validators=[
            Optional(),
            NumberRange(min=1, max=999, message='❌ Duration must be between 1 and 999 days'),
            validate_time
        ],
        render_kw={
            'placeholder': 'e.g., 90',
            'class': 'form-control',
            'min': '1',
            'max': '999'
        }
    )

    # Subscription Tier 3 (Bronze - Basic)
    # NOTE: Fields are optional - validation occurs based on selected tier count
    sub_3_price = DecimalField(
        'Tier 3 Price (USD)',
        validators=[
            Optional(),
            NumberRange(min=0, max=9999.99, message='❌ Price must be between $0.00 and $9999.99'),
            validate_price
        ],
        places=2,
        render_kw={
            'placeholder': 'e.g., 9.99',
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'max': '9999.99'
        }
    )

    sub_3_time = IntegerField(
        'Tier 3 Duration (Days)',
        validators=[
            Optional(),
            NumberRange(min=1, max=999, message='❌ Duration must be between 1 and 999 days'),
            validate_time
        ],
        render_kw={
            'placeholder': 'e.g., 30',
            'class': 'form-control',
            'min': '1',
            'max': '999'
        }
    )

    # Client Payment Information
    client_payout_network = SelectField(
        'Network Type',
        validators=[
            DataRequired(message='❌ Network type is required')
        ],
        choices=[
            ('', '-- Select Network --')
        ],
        validate_choice=False,  # Allow dynamic choices from JavaScript/database
        render_kw={
            'class': 'form-select',
            'id': 'client_payout_network'
        }
    )

    client_payout_currency = SelectField(
        'Payout Currency',
        validators=[
            DataRequired(message='❌ Payout currency is required')
        ],
        choices=[
            ('', '-- Select Currency --')
        ],
        validate_choice=False,  # Allow dynamic choices from JavaScript/database
        render_kw={
            'class': 'form-select',
            'id': 'client_payout_currency'
        }
    )

    client_wallet_address = StringField(
        'Wallet Address',
        validators=[
            DataRequired(message='❌ Wallet address is required'),
            Length(min=1, max=110, message='❌ Wallet address must be between 1 and 110 characters'),
            validate_wallet_address
        ],
        render_kw={
            'placeholder': 'e.g., 0x1234567890abcdef...',
            'class': 'form-control',
            'maxlength': '110'
        }
    )

    # CAPTCHA (simple math-based)
    captcha = StringField(
        'CAPTCHA Answer',
        validators=[
            DataRequired(message='❌ CAPTCHA answer is required')
        ],
        render_kw={
            'placeholder': 'Enter the answer',
            'class': 'form-control',
            'autocomplete': 'off'
        }
    )

    # Submit button
    submit = SubmitField(
        'Register Channel',
        render_kw={
            'class': 'btn btn-primary btn-lg w-100'
        }
    )
