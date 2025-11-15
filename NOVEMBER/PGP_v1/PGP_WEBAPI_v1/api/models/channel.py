#!/usr/bin/env python
"""
📺 Channel Models for GCRegisterAPI-10-26
Pydantic models for channel registration and management
"""
from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal


class ChannelRegistrationRequest(BaseModel):
    """Channel registration request"""
    # Open Channel
    open_channel_id: str
    open_channel_title: str
    open_channel_description: str

    # Closed Channel
    closed_channel_id: str
    closed_channel_title: str
    closed_channel_description: str
    closed_channel_donation_message: str  # Custom donation message (10-256 chars)

    # Subscription Tiers
    tier_count: int
    sub_1_price: Decimal
    sub_1_time: int
    sub_2_price: Optional[Decimal] = None
    sub_2_time: Optional[int] = None
    sub_3_price: Optional[Decimal] = None
    sub_3_time: Optional[int] = None

    # Payment Configuration
    client_wallet_address: str
    client_payout_currency: str
    client_payout_network: str

    # Threshold Payout (from THRESHOLD_PAYOUT_ARCHITECTURE)
    payout_strategy: str = 'instant'
    payout_threshold_usd: Optional[Decimal] = None

    # 🆕 Notification Configuration (from NOTIFICATION_MANAGEMENT_ARCHITECTURE)
    notification_status: bool = False
    notification_id: Optional[int] = None

    @field_validator('open_channel_id', 'closed_channel_id')
    @classmethod
    def validate_channel_id(cls, v):
        """Validate Telegram channel ID format"""
        if not v.startswith('-100'):
            raise ValueError('Channel ID must start with -100')
        if len(v) < 10 or len(v) > 14:
            raise ValueError('Channel ID must be between 10 and 14 characters')
        return v

    @field_validator('tier_count')
    @classmethod
    def validate_tier_count(cls, v):
        """Validate tier count"""
        if v not in [1, 2, 3]:
            raise ValueError('Tier count must be 1, 2, or 3')
        return v

    @field_validator('payout_strategy')
    @classmethod
    def validate_payout_strategy(cls, v):
        """Validate payout strategy"""
        if v not in ['instant', 'threshold']:
            raise ValueError('Payout strategy must be instant or threshold')
        return v

    @field_validator('closed_channel_donation_message')
    @classmethod
    def validate_donation_message(cls, v):
        """Validate donation message is not empty and within length limit"""
        if not v or not v.strip():
            raise ValueError('Donation message cannot be empty')
        if len(v) > 256:
            raise ValueError('Donation message cannot exceed 256 characters')
        if len(v.strip()) < 10:
            raise ValueError('Donation message must be at least 10 characters')
        return v.strip()  # Remove leading/trailing whitespace

    @field_validator('notification_id')
    @classmethod
    def validate_notification_id(cls, v, info):
        """Validate notification_id when notifications enabled"""
        notification_status = info.data.get('notification_status', False)

        if notification_status:
            # Notifications enabled - ID is required
            if v is None:
                raise ValueError('notification_id required when notifications enabled')
            if v <= 0:
                raise ValueError('notification_id must be positive')
            # Telegram user IDs are typically 9-10 digits, but support range 5-15
            if len(str(v)) < 5 or len(str(v)) > 15:
                raise ValueError('Invalid Telegram ID format (must be 5-15 digits)')

        return v

    def model_post_init(self, __context):
        """Validate tier-dependent fields"""
        # Tier 2 required if tier_count >= 2
        if self.tier_count >= 2:
            if self.sub_2_price is None or self.sub_2_time is None:
                raise ValueError('Tier 2 price and time required when tier_count >= 2')

        # Tier 3 required if tier_count == 3
        if self.tier_count == 3:
            if self.sub_3_price is None or self.sub_3_time is None:
                raise ValueError('Tier 3 price and time required when tier_count = 3')

        # Threshold required if strategy = threshold
        if self.payout_strategy == 'threshold':
            if self.payout_threshold_usd is None or self.payout_threshold_usd <= 0:
                raise ValueError('Threshold amount required and must be positive when strategy is threshold')


class ChannelUpdateRequest(BaseModel):
    """Channel update request (partial update allowed)"""
    open_channel_title: Optional[str] = None
    open_channel_description: Optional[str] = None
    closed_channel_title: Optional[str] = None
    closed_channel_description: Optional[str] = None
    closed_channel_donation_message: Optional[str] = None

    # NOTE: tier_count is not updatable - it's calculated dynamically from sub_X_price fields
    sub_1_price: Optional[Decimal] = None
    sub_1_time: Optional[int] = None
    sub_2_price: Optional[Decimal] = None
    sub_2_time: Optional[int] = None
    sub_3_price: Optional[Decimal] = None
    sub_3_time: Optional[int] = None

    client_wallet_address: Optional[str] = None
    client_payout_currency: Optional[str] = None
    client_payout_network: Optional[str] = None

    payout_strategy: Optional[str] = None
    payout_threshold_usd: Optional[Decimal] = None

    # 🆕 Notification Configuration (from NOTIFICATION_MANAGEMENT_ARCHITECTURE)
    notification_status: Optional[bool] = None
    notification_id: Optional[int] = None

    @field_validator('closed_channel_donation_message')
    @classmethod
    def validate_donation_message(cls, v):
        """Validate donation message if provided"""
        if v is not None:
            if not v.strip():
                raise ValueError('Donation message cannot be empty')
            if len(v) > 256:
                raise ValueError('Donation message cannot exceed 256 characters')
            if len(v.strip()) < 10:
                raise ValueError('Donation message must be at least 10 characters')
            return v.strip()
        return v

    @field_validator('notification_id')
    @classmethod
    def validate_notification_id(cls, v, info):
        """Validate notification_id when notifications enabled"""
        notification_status = info.data.get('notification_status')

        # Only validate if notification_status is being set to True
        if notification_status is True and v is None:
            raise ValueError('notification_id required when enabling notifications')

        if v is not None:
            if v <= 0:
                raise ValueError('notification_id must be positive')
            if len(str(v)) < 5 or len(str(v)) > 15:
                raise ValueError('Invalid Telegram ID format (must be 5-15 digits)')

        return v


class ChannelResponse(BaseModel):
    """Channel data response"""
    open_channel_id: str
    open_channel_title: str
    open_channel_description: str
    closed_channel_id: str
    closed_channel_title: str
    closed_channel_description: str
    closed_channel_donation_message: str  # Custom donation message

    tier_count: int
    sub_1_price: Decimal
    sub_1_time: int
    sub_2_price: Optional[Decimal]
    sub_2_time: Optional[int]
    sub_3_price: Optional[Decimal]
    sub_3_time: Optional[int]

    client_wallet_address: str
    client_payout_currency: str
    client_payout_network: str

    payout_strategy: str
    payout_threshold_usd: Optional[Decimal]
    accumulated_amount: Optional[Decimal] = None  # For threshold strategy

    # 🆕 Notification Configuration (from NOTIFICATION_MANAGEMENT_ARCHITECTURE)
    notification_status: bool
    notification_id: Optional[int]

    created_at: str
    updated_at: Optional[str]
