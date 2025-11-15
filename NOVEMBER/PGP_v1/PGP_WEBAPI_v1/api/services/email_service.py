#!/usr/bin/env python
"""
📧 Email Service for GCRegisterAPI-10-26
Handles sending verification and password reset emails via SendGrid

This service sends professional, responsive HTML emails for:
- Email verification (24-hour expiration)
- Password reset requests (1-hour expiration)
- Password reset confirmations

Features:
- SendGrid integration with fallback to dev mode
- Responsive HTML email templates
- Dev mode console logging for testing
- Comprehensive error handling
"""

import os
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content


class EmailService:
    """Handles email operations for authentication flows"""

    def __init__(self):
        """
        Initialize email service

        Loads configuration from environment variables:
        - SENDGRID_API_KEY: SendGrid API key (required for production)
        - FROM_EMAIL: Sender email address (default: noreply@telepay.com)
        - FROM_NAME: Sender display name (default: TelePay)
        - BASE_URL: Base URL for email links (default: https://app.telepay.com)

        If SENDGRID_API_KEY is not set, service operates in dev mode (console only).
        """
        self.sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@telepay.com')
        self.from_name = os.getenv('FROM_NAME', 'TelePay')
        self.base_url = os.getenv('BASE_URL', 'https://app.telepay.com')

        if not self.sendgrid_api_key:
            print("⚠️  SENDGRID_API_KEY not set - email sending disabled (DEV MODE)")

    def send_verification_email(
        self,
        to_email: str,
        username: str,
        token: str
    ) -> bool:
        """
        Send email verification email

        Args:
            to_email: Recipient email address
            username: User's username for personalization
            token: Verification token to embed in link

        Returns:
            True if sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = service.send_verification_email(
            ...     'user@example.com',
            ...     'johndoe',
            ...     'eyJhbGci...'
            ... )
        """
        verification_url = f"{self.base_url}/verify-email?token={token}"

        # Dev mode: Print to console instead of sending
        if not self.sendgrid_api_key:
            print(f"\n{'='*70}")
            print(f"📧 [DEV MODE] Email Verification")
            print(f"{'='*70}")
            print(f"To: {to_email}")
            print(f"Subject: Verify Your Email - {self.from_name}")
            print(f"Username: {username}")
            print(f"Verification URL: {verification_url}")
            print(f"Token: {token}")
            print(f"{'='*70}\n")
            return True

        # Production: Send via SendGrid
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject=f"Verify Your Email - {self.from_name}",
            html_content=self._get_verification_email_template(
                username,
                verification_url
            )
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Verification email sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send verification email: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending verification email to {to_email}: {e}")
            return False

    def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        token: str
    ) -> bool:
        """
        Send password reset email

        Args:
            to_email: Recipient email address
            username: User's username for personalization
            token: Reset token to embed in link

        Returns:
            True if sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = service.send_password_reset_email(
            ...     'user@example.com',
            ...     'johndoe',
            ...     'eyJhbGci...'
            ... )
        """
        reset_url = f"{self.base_url}/reset-password?token={token}"

        # Dev mode: Print to console instead of sending
        if not self.sendgrid_api_key:
            print(f"\n{'='*70}")
            print(f"🔐 [DEV MODE] Password Reset Request")
            print(f"{'='*70}")
            print(f"To: {to_email}")
            print(f"Subject: Password Reset Request - {self.from_name}")
            print(f"Username: {username}")
            print(f"Reset URL: {reset_url}")
            print(f"Token: {token}")
            print(f"{'='*70}\n")
            return True

        # Production: Send via SendGrid
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject=f"Password Reset Request - {self.from_name}",
            html_content=self._get_password_reset_email_template(
                username,
                reset_url
            )
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Password reset email sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send reset email: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending reset email to {to_email}: {e}")
            return False

    def send_password_reset_confirmation_email(
        self,
        to_email: str,
        username: str
    ) -> bool:
        """
        Send confirmation email after successful password reset

        This is a security notification to alert users of password changes.

        Args:
            to_email: Recipient email address
            username: User's username for personalization

        Returns:
            True if sent successfully, False otherwise

        Example:
            >>> service = EmailService()
            >>> success = service.send_password_reset_confirmation_email(
            ...     'user@example.com',
            ...     'johndoe'
            ... )
        """
        # Dev mode: Print to console instead of sending
        if not self.sendgrid_api_key:
            print(f"\n{'='*70}")
            print(f"✅ [DEV MODE] Password Reset Confirmation")
            print(f"{'='*70}")
            print(f"To: {to_email}")
            print(f"Subject: Password Reset Successful - {self.from_name}")
            print(f"Username: {username}")
            print(f"{'='*70}\n")
            return True

        # Production: Send via SendGrid
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject=f"Password Reset Successful - {self.from_name}",
            html_content=self._get_password_reset_confirmation_template(username)
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Reset confirmation email sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send confirmation email: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending confirmation email to {to_email}: {e}")
            return False

    @staticmethod
    def _get_verification_email_template(username: str, verification_url: str) -> str:
        """
        Get HTML template for verification email

        Responsive design with gradient header and clear CTA button.

        Args:
            username: User's username
            verification_url: Full URL with verification token

        Returns:
            HTML email content as string
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Welcome to TelePay! 🎉</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>Thanks for signing up! Please verify your email address to activate your account.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}"
                       style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>

                <p style="color: #666; font-size: 14px;">
                    This link will expire in <strong>24 hours</strong>.
                </p>

                <p style="color: #666; font-size: 14px;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{verification_url}" style="color: #667eea; word-break: break-all;">{verification_url}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #999; font-size: 12px;">
                    If you didn't create this account, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_password_reset_email_template(username: str, reset_url: str) -> str:
        """
        Get HTML template for password reset email

        Responsive design with security warnings.

        Args:
            username: User's username
            reset_url: Full URL with reset token

        Returns:
            HTML email content as string
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Password Reset Request 🔐</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>We received a request to reset your password. Click the button below to create a new password:</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}"
                       style="background: #f5576c; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Reset Password
                    </a>
                </div>

                <p style="color: #666; font-size: 14px;">
                    This link will expire in <strong>1 hour</strong>.
                </p>

                <p style="color: #666; font-size: 14px;">
                    If the button doesn't work, copy and paste this link into your browser:<br>
                    <a href="{reset_url}" style="color: #f5576c; word-break: break-all;">{reset_url}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #999; font-size: 12px;">
                    If you didn't request a password reset, please ignore this email or contact support if you have concerns.
                </p>
            </div>
        </body>
        </html>
        """

    def send_email_change_notification(
        self,
        to_email: str,
        username: str,
        new_email: str
    ) -> bool:
        """
        Send notification to OLD email address when email change is requested

        This is a security notification to alert users of email change attempts.

        Args:
            to_email: Current/old email address
            username: User's username
            new_email: New email address being requested

        Returns:
            True if sent successfully, False otherwise
        """
        # Dev mode: Print to console instead of sending
        if not self.sendgrid_api_key:
            print(f"\n{'='*70}")
            print(f"🔔 [DEV MODE] Email Change Notification (to OLD email)")
            print(f"{'='*70}")
            print(f"To: {to_email}")
            print(f"Subject: Email Change Request - {self.from_name}")
            print(f"Username: {username}")
            print(f"New Email: {new_email}")
            print(f"{'='*70}\n")
            return True

        # Production: Send via SendGrid
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject=f"Email Change Request - {self.from_name}",
            html_content=self._get_email_change_notification_template(username, new_email)
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Email change notification sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send notification: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending notification to {to_email}: {e}")
            return False

    def send_email_change_confirmation(
        self,
        to_email: str,
        username: str,
        confirmation_url: str
    ) -> bool:
        """
        Send confirmation email to NEW email address with confirmation link

        Args:
            to_email: New email address to be confirmed
            username: User's username
            confirmation_url: Full URL with email change token

        Returns:
            True if sent successfully, False otherwise
        """
        # Dev mode: Print to console instead of sending
        if not self.sendgrid_api_key:
            print(f"\n{'='*70}")
            print(f"📧 [DEV MODE] Email Change Confirmation (to NEW email)")
            print(f"{'='*70}")
            print(f"To: {to_email}")
            print(f"Subject: Confirm Email Change - {self.from_name}")
            print(f"Username: {username}")
            print(f"Confirmation URL: {confirmation_url}")
            print(f"{'='*70}\n")
            return True

        # Production: Send via SendGrid
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject=f"Confirm Email Change - {self.from_name}",
            html_content=self._get_email_change_confirmation_template(username, confirmation_url)
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Email change confirmation sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send confirmation: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending confirmation to {to_email}: {e}")
            return False

    def send_email_change_success(
        self,
        to_email: str,
        username: str
    ) -> bool:
        """
        Send success notification to NEW email address after email change is complete

        Args:
            to_email: New email address (now active)
            username: User's username

        Returns:
            True if sent successfully, False otherwise
        """
        # Dev mode: Print to console instead of sending
        if not self.sendgrid_api_key:
            print(f"\n{'='*70}")
            print(f"✅ [DEV MODE] Email Change Success")
            print(f"{'='*70}")
            print(f"To: {to_email}")
            print(f"Subject: Email Change Successful - {self.from_name}")
            print(f"Username: {username}")
            print(f"{'='*70}\n")
            return True

        # Production: Send via SendGrid
        message = Mail(
            from_email=Email(self.from_email, self.from_name),
            to_emails=To(to_email),
            subject=f"Email Change Successful - {self.from_name}",
            html_content=self._get_email_change_success_template(username)
        )

        try:
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                print(f"✅ Email change success notification sent to {to_email}")
                return True
            else:
                print(f"❌ Failed to send success notification: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error sending success notification to {to_email}: {e}")
            return False

    @staticmethod
    def _get_password_reset_confirmation_template(username: str) -> str:
        """
        Get HTML template for password reset confirmation

        Security notification email after successful password change.

        Args:
            username: User's username

        Returns:
            HTML email content as string
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Password Reset Successful ✅</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>Your password has been successfully reset.</p>

                <p>You can now log in with your new password.</p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #d32f2f; font-size: 14px; font-weight: bold;">
                    ⚠️ If you did not make this change, please contact support immediately.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_email_change_notification_template(username: str, new_email: str) -> str:
        """Get HTML template for email change notification (to OLD email)"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Email Change Request 📧</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>We received a request to change your email address to:</p>

                <p style="text-align: center; font-size: 18px; background: #fff; padding: 15px; border-radius: 5px; font-weight: bold;">
                    {new_email}
                </p>

                <p>A confirmation email has been sent to the new address.</p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #d32f2f; font-size: 14px; font-weight: bold;">
                    ⚠️ If you did not request this change, please contact support immediately.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_email_change_confirmation_template(username: str, confirmation_url: str) -> str:
        """Get HTML template for email change confirmation (to NEW email)"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Confirm Email Change 🔐</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>Click the button below to confirm this email address for your TelePay account:</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{confirmation_url}"
                       style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Confirm Email Change
                    </a>
                </div>

                <p style="color: #666; font-size: 14px;">
                    This link will expire in <strong>1 hour</strong>.
                </p>

                <p style="color: #666; font-size: 14px;">
                    If the button doesn't work, copy and paste this link:<br>
                    <a href="{confirmation_url}" style="color: #667eea; word-break: break-all;">{confirmation_url}</a>
                </p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #999; font-size: 12px;">
                    If you didn't request this change, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _get_email_change_success_template(username: str) -> str:
        """Get HTML template for email change success (to NEW email)"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Email Change Successful ✅</h1>
            </div>

            <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
                <p>Hi <strong>{username}</strong>,</p>

                <p>Your email address has been successfully updated!</p>

                <p>This is now your primary email for your TelePay account.</p>

                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">

                <p style="color: #666; font-size: 14px;">
                    You can now log in using this email address.
                </p>
            </div>
        </body>
        </html>
        """
