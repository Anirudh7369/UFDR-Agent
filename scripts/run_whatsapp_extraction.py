#!/usr/bin/env python3
"""
Standalone script to run WhatsApp extraction from a UFDR file.

Usage:
    python scripts/run_whatsapp_extraction.py <path_to_ufdr_file> <upload_id>

Example:
    python scripts/run_whatsapp_extraction.py realtime/uploads/ufdr_files/report.ufdr test-upload-001
"""

import sys
import os
import asyncio
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from realtime.worker.ufdr_whatsapp_extractor import UFDRWhatsAppExtractor
from realtime.utils.db import whatsapp_operations
from dotenv import load_dotenv

# Load environment variables
load_dotenv('realtime/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


async def main():
    """Main execution function."""
    if len(sys.argv) < 3:
        print("Usage: python scripts/run_whatsapp_extraction.py <ufdr_file_path> <upload_id>")
        print("\nExample:")
        print("  python scripts/run_whatsapp_extraction.py realtime/uploads/ufdr_files/report.ufdr test-001")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Verify file exists
    if not os.path.exists(ufdr_path):
        logger.error(f"UFDR file not found: {ufdr_path}")
        sys.exit(1)

    logger.info(f"Starting WhatsApp extraction from UFDR file")
    logger.info(f"  UFDR file: {ufdr_path}")
    logger.info(f"  Upload ID: {upload_id}")

    try:
        # Initialize database schema
        logger.info("Initializing WhatsApp database schema...")
        await whatsapp_operations.init_whatsapp_schema()
        logger.info("Schema initialized successfully")

        # Create extractor and run extraction
        logger.info("Creating extractor instance...")
        extractor = UFDRWhatsAppExtractor(ufdr_path, upload_id)

        logger.info("Starting extraction and database loading...")
        await extractor.extract_and_load(whatsapp_operations)

        logger.info("=" * 80)
        logger.info("WhatsApp extraction completed successfully!")
        logger.info("=" * 80)

        # Get extraction status
        status = await whatsapp_operations.get_extraction_status(upload_id)
        if status:
            logger.info(f"\nExtraction Summary:")
            logger.info(f"  Status: {status['extraction_status']}")
            logger.info(f"  Total messages: {status['total_messages']}")
            logger.info(f"  Processed: {status['processed_messages']}")
            logger.info(f"  Started: {status['started_at']}")
            logger.info(f"  Completed: {status['completed_at']}")

        # Get sample messages
        logger.info("\nFetching sample messages...")
        messages = await whatsapp_operations.get_whatsapp_messages(upload_id, limit=5)
        if messages:
            logger.info(f"\nSample Messages (first {len(messages)}):")
            for i, msg in enumerate(messages, 1):
                logger.info(f"\n  Message {i}:")
                logger.info(f"    Chat: {msg.get('chat_jid')}")
                logger.info(f"    From: {msg.get('sender_jid', 'Me' if msg.get('from_me') else 'Unknown')}")
                msg_text = msg.get('message_text') or ''
                logger.info(f"    Text: {msg_text[:100] if msg_text else '(no text)'}")
                logger.info(f"    Timestamp: {msg.get('timestamp_dt')}")

        # Get call logs
        logger.info("\nFetching call logs...")
        call_logs = await whatsapp_operations.get_whatsapp_call_logs(upload_id, limit=10)
        if call_logs:
            logger.info(f"\nCall Logs (first {len(call_logs)}):")
            for i, call in enumerate(call_logs, 1):
                logger.info(f"\n  Call {i}:")
                logger.info(f"    Type: {call.get('call_type')}")
                logger.info(f"    Direction: {'Outgoing' if call.get('from_me') else 'Incoming'}")
                logger.info(f"    Participant: {call.get('from_jid') or call.get('to_jid')}")
                logger.info(f"    Duration: {call.get('duration')} seconds")
                logger.info(f"    Status: {call.get('status')}")
                logger.info(f"    Timestamp: {call.get('timestamp_dt')}")

    except Exception as e:
        logger.error(f"Extraction failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
