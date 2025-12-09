"""
Database operations for instant messages extracted from UFDR files.

This module provides async functions to interact with the messages tables.
"""

import asyncpg
import os
import json
from typing import List, Dict, Any, Optional
import logging
from .connection import get_db_connection, get_db_pool

logger = logging.getLogger(__name__)


async def init_messages_schema():
    """Initialize the messages database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        'messages_schema.sql'
    )

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    async with get_db_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Messages schema initialized successfully")


async def create_message_extraction_job(upload_id: str, ufdr_filename: str):
    """Create a new message extraction job."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO message_extractions (upload_id, ufdr_filename, extraction_status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (upload_id) DO UPDATE
            SET ufdr_filename = EXCLUDED.ufdr_filename,
                updated_at = CURRENT_TIMESTAMP
        """, upload_id, ufdr_filename)

    logger.info(f"Created message extraction job for upload_id: {upload_id}")


async def update_message_extraction_status(
    upload_id: str,
    status: str,
    total_messages: Optional[int] = None,
    processed_messages: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Update the status of a message extraction job."""
    async with get_db_connection() as conn:
        updates = ["extraction_status = $2", "updated_at = CURRENT_TIMESTAMP"]
        params = [upload_id, status]
        param_idx = 3

        if total_messages is not None:
            updates.append(f"total_messages = ${param_idx}")
            params.append(total_messages)
            param_idx += 1

        if processed_messages is not None:
            updates.append(f"processed_messages = ${param_idx}")
            params.append(processed_messages)
            param_idx += 1

        if error_message is not None:
            updates.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query = f"""
            UPDATE message_extractions
            SET {', '.join(updates)}
            WHERE upload_id = $1
        """

        await conn.execute(query, *params)

    logger.info(f"Updated message extraction status for {upload_id}: {status}")


