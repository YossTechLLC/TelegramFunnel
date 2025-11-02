#!/usr/bin/env python3
"""
Generic package verification script - Research-first approach
Usage: python3 verify_package.py <package-name> [import-name]

Examples:
    python3 verify_package.py playwright
    python3 verify_package.py google-cloud-logging google.cloud.logging
"""

import sys
import subprocess
import importlib

def verify_package(package_name, import_name=None):
    """
    Verify package installation using research-first methodology.

    Args:
        package_name: pip package name (e.g., 'google-cloud-logging')
        import_name: Python import name (e.g., 'google.cloud.logging')

    Returns:
        bool: True if package is installed and importable
    """
    if import_name is None:
        # Common pattern: hyphens -> underscores
        import_name = package_name.replace('-', '_')

    print(f"🔍 Verifying: {package_name}")
    print("=" * 60)

    # STEP 1: Check installation via pip (NO ASSUMPTIONS)
    print("\n📦 Step 1: Checking installation metadata...")
    result = subprocess.run(
        ['pip3', 'show', package_name],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Package '{package_name}' not installed")
        print(f"\nInstall with: pip3 install {package_name}")
        return False

    # Extract key metadata
    metadata = {}
    for line in result.stdout.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip()

    print(f"✅ Installed: {metadata.get('Version', 'unknown')}")
    print(f"📍 Location: {metadata.get('Location', 'unknown')}")
    if metadata.get('Requires'):
        print(f"📌 Requires: {metadata.get('Requires')}")

    # STEP 2: Test import
    print(f"\n🐍 Step 2: Testing import '{import_name}'...")
    try:
        module = importlib.import_module(import_name)
        print(f"✅ Import successful: {import_name}")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print(f"\n💡 Hint: Package name might not match import name")
        print(f"   Try: python3 -c 'import {package_name.replace('-', '_')}'")
        return False

    # STEP 3: Inspect module structure
    print(f"\n🔍 Step 3: Inspecting module structure...")

    # Check for __version__
    if hasattr(module, '__version__'):
        print(f"✅ Module __version__: {module.__version__}")
    else:
        print(f"ℹ️  No __version__ attribute (use 'pip show' for version)")

    # Show public attributes (sample)
    public_attrs = [a for a in dir(module) if not a.startswith('_')]
    if public_attrs:
        sample = public_attrs[:8]
        print(f"📋 Public attributes (sample): {', '.join(sample)}")
        if len(public_attrs) > 8:
            print(f"   ... and {len(public_attrs) - 8} more")

    # STEP 4: Check for CLI tools
    print(f"\n🔧 Step 4: Checking for CLI tools...")
    files_result = subprocess.run(
        ['pip3', 'show', '-f', package_name],
        capture_output=True,
        text=True
    )

    cli_tools = []
    in_files_section = False
    for line in files_result.stdout.split('\n'):
        if line.startswith('Files:'):
            in_files_section = True
            continue
        if in_files_section and 'bin/' in line:
            tool = line.strip().split('/')[-1]
            cli_tools.append(tool)

    if cli_tools:
        print(f"✅ CLI tools found: {', '.join(cli_tools[:5])}")
        if cli_tools:
            print(f"   Usage: python3 -m {package_name.replace('-', '_')}")
    else:
        print(f"ℹ️  No CLI tools installed")

    # FINAL SUMMARY
    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE")
    print(f"   Package: {package_name} v{metadata.get('Version', 'unknown')}")
    print(f"   Import:  {import_name}")
    print(f"   Status:  Functional")
    print("=" * 60)

    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: verify_package.py <package-name> [import-name]")
        print("\nExamples:")
        print("  python3 verify_package.py playwright")
        print("  python3 verify_package.py google-cloud-logging google.cloud.logging")
        sys.exit(1)

    package = sys.argv[1]
    import_name = sys.argv[2] if len(sys.argv) > 2 else None

    success = verify_package(package, import_name)
    sys.exit(0 if success else 1)
