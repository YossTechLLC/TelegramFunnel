#!/usr/bin/env python
"""
Currency Migration Utility for TelegramFunnel Database

This utility helps diagnose and fix client_payout_currency issues in the database.
It can identify invalid currency values (like "USD") and migrate them to valid token symbols.

Usage:
    python currency_migration_utility.py --check     # Check current currency distribution
    python currency_migration_utility.py --migrate --target LINK --dry-run    # Simulate migration to LINK
    python currency_migration_utility.py --migrate --target ETH               # Actually migrate USD to ETH
"""

import argparse
import sys
import os
from database import DatabaseManager

def main():
    parser = argparse.ArgumentParser(description='Currency Migration Utility for TelegramFunnel')
    parser.add_argument('--check', action='store_true', help='Check current currency distribution')
    parser.add_argument('--migrate', action='store_true', help='Migrate USD records to target currency')
    parser.add_argument('--target', default='ETH', help='Target currency for migration (default: ETH)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate migration without making changes')
    
    args = parser.parse_args()
    
    if not args.check and not args.migrate:
        parser.print_help()
        print("\n❌ ERROR: Must specify either --check or --migrate")
        sys.exit(1)
    
    try:
        # Initialize database manager
        print("🔧 [INFO] Initializing database manager...")
        db_manager = DatabaseManager()
        print("✅ [INFO] Database manager initialized successfully")
        
        if args.check:
            print("\n📊 [INFO] Checking currency distribution...")
            result = db_manager.get_currency_distribution()
            
            if result['success']:
                print(f"\n📈 [RESULTS] Total records: {result['total_records']}")
                print("💰 [DISTRIBUTION] Currency breakdown:")
                for currency, count in result['distribution'].items():
                    print(f"  - {currency}: {count} records")
                
                # Check for problematic currencies
                if "USD" in result['distribution']:
                    print(f"\n⚠️ [WARNING] Found {result['distribution']['USD']} records with 'USD' currency")
                    print("💡 [SUGGESTION] Run with --migrate to fix these records")
                
            else:
                print(f"❌ [ERROR] {result['error']}")
                sys.exit(1)
        
        if args.migrate:
            action = "DRY RUN" if args.dry_run else "MIGRATION"
            print(f"\n🔄 [INFO] Starting {action} to migrate USD records to {args.target}...")
            
            result = db_manager.migrate_usd_to_token_currency(
                target_currency=args.target,
                dry_run=args.dry_run
            )
            
            if result['success']:
                print(f"\n✅ [SUCCESS] {result['message']}")
                print(f"📊 [STATS] Found: {result['records_found']} records")
                print(f"📊 [STATS] Updated: {result['records_updated']} records")
                
                if args.dry_run and result['records_found'] > 0:
                    print(f"\n💡 [NEXT STEP] Run without --dry-run to apply changes:")
                    print(f"python {os.path.basename(__file__)} --migrate --target {args.target}")
                    
            else:
                print(f"❌ [ERROR] {result['error']}")
                sys.exit(1)
        
        print("\n🎉 [COMPLETE] Currency utility finished successfully")
        
    except Exception as e:
        print(f"❌ [FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()