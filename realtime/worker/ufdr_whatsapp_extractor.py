"""
UFDR WhatsApp Data Extractor

This module extracts WhatsApp data from UFDR files and inserts it into PostgreSQL.
It processes the msgstore.db and other WhatsApp SQLite databases found within UFDR archives.

Usage:
    Can be called directly or as an RQ worker job.
"""

import os
import tempfile
import shutil
import sqlite3
import zipfile
from typing import Dict, List, Any, Optional, Tuple
import logging
import asyncio
from datetime import datetime
import urllib.parse
import urllib.request
from dotenv import load_dotenv

# Load environment variables from .env file
# Get the realtime directory (parent of worker directory)
realtime_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(realtime_dir, '.env')

# Load .env file and verify it exists
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[ufdr_extractor] Loaded .env from: {env_path}")
else:
    print(f"[ufdr_extractor] WARNING: .env file not found at: {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UFDRWhatsAppExtractor:
    """
    Extracts WhatsApp data from UFDR files and loads it into PostgreSQL.
    Supports both local file paths and MinIO/S3 URLs.
    """

    def __init__(self, ufdr_path_or_url: str, upload_id: str):
        """
        Initialize the extractor.

        Args:
            ufdr_path_or_url: Path to the UFDR file or MinIO URL
            upload_id: Unique identifier for this upload/extraction
        """
        self.ufdr_source = ufdr_path_or_url
        self.upload_id = upload_id
        self.temp_dir = None
        self.extracted_dbs = []
        self.ufdr_path = None  # Will be set after download if URL
        self.is_url = self._is_url(ufdr_path_or_url)

    def _is_url(self, path: str) -> bool:
        """Check if the path is a URL."""
        return path.startswith('http://') or path.startswith('https://')

    def _download_from_url(self, url: str) -> str:
        """
        Download UFDR file from MinIO URL to temporary file.

        Args:
            url: MinIO URL to download from (format: http://host:port/bucket/key)

        Returns:
            str: Path to downloaded temporary file
        """
        try:
            logger.info(f"Downloading UFDR file from: {url}")

            # Parse the MinIO URL to extract bucket and key
            # Format: http://localhost:9000/bucket/key/path
            from urllib.parse import urlparse, unquote
            import boto3
            from botocore.client import Config

            parsed = urlparse(url)
            # Remove leading slash and split into bucket and key
            path_parts = parsed.path.lstrip('/').split('/', 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid MinIO URL format: {url}")

            bucket = path_parts[0]
            key = unquote(path_parts[1])  # URL decode the key

            logger.info(f"Parsed MinIO URL - Bucket: {bucket}, Key: {key}")

            # Create boto3 client with credentials from environment
            s3_endpoint = os.getenv("S3_ENDPOINT", "http://localhost:9000")
            s3_region = os.getenv("S3_REGION", "us-east-1")
            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

            s3 = boto3.client(
                "s3",
                endpoint_url=s3_endpoint,
                region_name=s3_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                config=Config(signature_version="s3v4"),
            )

            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.ufdr', prefix='ufdr_download_')
            os.close(temp_fd)

            # Download file using boto3
            logger.info(f"Downloading from S3: bucket={bucket}, key={key}")
            s3.download_file(bucket, key, temp_path)

            file_size = os.path.getsize(temp_path)
            logger.info(f"Downloaded UFDR file: {file_size} bytes to {temp_path}")

            return temp_path

        except Exception as e:
            logger.error(f"Failed to download UFDR file from URL: {e}", exc_info=True)
            raise

    def extract_whatsapp_databases(self) -> List[str]:
        """
        Extract WhatsApp SQLite databases from the UFDR file.
        Handles both local files and MinIO URLs.

        Returns:
            List of paths to extracted database files
        """
        # Download from URL if needed
        if self.is_url:
            self.ufdr_path = self._download_from_url(self.ufdr_source)
        else:
            self.ufdr_path = self.ufdr_source

        logger.info(f"Extracting WhatsApp databases from {self.ufdr_path}")

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix=f"ufdr_wa_{self.upload_id}_")
        logger.info(f"Created temp directory: {self.temp_dir}")

        db_files = []

        try:
            with zipfile.ZipFile(self.ufdr_path, 'r') as zf:
                # Find all WhatsApp related database files
                whatsapp_db_patterns = [
                    'msgstore.db',
                    'msgstore-',  # Backup databases
                    'wa.db',
                ]

                for file_info in zf.namelist():
                    # Check if file is a WhatsApp database
                    if 'files/Database/' in file_info:
                        basename = os.path.basename(file_info)
                        if any(pattern in basename for pattern in whatsapp_db_patterns):
                            logger.info(f"Found WhatsApp DB: {file_info}")

                            # Extract to temp directory
                            extracted_path = zf.extract(file_info, self.temp_dir)
                            db_files.append(extracted_path)

            self.extracted_dbs = db_files
            logger.info(f"Extracted {len(db_files)} WhatsApp database files")
            return db_files

        except Exception as e:
            logger.error(f"Error extracting databases: {e}", exc_info=True)
            raise

    def parse_sqlite_messages(self, db_path: str) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """
        Parse messages, chats, contacts, and call logs from a WhatsApp SQLite database.

        Args:
            db_path: Path to the SQLite database file

        Returns:
            Tuple of (messages, chats, contacts, call_logs)
        """
        logger.info(f"Parsing SQLite database: {db_path}")

        messages = []
        chats = []
        contacts = []
        call_logs = []

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check which schema this database uses
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
            has_messages_table = cursor.fetchone() is not None

            if has_messages_table:
                # Parse messages from 'messages' table (older WhatsApp schema)
                messages = self._parse_messages_table(cursor)
            else:
                # Try the newer schema with 'message' table
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message'")
                has_message_table = cursor.fetchone() is not None

                if has_message_table:
                    messages = self._parse_message_table(cursor)

            # Parse chats
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat'")
            if cursor.fetchone():
                chats = self._parse_chat_table(cursor)

            # Parse JIDs/contacts
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jid'")
            if cursor.fetchone():
                contacts = self._parse_jid_table(cursor)

            # Parse call logs
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='call_log'")
            if cursor.fetchone():
                call_logs = self._parse_call_log_table(cursor)

            conn.close()

            logger.info(f"Parsed {len(messages)} messages, {len(chats)} chats, {len(contacts)} contacts, {len(call_logs)} call logs")
            return messages, chats, contacts, call_logs

        except Exception as e:
            logger.error(f"Error parsing database {db_path}: {e}", exc_info=True)
            return [], [], [], []

    def _parse_messages_table(self, cursor: sqlite3.Cursor) -> List[Dict]:
        """Parse messages from the 'messages' table (older schema)."""
        messages = []

        try:
            # Query all messages
            cursor.execute("""
                SELECT
                    _id, key_remote_jid, key_from_me, key_id,
                    status, data, timestamp, media_url, media_mime_type,
                    media_wa_type, media_size, media_name, media_caption,
                    media_hash, media_duration, latitude, longitude,
                    remote_resource, received_timestamp, send_timestamp,
                    starred, quoted_row_id, forwarded, mentioned_jids
                FROM messages
                WHERE _id > 0
            """)

            for row in cursor.fetchall():
                # Helper to safely convert to int
                def safe_int(val, default=0):
                    if val is None:
                        return default
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return default

                msg = {
                    'msg_id': row['key_id'] or str(row['_id']),
                    'chat_jid': row['key_remote_jid'] or '',
                    'sender_jid': row['remote_resource'] if not row['key_from_me'] else None,
                    'from_me': safe_int(row['key_from_me']),
                    'message_text': row['data'],
                    'message_type': safe_int(row['media_wa_type']),
                    'timestamp': safe_int(row['timestamp'], None),
                    'received_timestamp': safe_int(row['received_timestamp'], None),
                    'send_timestamp': safe_int(row['send_timestamp'], None),
                    'status': safe_int(row['status']),
                    'starred': safe_int(row['starred']),
                    'media_url': row['media_url'],
                    'media_mimetype': row['media_mime_type'],
                    'media_size': safe_int(row['media_size'], None),
                    'media_name': row['media_name'],
                    'media_caption': row['media_caption'],
                    'media_hash': row['media_hash'],
                    'media_duration': safe_int(row['media_duration'], None),
                    'media_wa_type': str(row['media_wa_type']) if row['media_wa_type'] else None,
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'quoted_row_id': safe_int(row['quoted_row_id'], None),
                    'forwarded': safe_int(row['forwarded']),
                    'mentioned_jids': row['mentioned_jids'],
                    'raw_json': dict(row)
                }
                messages.append(msg)

        except Exception as e:
            logger.error(f"Error parsing messages table: {e}", exc_info=True)

        return messages

    def _parse_message_table(self, cursor: sqlite3.Cursor) -> List[Dict]:
        """Parse messages from the 'message' table (newer schema)."""
        messages = []

        try:
            # First check if we need to join with other tables
            cursor.execute("""
                SELECT
                    m._id, m.chat_row_id, m.from_me, m.key_id,
                    m.sender_jid_row_id, m.status, m.timestamp,
                    m.received_timestamp, m.message_type, m.text_data,
                    m.starred
                FROM message m
                WHERE m.chat_row_id > 0
                LIMIT 1
            """)

            if cursor.fetchone() is None:
                logger.info("No messages found in 'message' table")
                return messages

            # Get messages with chat and sender information
            cursor.execute("""
                SELECT
                    m._id, m.chat_row_id, m.from_me, m.key_id,
                    m.sender_jid_row_id, m.status, m.timestamp,
                    m.received_timestamp, m.message_type, m.text_data,
                    m.starred,
                    c.jid_row_id as chat_jid_row,
                    sender.raw_string as sender_jid,
                    chat_jid.raw_string as chat_jid
                FROM message m
                LEFT JOIN chat c ON m.chat_row_id = c._id
                LEFT JOIN jid chat_jid ON c.jid_row_id = chat_jid._id
                LEFT JOIN jid sender ON m.sender_jid_row_id = sender._id
                WHERE m.chat_row_id > 0
            """)

            for row in cursor.fetchall():
                # Helper to safely convert to int
                def safe_int(val, default=0):
                    if val is None:
                        return default
                    try:
                        return int(val)
                    except (ValueError, TypeError):
                        return default

                # Check for media
                media_info = self._get_message_media(cursor, row['_id'], row['chat_row_id'])

                msg = {
                    'msg_id': row['key_id'] or str(row['_id']),
                    'chat_jid': row['chat_jid'] or '',
                    'sender_jid': row['sender_jid'],
                    'from_me': safe_int(row['from_me']),
                    'message_text': row['text_data'],
                    'message_type': safe_int(row['message_type']),
                    'timestamp': safe_int(row['timestamp'], None),
                    'received_timestamp': safe_int(row['received_timestamp'], None),
                    'status': safe_int(row['status']),
                    'starred': safe_int(row['starred']),
                    **media_info,  # Merge media information
                    'raw_json': dict(row)
                }
                messages.append(msg)

        except Exception as e:
            logger.error(f"Error parsing message table: {e}", exc_info=True)

        return messages

    def _get_message_media(self, cursor: sqlite3.Cursor, message_row_id: int, chat_row_id: int) -> Dict:
        """Get media information for a message from message_media table."""
        def safe_int(val, default=None):
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        media_info = {
            'media_path': None,
            'media_mimetype': None,
            'media_size': None,
            'media_name': None,
            'media_hash': None,
            'media_duration': None,
            'media_url': None,
        }

        try:
            cursor.execute("""
                SELECT
                    file_path, mime_type, file_size, media_name,
                    file_hash, media_duration, message_url
                FROM message_media
                WHERE message_row_id = ? AND chat_row_id = ?
            """, (message_row_id, chat_row_id))

            row = cursor.fetchone()
            if row:
                media_info = {
                    'media_path': row['file_path'],
                    'media_mimetype': row['mime_type'],
                    'media_size': safe_int(row['file_size']),
                    'media_name': row['media_name'],
                    'media_hash': row['file_hash'],
                    'media_duration': safe_int(row['media_duration']),
                    'media_url': row['message_url'],
                }
        except Exception as e:
            logger.debug(f"No media found for message {message_row_id}: {e}")

        return media_info

    def _parse_chat_table(self, cursor: sqlite3.Cursor) -> List[Dict]:
        """Parse chats from the chat table."""
        chats = []

        try:
            cursor.execute("""
                SELECT
                    c._id, c.jid_row_id, c.subject, c.created_timestamp,
                    c.archived, c.hidden, c.sort_timestamp,
                    c.unseen_message_count,
                    j.raw_string as chat_jid
                FROM chat c
                LEFT JOIN jid j ON c.jid_row_id = j._id
            """)

            for row in cursor.fetchall():
                chat = {
                    'chat_jid': row['chat_jid'] or '',
                    'subject': row['subject'],
                    'created_timestamp': row['created_timestamp'],
                    'archived': row['archived'] or 0,
                    'hidden': row['hidden'] or 0,
                    'last_message_timestamp': row['sort_timestamp'],
                    'unseen_message_count': row['unseen_message_count'] or 0,
                    'metadata': dict(row)
                }
                chats.append(chat)

        except Exception as e:
            logger.error(f"Error parsing chat table: {e}", exc_info=True)

        return chats

    def _parse_jid_table(self, cursor: sqlite3.Cursor) -> List[Dict]:
        """Parse contacts/JIDs from the jid table."""
        contacts = []

        try:
            cursor.execute("""
                SELECT _id, user, server, raw_string, type
                FROM jid
            """)

            for row in cursor.fetchall():
                contact = {
                    'jid': row['raw_string'] or '',
                    'display_name': None,  # Will be enriched later if contacts table exists
                    'phone_number': row['user'],
                    'metadata': dict(row)
                }
                contacts.append(contact)

        except Exception as e:
            logger.error(f"Error parsing jid table: {e}", exc_info=True)

        return contacts

    def _parse_call_log_table(self, cursor: sqlite3.Cursor) -> List[Dict]:
        """Parse call logs from the call_log table."""
        call_logs = []

        def safe_int(val, default=0):
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        try:
            # Get call logs with joined JID information
            cursor.execute("""
                SELECT
                    cl._id, cl.jid_row_id, cl.from_me, cl.call_id,
                    cl.timestamp, cl.video_call, cl.duration, cl.call_result,
                    cl.bytes_transferred, cl.group_jid_row_id,
                    j.raw_string as jid
                FROM call_log cl
                LEFT JOIN jid j ON cl.jid_row_id = j._id
            """)

            for row in cursor.fetchall():
                # Determine call type
                call_type = 'video' if safe_int(row['video_call']) else 'voice'

                # Determine call status based on call_result
                # Common values: 5 = completed, 1 = missed, 2 = rejected, etc.
                call_result = safe_int(row['call_result'])
                if call_result == 5:
                    status = 'completed'
                elif call_result == 1:
                    status = 'missed'
                elif call_result == 2:
                    status = 'rejected'
                elif call_result == 3:
                    status = 'cancelled'
                else:
                    status = f'unknown_{call_result}'

                call_log = {
                    'call_id': row['call_id'],
                    'from_jid': row['jid'] if not safe_int(row['from_me']) else None,
                    'to_jid': row['jid'] if safe_int(row['from_me']) else None,
                    'from_me': safe_int(row['from_me']),
                    'call_type': call_type,
                    'timestamp': safe_int(row['timestamp'], None),
                    'duration': safe_int(row['duration'], None),
                    'status': status,
                    'call_result': call_result,
                    'bytes_transferred': safe_int(row['bytes_transferred'], None),
                    'is_group_call': 1 if safe_int(row['group_jid_row_id']) > 0 else 0,
                    'raw_json': dict(row)
                }
                call_logs.append(call_log)

        except Exception as e:
            logger.error(f"Error parsing call_log table: {e}", exc_info=True)

        return call_logs

    def cleanup(self):
        """Clean up temporary files including downloaded UFDR file if from URL."""
        # Clean up temp directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")

        # Clean up downloaded file if it was from URL
        if self.is_url and self.ufdr_path and os.path.exists(self.ufdr_path):
            try:
                os.remove(self.ufdr_path)
                logger.info(f"Cleaned up downloaded UFDR file: {self.ufdr_path}")
            except Exception as e:
                logger.error(f"Error cleaning up downloaded UFDR file: {e}")

    async def extract_and_load(self, db_operations_module):
        """
        Main extraction and loading pipeline.

        Args:
            db_operations_module: The whatsapp_operations module for DB operations
        """
        try:
            # Extract databases first (this sets self.ufdr_path)
            db_files = self.extract_whatsapp_databases()

            # Create extraction job (now self.ufdr_path is set)
            await db_operations_module.create_extraction_job(
                self.upload_id,
                os.path.basename(self.ufdr_path)
            )

            # Update status to processing
            await db_operations_module.update_extraction_status(
                self.upload_id,
                'processing'
            )

            if not db_files:
                logger.warning("No WhatsApp databases found in UFDR file")
                await db_operations_module.update_extraction_status(
                    self.upload_id,
                    'completed',
                    total_messages=0,
                    processed_messages=0
                )
                return

            # Process each database
            all_messages = []
            all_chats = []
            all_contacts = []
            all_call_logs = []

            for db_file in db_files:
                messages, chats, contacts, call_logs = self.parse_sqlite_messages(db_file)
                all_messages.extend(messages)
                all_chats.extend(chats)
                all_contacts.extend(contacts)
                all_call_logs.extend(call_logs)

            # Deduplicate
            unique_messages = self._deduplicate_messages(all_messages)
            unique_chats = self._deduplicate_by_key(all_chats, 'chat_jid')
            unique_contacts = self._deduplicate_by_key(all_contacts, 'jid')
            unique_call_logs = self._deduplicate_by_key(all_call_logs, 'call_id')

            logger.info(f"Total unique messages: {len(unique_messages)}")
            logger.info(f"Total unique chats: {len(unique_chats)}")
            logger.info(f"Total unique contacts: {len(unique_contacts)}")
            logger.info(f"Total unique call logs: {len(unique_call_logs)}")

            # Update total count
            await db_operations_module.update_extraction_status(
                self.upload_id,
                'processing',
                total_messages=len(unique_messages)
            )

            # Insert chats first
            for chat in unique_chats:
                await db_operations_module.insert_whatsapp_chat(
                    self.upload_id,
                    chat['chat_jid'],
                    chat.get('subject'),
                    chat.get('created_timestamp'),
                    chat.get('metadata')
                )

            # Insert contacts
            for contact in unique_contacts:
                if contact['jid']:  # Skip empty JIDs
                    await db_operations_module.insert_whatsapp_contact(
                        self.upload_id,
                        contact['jid'],
                        contact.get('display_name'),
                        contact.get('phone_number'),
                        contact.get('metadata')
                    )

            # Insert call logs
            for call_log in unique_call_logs:
                if call_log.get('call_id'):  # Skip empty call IDs
                    await db_operations_module.insert_whatsapp_call_log(
                        self.upload_id,
                        call_log
                    )

            logger.info(f"Inserted {len(unique_call_logs)} call logs")

            # Insert messages in batches
            batch_size = 100
            processed = 0

            for i in range(0, len(unique_messages), batch_size):
                batch = unique_messages[i:i + batch_size]
                await db_operations_module.bulk_insert_messages(self.upload_id, batch)
                processed += len(batch)

                # Update progress
                await db_operations_module.update_extraction_status(
                    self.upload_id,
                    'processing',
                    processed_messages=processed
                )

                logger.info(f"Processed {processed}/{len(unique_messages)} messages")

            # Mark as completed
            await db_operations_module.update_extraction_status(
                self.upload_id,
                'completed',
                total_messages=len(unique_messages),
                processed_messages=processed
            )

            logger.info(f"Extraction completed for upload_id: {self.upload_id}")

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            await db_operations_module.update_extraction_status(
                self.upload_id,
                'failed',
                error_message=str(e)
            )
            raise
        finally:
            self.cleanup()

    def _deduplicate_messages(self, messages: List[Dict]) -> List[Dict]:
        """Deduplicate messages by msg_id and chat_jid."""
        seen = set()
        unique = []

        for msg in messages:
            key = (msg.get('msg_id'), msg.get('chat_jid'))
            if key not in seen and msg.get('chat_jid'):
                seen.add(key)
                unique.append(msg)

        return unique

    def _deduplicate_by_key(self, items: List[Dict], key: str) -> List[Dict]:
        """Deduplicate items by a specific key."""
        seen = set()
        unique = []

        for item in items:
            val = item.get(key)
            if val and val not in seen:
                seen.add(val)
                unique.append(item)

        return unique


# Async wrapper for RQ worker
def extract_whatsapp_from_ufdr(upload_id: str, ufdr_path: str):
    """
    RQ worker job to extract WhatsApp data from UFDR file.

    Args:
        upload_id: Unique upload identifier
        ufdr_path: Path to the UFDR file
    """
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import whatsapp_operations

    logger.info(f"Starting WhatsApp extraction for upload_id: {upload_id}")

    extractor = UFDRWhatsAppExtractor(ufdr_path, upload_id)

    # Run async extraction
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(extractor.extract_and_load(whatsapp_operations))
        logger.info("WhatsApp extraction completed successfully")
    except Exception as e:
        logger.error(f"WhatsApp extraction failed: {e}", exc_info=True)
        raise
    finally:
        loop.close()


# Main function for standalone execution
async def main():
    """Main function for testing the extractor standalone."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ufdr_whatsapp_extractor.py <ufdr_file_path> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Setup path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import whatsapp_operations

    # Initialize schema
    await whatsapp_operations.init_whatsapp_schema()

    # Run extraction
    extractor = UFDRWhatsAppExtractor(ufdr_path, upload_id)
    await extractor.extract_and_load(whatsapp_operations)


if __name__ == '__main__':
    asyncio.run(main())