async def bulk_insert_messages(upload_id: str, messages: List[Dict[str, Any]]):
    """Bulk insert instant messages."""
    if not messages:
        return

    async with get_db_connection() as conn:
        # Prepare message records
        message_records = []
        party_records = []
        attachment_records = []

        for message in messages:
            # Prepare raw_json by converting datetime to string
            message_json = message.copy()
            if message_json.get('message_timestamp_dt'):
                message_json['message_timestamp_dt'] = message_json['message_timestamp_dt'].isoformat()

            # Prepare main message record
            record = (
                upload_id,
                message.get('message_id'),
                message.get('source_app'),
                message.get('body'),
                message.get('message_type'),
                message.get('platform'),
                message.get('message_timestamp'),
                message.get('message_timestamp_dt'),  # Keep as datetime for database
                message.get('from_party_identifier'),
                message.get('from_party_name'),
                message.get('from_party_is_owner', False),
                message.get('to_party_identifier'),
                message.get('to_party_name'),
                message.get('to_party_is_owner', False),
                message.get('has_attachments', False),
                message.get('attachment_count', 0),
                message.get('deleted_state'),
                message.get('decoding_confidence'),
                message.get('raw_xml'),
                json.dumps(message_json),  # raw_json with datetime converted to string
            )
            message_records.append(record)

        # Insert messages
        await conn.executemany("""
            INSERT INTO messages (
                upload_id, message_id, source_app, body, message_type, platform,
                message_timestamp, message_timestamp_dt,
                from_party_identifier, from_party_name, from_party_is_owner,
                to_party_identifier, to_party_name, to_party_is_owner,
                has_attachments, attachment_count,
                deleted_state, decoding_confidence, raw_xml, raw_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
        """, message_records)

        # Get message IDs for inserted records
        message_ids = await conn.fetch("""
            SELECT id, message_id FROM messages
            WHERE upload_id = $1 AND message_id = ANY($2)
        """, upload_id, [msg['message_id'] for msg in messages])

        message_id_map = {row['message_id']: row['id'] for row in message_ids}

        # Prepare party records
        for message in messages:
            msg_id = message_id_map.get(message['message_id'])
            if msg_id and message.get('parties'):
                for party in message['parties']:
                    party_records.append((
                        msg_id,
                        upload_id,
                        party.get('identifier'),
                        party.get('name'),
                        party.get('role'),
                        party.get('is_phone_owner', False),
                        json.dumps(party),
                    ))

        # Prepare attachment records
        for message in messages:
            msg_id = message_id_map.get(message['message_id'])
            if msg_id and message.get('attachments'):
                for attachment in message['attachments']:
                    attachment_records.append((
                        msg_id,
                        upload_id,
                        attachment.get('attachment_type'),
                        attachment.get('filename'),
                        attachment.get('file_path'),
                        attachment.get('file_size'),
                        attachment.get('mime_type'),
                        json.dumps(attachment),
                    ))

        # Insert parties
        if party_records:
            await conn.executemany("""
                INSERT INTO message_parties (
                    message_id, upload_id, party_identifier, party_name,
                    party_role, is_phone_owner, raw_json
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, party_records)

        # Insert attachments
        if attachment_records:
            await conn.executemany("""
                INSERT INTO message_attachments (
                    message_id, upload_id, attachment_type, filename,
                    file_path, file_size, mime_type, raw_json
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, attachment_records)

    logger.info(f"Bulk inserted {len(messages)} messages for upload_id: {upload_id}")


async def get_message_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a message extraction job."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM message_extractions
            WHERE upload_id = $1
        """, upload_id)

        if row:
            return dict(row)
        return None


async def get_messages(
    upload_id: str,
    source_app: Optional[str] = None,
    message_type: Optional[str] = None,
    has_attachments: Optional[bool] = None,
    search_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get messages with optional filtering."""
    query = "SELECT * FROM messages WHERE upload_id = $1"
    params = [upload_id]
    param_idx = 2

    if source_app:
        query += f" AND source_app = ${param_idx}"
        params.append(source_app)
        param_idx += 1

    if message_type:
        query += f" AND message_type = ${param_idx}"
        params.append(message_type)
        param_idx += 1

    if has_attachments is not None:
        query += f" AND has_attachments = ${param_idx}"
        params.append(has_attachments)
        param_idx += 1

    if search_text:
        query += f" AND body ILIKE ${param_idx}"
        params.append(f'%{search_text}%')
        param_idx += 1

    query += f" ORDER BY message_timestamp_dt DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_message_statistics(upload_id: str) -> Dict[str, Any]:
    """Get statistics about messages."""
    async with get_db_connection() as conn:
        # Total messages
        total_messages = await conn.fetchval("""
            SELECT COUNT(*) FROM messages
            WHERE upload_id = $1
        """, upload_id)

        # Messages by app
        app_stats = await conn.fetch("""
            SELECT source_app, COUNT(*) as count
            FROM messages
            WHERE upload_id = $1
            GROUP BY source_app
            ORDER BY count DESC
        """, upload_id)

        # Messages by type
        type_stats = await conn.fetch("""
            SELECT message_type, COUNT(*) as count
            FROM messages
            WHERE upload_id = $1
            GROUP BY message_type
            ORDER BY count DESC
        """, upload_id)

        # Messages with attachments
        attachment_stats = await conn.fetchrow("""
            SELECT
                SUM(CASE WHEN has_attachments THEN 1 ELSE 0 END) as with_attachments,
                SUM(CASE WHEN NOT has_attachments THEN 1 ELSE 0 END) as without_attachments,
                SUM(attachment_count) as total_attachments
            FROM messages
            WHERE upload_id = $1
        """, upload_id)

        # Date range
        date_range = await conn.fetchrow("""
            SELECT
                MIN(message_timestamp_dt) as first_message,
                MAX(message_timestamp_dt) as last_message
            FROM messages
            WHERE upload_id = $1 AND message_timestamp_dt IS NOT NULL
        """, upload_id)

        return {
            'total_messages': total_messages,
            'with_attachments': attachment_stats['with_attachments'] if attachment_stats else 0,
            'without_attachments': attachment_stats['without_attachments'] if attachment_stats else 0,
            'total_attachments': attachment_stats['total_attachments'] if attachment_stats else 0,
            'first_message_date': date_range['first_message'].isoformat() if date_range and date_range['first_message'] else None,
            'last_message_date': date_range['last_message'].isoformat() if date_range and date_range['last_message'] else None,
            'by_app': [dict(row) for row in app_stats],
            'by_type': [dict(row) for row in type_stats],
        }
