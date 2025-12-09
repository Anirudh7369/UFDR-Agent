#!/usr/bin/env python3
"""
Test script for UFDR Installed Apps extraction.

Usage:
    python scripts/run_apps_extraction.py <ufdr_file_path> <upload_id>

Example:
    python scripts/run_apps_extraction.py "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" test-001
"""

import sys
import os
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realtime.worker.ufdr_apps_extractor import UFDRAppsExtractor
from realtime.utils.db import apps_operations


async def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/run_apps_extraction.py <ufdr_file_path> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    print("=" * 80)
    print("UFDR Installed Apps Extraction Test")
    print("=" * 80)
    print(f"UFDR File: {ufdr_path}")
    print(f"Upload ID: {upload_id}")
    print()

    # Initialize schema
    print("[1/4] Initializing database schema...")
    try:
        await apps_operations.init_apps_schema()
        print("✓ Schema initialized successfully")
    except Exception as e:
        print(f"✗ Schema initialization failed: {e}")
        print("Note: If tables already exist, this is expected")

    print()

    # Run extraction
    print("[2/4] Starting extraction...")
    extractor = UFDRAppsExtractor(ufdr_path, upload_id)

    try:
        await extractor.extract_and_load(apps_operations)
        print("✓ Extraction completed successfully")
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()

    # Get extraction status
    print("[3/4] Retrieving extraction status...")
    status = await apps_operations.get_app_extraction_status(upload_id)
    if status:
        print(f"✓ Status: {status['extraction_status']}")
        print(f"  Total apps: {status['total_apps']}")
        print(f"  Processed apps: {status['processed_apps']}")
        if status.get('error_message'):
            print(f"  Error: {status['error_message']}")
    else:
        print("✗ No extraction status found")

    print()

    # Get and display statistics
    print("[4/4] Getting app statistics...")
    stats = await apps_operations.get_app_statistics(upload_id)

    print("=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total Apps: {stats['total_apps']}")
    print(f"Apps with Install Timestamps: {stats['apps_with_install_timestamps']}")
    print(f"First Install: {stats['first_install_date']}")
    print(f"Last Install: {stats['last_install_date']}")
    print()

    # Display top categories
    print("Top 10 Categories:")
    print("-" * 80)
    for i, cat in enumerate(stats['categories'][:10], 1):
        print(f"  {i}. {cat['category']}: {cat['count']} apps")
    print()

    # Display top permissions
    print("Top 10 Permissions:")
    print("-" * 80)
    for i, perm in enumerate(stats['permissions'][:10], 1):
        print(f"  {i}. {perm['permission_category']}: {perm['count']} apps")
    print()

    # Display sample apps
    print("Sample Installed Apps (10 most recent):")
    print("-" * 80)
    apps = await apps_operations.get_installed_apps(upload_id, limit=10)
    for i, app in enumerate(apps, 1):
        print(f"\n{i}. {app['app_name']}")
        print(f"   Package: {app['app_identifier']}")
        print(f"   Version: {app['app_version']}")
        if app['install_timestamp_dt']:
            print(f"   Installed: {app['install_timestamp_dt']}")
        if app['categories']:
            import json
            categories = json.loads(app['categories']) if isinstance(app['categories'], str) else app['categories']
            print(f"   Categories: {', '.join(categories)}")

    print()
    print("=" * 80)
    print("✓ Test completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
