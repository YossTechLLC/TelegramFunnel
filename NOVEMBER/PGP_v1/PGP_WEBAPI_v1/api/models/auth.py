#!/usr/bin/env python
"""
🔐 Authentication Models for GCRegisterAPI-10-26
Pydantic models for authentication requests and responses
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


class SignupRequest(BaseModel):
    """User signup request"""
    username: str
    email: EmailStr
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Validate username format"""
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Username must be between 3 and 50 characters')
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


class LoginRequest(BaseModel):
    """User login request"""
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class AuthResponse(BaseModel):
    """Authentication response"""
    user_id: str
    username: str
    email: str
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # 15 minutes
    email_verified: bool = False  # NEW: Email verification status
    verification_required: bool = False  # NEW: Whether verification is needed


class RefreshResponse(BaseModel):
    """Token refresh response"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


class SignupResponse(BaseModel):
    """Signup response (email verification required)"""
    success: bool
    message: str
    user_id: str
    email: str
    email_verified: bool = False
    verification_required: bool = True


class ResendVerificationRequest(BaseModel):
    """Request to resend verification email"""
    email: EmailStr


class VerifyEmailResponse(BaseModel):
    """Email verification response"""
    success: bool
    message: str
    redirect_url: str = "/login"


class GenericMessageResponse(BaseModel):
    """Generic success/error message response"""
    success: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    """Password reset request"""
    email: EmailStr
    recaptcha_token: Optional[str] = None  # Optional reCAPTCHA token


class ResetPasswordRequest(BaseModel):
    """Password reset with new password"""
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validate new password strength (reuse signup validation)"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


# ============================================================================
# NEW MODELS FOR VERIFICATION & ACCOUNT MANAGEMENT (Phase 3)
# ============================================================================

class VerificationStatusResponse(BaseModel):
    """Detailed email verification status for current user"""
    email_verified: bool
    email: str
    verification_token_expires: Optional[str] = None  # ISO format datetime
    can_resend: bool
    last_resent_at: Optional[str] = None  # ISO format datetime
    resend_count: int = 0


class EmailChangeRequest(BaseModel):
    """Request to change email address (requires verified account + password)"""
    new_email: EmailStr
    password: str

    @field_validator('new_email')
    @classmethod
    def validate_new_email(cls, v):
        """Ensure email format is valid"""
        # EmailStr already validates format, but we can add custom checks
        if len(v) > 255:
            raise ValueError('Email address too long')
        return v.lower()  # Normalize to lowercase


class EmailChangeResponse(BaseModel):
    """Response after requesting email change"""
    success: bool
    message: str
    pending_email: str
    notification_sent_to_old: bool
    confirmation_sent_to_new: bool


class PasswordChangeRequest(BaseModel):
    """Request to change password (requires verified account + current password)"""
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v):
        """Validate new password strength (same rules as signup)"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


class PasswordChangeResponse(BaseModel):
    """Response after password change"""
    success: bool
    message: str
