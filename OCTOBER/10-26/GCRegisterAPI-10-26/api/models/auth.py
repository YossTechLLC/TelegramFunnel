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


class RefreshResponse(BaseModel):
    """Token refresh response"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 900
