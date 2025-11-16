#!/usr/bin/env python3
"""
Bulk Security Update Script for PayGatePrime v1
Applies OIDC authentication and security headers to all internal services
"""

import os
import re

# Base directory
BASE_DIR = "/home/user/TelegramFunnel/NOVEMBER/PGP_v1"

# Services to update (service_dir, main_file)
SERVICES = [
    ("GCSplit2-PGP", "tps2-10-26.py"),
    ("GCSplit3-PGP", "tps3-10-26.py"),
    ("GCHostPay1-PGP", "tphp1-10-26.py"),
    ("GCHostPay2-PGP", "tphp2-10-26.py"),
    ("GCHostPay3-PGP", "tphp3-10-26.py"),
    ("GCAccumulator-PGP", "acc10-26.py"),
    ("GCBatchProcessor-PGP", "batch10-26.py"),
    ("GCMicroBatchProcessor-PGP", "microbatch10-26.py"),
]

# Import statements to add
SECURITY_IMPORTS = """# Add common modules to path
sys.path.append('/workspace')
from common.oidc_auth import require_oidc_token, get_caller_identity
from common.security_headers import apply_internal_security
"""

# Security headers initialization
SECURITY_INIT = """
# Apply security headers (Flask-Talisman)
apply_internal_security(app)
"""

# OIDC caller logging
OIDC_LOG = """        # Log authenticated caller
        caller = get_caller_identity()
        caller_email = caller.get('email', 'unknown') if caller else 'unknown'
        print(f"🔐 [OIDC_AUTH] Authenticated caller: {caller_email}")
"""


def update_imports(file_path):
    """Add security imports to the file"""
    with open(file_path, 'r') as f:
        content = f.read()

    # Check if already updated
    if 'from common.oidc_auth import' in content:
        print(f"  ⏭️  Imports already updated")
        return False

    # Find the Flask import line and add security imports after it
    # Pattern: import sys might already exist, if not add it
    if 'import sys' not in content:
        content = content.replace('import time', 'import sys\nimport time', 1)

    # Add security imports after Flask import
    pattern = r'(from flask import .*?\n)'
    replacement = r'\1\n' + SECURITY_IMPORTS + '\n'
    content = re.sub(pattern, replacement, content, count=1)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"  ✅ Imports updated")
    return True


def add_security_headers_init(file_path):
    """Add security headers initialization after app = Flask(__name__)"""
    with open(file_path, 'r') as f:
        content = f.read()

    # Check if already added
    if 'apply_internal_security(app)' in content:
        print(f"  ⏭️  Security headers already initialized")
        return False

    # Add after app = Flask(__name__)
    pattern = r'(app = Flask\(__name__\))'
    replacement = r'\1' + SECURITY_INIT
    content = re.sub(pattern, replacement, content, count=1)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"  ✅ Security headers initialized")
    return True


def add_oidc_decorator_to_endpoints(file_path):
    """Add @require_oidc_token decorator to POST endpoints (except /health)"""
    with open(file_path, 'r') as f:
        content = f.read()

    # Count existing decorators
    existing_count = content.count('@require_oidc_token')
    if existing_count > 0:
        print(f"  ⏭️  {existing_count} OIDC decorators already present")
        return False

    # Find all @app.route POST endpoints except /health
    # Pattern: @app.route("...", methods=["POST"])
    # But NOT @app.route("/health"...)

    lines = content.split('\n')
    updated_lines = []
    i = 0

    added_count = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a route decorator
        if '@app.route(' in line and 'methods=["POST"]' in line:
            # Check if it's NOT /health
            if '/health' not in line:
                # Add OIDC decorator before the route
                updated_lines.append(line)
                updated_lines.append('@require_oidc_token')
                added_count += 1
                i += 1
                continue

        updated_lines.append(line)
        i += 1

    if added_count > 0:
        content = '\n'.join(updated_lines)
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  ✅ Added @require_oidc_token to {added_count} endpoints")
        return True
    else:
        print(f"  ⏭️  No POST endpoints found to decorate")
        return False


def add_requirements(service_dir):
    """Add security dependencies to requirements.txt"""
    req_file = os.path.join(BASE_DIR, service_dir, "requirements.txt")

    if not os.path.exists(req_file):
        print(f"  ⚠️  No requirements.txt found")
        return False

    with open(req_file, 'r') as f:
        content = f.read()

    # Check if already added
    if 'flask-talisman' in content and 'google-auth' in content:
        print(f"  ⏭️  Requirements already updated")
        return False

    lines = content.strip().split('\n')
    updated_lines = []

    for line in lines:
        updated_lines.append(line)
        # Add security deps after Flask line
        if line.startswith('Flask'):
            if 'flask-talisman' not in content:
                updated_lines.append('flask-talisman==1.1.0')
            if 'google-auth' not in content:
                updated_lines.append('google-auth==2.23.4')

    with open(req_file, 'w') as f:
        f.write('\n'.join(updated_lines) + '\n')

    print(f"  ✅ Requirements updated")
    return True


def process_service(service_dir, main_file):
    """Process a single service"""
    print(f"\n{'='*60}")
    print(f"Processing: {service_dir}/{main_file}")
    print(f"{'='*60}")

    file_path = os.path.join(BASE_DIR, service_dir, main_file)

    if not os.path.exists(file_path):
        print(f"  ❌ File not found: {file_path}")
        return False

    # Step 1: Update imports
    update_imports(file_path)

    # Step 2: Add security headers initialization
    add_security_headers_init(file_path)

    # Step 3: Add OIDC decorators to endpoints
    add_oidc_decorator_to_endpoints(file_path)

    # Step 4: Update requirements.txt
    add_requirements(service_dir)

    return True


def main():
    print("🔒 PayGatePrime v1 - Bulk Security Update")
    print("=" * 60)
    print(f"Base directory: {BASE_DIR}")
    print(f"Services to update: {len(SERVICES)}")
    print()

    success_count = 0
    for service_dir, main_file in SERVICES:
        if process_service(service_dir, main_file):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"✅ Completed: {success_count}/{len(SERVICES)} services updated")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
