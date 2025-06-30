#!/usr/bin/env python
"""
Environment Variable Validation Script
Checks all required environment variables for telepay30.py and tph30.py
"""
import os
from google.cloud import secretmanager
from typing import Dict, List, Tuple

def check_environment_variable(var_name: str) -> Tuple[bool, str]:
    """Check if environment variable is set and return its value."""
    value = os.getenv(var_name)
    if not value:
        return False, f"❌ {var_name} is not set"
    return True, f"✅ {var_name} is set: {value[:50]}..." if len(value) > 50 else f"✅ {var_name} is set: {value}"

def check_secret_access(secret_path: str, var_name: str) -> Tuple[bool, str]:
    """Check if the secret can be accessed from Google Secret Manager."""
    if not secret_path:
        return False, f"❌ {var_name}: No secret path provided"
    
    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_path})
        secret_value = response.payload.data.decode("UTF-8")
        return True, f"✅ {var_name}: Secret accessible (length: {len(secret_value)})"
    except Exception as e:
        return False, f"❌ {var_name}: Secret access failed - {e}"

def main():
    print("🔍 Environment Variable Validation for TelegramFunnel/30")
    print("=" * 60)
    
    # Required environment variables for telepay30.py
    telepay_vars = [
        "TELEGRAM_BOT_SECRET_NAME",
        "TELEGRAM_BOT_USERNAME", 
        "NOWPAYMENT_WEBHOOK_KEY",
        "DATABASE_HOST_SECRET",
        "DATABASE_NAME_SECRET",
        "DATABASE_USER_SECRET",
        "DATABASE_PASSWORD_SECRET",
        "CHANGENOW_API_KEY",
        "HOST_WALLET_ETH_ADDRESS",
        "HOST_WALLET_PRIVATE_KEY"
    ]
    
    # Required environment variables for tph30.py
    webhook_vars = [
        "TELEGRAM_BOT_SECRET_NAME",
        "SUCCESS_URL_SIGNING_KEY",
        "DATABASE_NAME_SECRET",
        "DATABASE_USER_SECRET", 
        "DATABASE_PASSWORD_SECRET",
        "CLOUD_SQL_CONNECTION_NAME",
        "TPS30_WEBHOOK_URL",
        "TPBTCS1_WEBHOOK_URL",
        "CHANGENOW_API_KEY",
        "HOST_WALLET_ETH_ADDRESS",
        "HOST_WALLET_PRIVATE_KEY"
    ]
    
    # Check telepay30.py environment variables
    print("\\n📱 TELEPAY30.PY Environment Variables:")
    print("-" * 40)
    
    all_telepay_good = True
    for var in telepay_vars:
        is_set, message = check_environment_variable(var)
        print(message)
        if not is_set:
            all_telepay_good = False
        elif var not in ["CLOUD_SQL_CONNECTION_NAME", "TPS30_WEBHOOK_URL", "TPBTCS1_WEBHOOK_URL"]:
            # Test secret access for Secret Manager variables
            secret_path = os.getenv(var)
            if secret_path and secret_path.startswith("projects/"):
                is_accessible, secret_message = check_secret_access(secret_path, var)
                print(f"    {secret_message}")
                if not is_accessible:
                    all_telepay_good = False
    
    # Check tph30.py environment variables  
    print("\\n🌐 TPH30.PY Environment Variables:")
    print("-" * 40)
    
    all_webhook_good = True
    for var in webhook_vars:
        is_set, message = check_environment_variable(var)
        print(message)
        if not is_set:
            all_webhook_good = False
        elif var not in ["CLOUD_SQL_CONNECTION_NAME", "TPS30_WEBHOOK_URL", "TPBTCS1_WEBHOOK_URL"]:
            # Test secret access for Secret Manager variables
            secret_path = os.getenv(var)
            if secret_path and secret_path.startswith("projects/"):
                is_accessible, secret_message = check_secret_access(secret_path, var)
                print(f"    {secret_message}")
                if not is_accessible:
                    all_webhook_good = False
    
    # Summary
    print("\\n" + "=" * 60)
    print("📋 SUMMARY:")
    
    if all_telepay_good:
        print("✅ telepay30.py: All environment variables are properly configured")
    else:
        print("❌ telepay30.py: Some environment variables need attention")
    
    if all_webhook_good:
        print("✅ tph30.py: All environment variables are properly configured")
    else:
        print("❌ tph30.py: Some environment variables need attention")
    
    # Common issues and suggestions
    print("\\n🔧 COMMON FIXES:")
    print("-" * 40)
    print("1. If 'Secret not found' errors occur:")
    print("   - Check secret names in Google Secret Manager")
    print("   - Ensure IAM permissions for Secret Manager access")
    print("   - Verify project ID in secret paths")
    print("\\n2. If 'Environment variable not set' errors occur:")
    print("   - Run 'source ~/.profile' to load environment variables")
    print("   - Check .profile file for typos")
    print("\\n3. For HOST_WALLET_PRIVATE_KEY_SECRET errors:")
    print("   - Either create 'HOST_WALLET_PRIVATE_KEY_SECRET' secret")
    print("   - Or update .profile to point to existing secret name")

if __name__ == "__main__":
    main()