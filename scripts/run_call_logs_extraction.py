"""
Test script for UFDR Call Logs extraction.

Usage:
    python scripts/run_call_logs_extraction.py <ufdr_file_path> <upload_id>

Example:
    python scripts/run_call_logs_extraction.py "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" test-calls-001
"""

import sys
import os
import asyncio

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from realtime.worker.ufdr_call_logs_extractor import UFDRCallLogsExtractor
from realtime.utils.db import call_logs_operations


async def main():
    """Main test function."""
    if len(sys.argv) < 3:
        print("Usage: python scripts/run_call_logs_extraction.py <ufdr_file_path> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    print("=" * 80)
    print("UFDR Call Logs Extraction Test")
    print("=" * 80)
    print(f"UFDR File: {ufdr_path}")
    print(f"Upload ID: {upload_id}")
    print()

    # Step 1: Initialize schema
    print("[1/4] Initializing database schema...")
    try:
        await call_logs_operations.init_call_logs_schema()
        print("✓ Schema initialized successfully")
    except Exception as e:
        print(f"✗ Schema initialization failed: {e}")
        sys.exit(1)

    print()

    # Step 2: Run extraction
    print("[2/4] Starting extraction...")
    try:
        extractor = UFDRCallLogsExtractor(ufdr_path, upload_id)
        await extractor.extract_and_load(call_logs_operations)
        print("✓ Extraction completed successfully")
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()

    # Step 3: Get extraction status
    print("[3/4] Retrieving extraction status...")
    try:
        status = await call_logs_operations.get_call_log_extraction_status(upload_id)
        if status:
            print(f"✓ Status: {status['extraction_status']}")
            print(f"  Total calls: {status['total_calls']}")
            print(f"  Processed calls: {status['processed_calls']}")
            if status.get('error_message'):
                print(f"  Error: {status['error_message']}")
        else:
            print("✗ No extraction status found")
    except Exception as e:
        print(f"✗ Failed to get status: {e}")

    print()

    # Step 4: Get statistics
    print("[4/4] Getting call log statistics...")
    try:
        stats = await call_logs_operations.get_call_log_statistics(upload_id)

        print("=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        print(f"Total Calls: {stats['total_calls']}")
        print(f"Video Calls: {stats['video_calls']}")
        print(f"Voice Calls: {stats['voice_calls']}")
        print(f"First Call: {stats['first_call_date']}")
        print(f"Last Call: {stats['last_call_date']}")
        print()

        # By app
        print("Calls by App:")
        print("-" * 80)
        for app_stat in stats['by_app'][:10]:
            print(f"  {app_stat['source_app']}: {app_stat['count']} calls")
        print()

        # By direction
        print("Calls by Direction:")
        print("-" * 80)
        for dir_stat in stats['by_direction']:
            print(f"  {dir_stat['direction']}: {dir_stat['count']} calls")
        print()

        # By status
        print("Calls by Status:")
        print("-" * 80)
        for status_stat in stats['by_status'][:5]:
            print(f"  {status_stat['status']}: {status_stat['count']} calls")
        print()

        # Sample calls
        print("Sample Call Logs (10 most recent):")
        print("-" * 80)
        calls = await call_logs_operations.get_call_logs(upload_id, limit=10)
        for i, call in enumerate(calls, 1):
            print(f"{i}. {call['source_app']} - {call['call_type']} ({call['direction']})")
            print(f"   Status: {call['status']}")
            if call['call_timestamp_dt']:
                print(f"   Time: {call['call_timestamp_dt']}")
            if call['duration_seconds']:
                print(f"   Duration: {call['duration_seconds']}s")
            print(f"   From: {call['from_party_name'] or call['from_party_identifier']}")
            print(f"   To: {call['to_party_name'] or call['to_party_identifier']}")
            print()

        print("=" * 80)
        print("✓ Test completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"✗ Failed to get statistics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
