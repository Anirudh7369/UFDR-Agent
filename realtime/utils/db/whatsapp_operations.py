"""
Database operations for WhatsApp data extraction from UFDR files.
"""

import asyncpg
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone
from .connection import get_db_connection

logger = logging.getLogger(__name__)


async def init_whatsapp_schema():
    """
    Initialize the WhatsApp database schema.
    Reads and executes the schema SQL file.
    """
    try:
        import os
        schema_path = os.path.join(os.path.dirname(__file__), 'whatsapp_schema.sql')

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        async with get_db_connection() as conn:
            await conn.execute(schema_sql)
            logger.info("WhatsApp schema initialized successfully")
            return True
    except Exception as e:
        logger.error(f"Failed to initialize WhatsApp schema: {str(e)}", exc_info=True)
        raise


async def create_extraction_job(
    upload_id: str,
    ufdr_filename: str,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Create a new UFDR extraction job record.

    Args:
        upload_id: Unique upload identifier
        ufdr_filename: Name of the UFDR file
        metadata: Optional metadata dict

    Returns:
        int: The extraction job ID
    """
    try:
        import json
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ufdr_extractions (upload_id, ufdr_filename, extraction_status, metadata)
                VALUES ($1, $2, 'pending', $3)
                ON CONFLICT (upload_id)
                DO UPDATE SET
                    extraction_status = 'pending',
                    started_at = NOW(),
                    metadata = $3
                RETURNING id
                """,
                upload_id,
                ufdr_filename,
                json.dumps(metadata) if metadata else None
            )
            job_id = row['id']
            logger.info(f"Created extraction job {job_id} for upload_id: {upload_id}")
            return job_id
    except Exception as e:
        logger.error(f"Failed to create extraction job: {str(e)}", exc_info=True)
        raise


async def update_extraction_status(
    upload_id: str,
    status: str,
    total_messages: Optional[int] = None,
    processed_messages: Optional[int] = None,
    error_message: Optional[str] = None
) -> bool:
    """
    Update the status of an extraction job.

    Args:
        upload_id: Upload identifier
        status: New status (pending, processing, completed, failed)
        total_messages: Total number of messages to process
        processed_messages: Number of messages processed so far
        error_message: Error message if failed

    Returns:
        bool: True if successful
    """
    try:
        async with get_db_connection() as conn:
            update_parts = ["extraction_status = $2"]
            params = [upload_id, status]
            param_idx = 3

            if total_messages is not None:
                update_parts.append(f"total_messages = ${param_idx}")
                params.append(total_messages)
                param_idx += 1

            if processed_messages is not None:
                update_parts.append(f"processed_messages = ${param_idx}")
                params.append(processed_messages)
                param_idx += 1

            if error_message is not None:
                update_parts.append(f"error_message = ${param_idx}")
                params.append(error_message)
                param_idx += 1

            if status == 'completed':
                update_parts.append("completed_at = NOW()")

            query = f"""
                UPDATE ufdr_extractions
                SET {', '.join(update_parts)}
                WHERE upload_id = $1
            """

            await conn.execute(query, *params)
            logger.info(f"Updated extraction status for {upload_id}: {status}")
            return True
    except Exception as e:
        logger.error(f"Failed to update extraction status: {str(e)}", exc_info=True)
        return False


async def insert_whatsapp_jid(
    upload_id: str,
    raw_string: str,
    user_part: Optional[str] = None,
    server_part: Optional[str] = None,
    jid_type: Optional[int] = None
) -> int:
    """
    Insert or get a WhatsApp JID.

    Returns:
        int: The JID ID
    """
    try:
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO whatsapp_jids (upload_id, raw_string, user_part, server_part, jid_type)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (upload_id, raw_string) DO UPDATE SET user_part = $3
                RETURNING id
                """,
                upload_id, raw_string, user_part, server_part, jid_type
            )
            return row['id']
    except Exception as e:
        logger.error(f"Failed to insert WhatsApp JID: {str(e)}", exc_info=True)
        raise


async def insert_whatsapp_chat(
    upload_id: str,
    chat_jid: str,
    subject: Optional[str] = None,
    created_timestamp: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Insert or update a WhatsApp chat.

    Returns:
        int: The chat ID
    """
    try:
        import json
        async with get_db_connection() as conn:
            # First, ensure the JID exists
            jid_id = await insert_whatsapp_jid(upload_id, chat_jid)

            row = await conn.fetchrow(
                """
                INSERT INTO whatsapp_chats (upload_id, chat_jid, chat_jid_id, subject, created_timestamp, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (upload_id, chat_jid)
                DO UPDATE SET
                    subject = COALESCE($4, whatsapp_chats.subject),
                    metadata = $6
                RETURNING id
                """,
                upload_id, chat_jid, jid_id, subject, created_timestamp,
                json.dumps(metadata) if metadata else None
            )
            return row['id']
    except Exception as e:
        logger.error(f"Failed to insert WhatsApp chat: {str(e)}", exc_info=True)
        raise


async def bulk_insert_messages(upload_id: str, messages: List[Dict[str, Any]]) -> int:
    """
    Bulk insert WhatsApp messages.

    Args:
        upload_id: Upload identifier
        messages: List of message dictionaries

    Returns:
        int: Number of messages inserted
    """
    if not messages:
        return 0

    try:
        import json
        async with get_db_connection() as conn:
            # Prepare data for bulk insert
            records = []
            for msg in messages:
                # Convert timestamp to datetime if present
                timestamp_dt = None
                if msg.get('timestamp'):
                    try:
                        timestamp_dt = datetime.fromtimestamp(msg['timestamp'] / 1000.0, tz=timezone.utc)
                    except:
                        pass

                # Ensure chat exists
                chat_id = None
                if msg.get('chat_jid'):
                    chat_id = await insert_whatsapp_chat(upload_id, msg['chat_jid'])

                # Ensure sender JID exists if present
                sender_jid_id = None
                if msg.get('sender_jid'):
                    sender_jid_id = await insert_whatsapp_jid(upload_id, msg['sender_jid'])

                record = (
                    upload_id,
                    msg.get('msg_id', ''),
                    msg.get('chat_jid', ''),
                    chat_id,
                    msg.get('sender_jid'),
                    sender_jid_id,
                    msg.get('from_me', 0),
                    msg.get('message_text'),
                    msg.get('message_type'),
                    msg.get('timestamp'),
                    timestamp_dt,
                    msg.get('received_timestamp'),
                    msg.get('send_timestamp'),
                    msg.get('status'),
                    msg.get('starred', 0),
                    msg.get('media_url'),
                    msg.get('media_path'),
                    msg.get('media_mimetype'),
                    msg.get('media_size'),
                    msg.get('media_name'),
                    msg.get('media_caption'),
                    msg.get('media_hash'),
                    msg.get('media_duration'),
                    msg.get('media_wa_type'),
                    msg.get('latitude'),
                    msg.get('longitude'),
                    msg.get('quoted_row_id'),
                    msg.get('forwarded', 0),
                    msg.get('mentioned_jids'),
                    json.dumps(msg.get('raw_json', msg))
                )
                records.append(record)

            # Bulk insert
            await conn.executemany(
                """
                INSERT INTO whatsapp_messages (
                    upload_id, msg_id, chat_jid, chat_id,
                    sender_jid, sender_jid_id, from_me,
                    message_text, message_type,
                    timestamp, timestamp_dt, received_timestamp, send_timestamp,
                    status, starred,
                    media_url, media_path, media_mimetype, media_size, media_name,
                    media_caption, media_hash, media_duration, media_wa_type,
                    latitude, longitude,
                    quoted_row_id, forwarded, mentioned_jids,
                    raw_json
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                        $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30)
                ON CONFLICT (upload_id, msg_id, chat_jid) DO NOTHING
                """,
                records
            )

            logger.info(f"Bulk inserted {len(records)} messages for upload_id: {upload_id}")
            return len(records)

    except Exception as e:
        logger.error(f"Failed to bulk insert messages: {str(e)}", exc_info=True)
        raise


async def insert_whatsapp_contact(
    upload_id: str,
    jid: str,
    display_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Insert or update a WhatsApp contact.

    Returns:
        int: The contact ID
    """
    try:
        import json
        async with get_db_connection() as conn:
            # Ensure JID exists
            jid_id = await insert_whatsapp_jid(upload_id, jid)

            row = await conn.fetchrow(
                """
                INSERT INTO whatsapp_contacts (upload_id, jid, jid_id, display_name, phone_number, metadata)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (upload_id, jid)
                DO UPDATE SET
                    display_name = COALESCE($4, whatsapp_contacts.display_name),
                    phone_number = COALESCE($5, whatsapp_contacts.phone_number),
                    metadata = $6
                RETURNING id
                """,
                upload_id, jid, jid_id, display_name, phone_number,
                json.dumps(metadata) if metadata else None
            )
            return row['id']
    except Exception as e:
        logger.error(f"Failed to insert WhatsApp contact: {str(e)}", exc_info=True)
        raise


async def get_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current status of an extraction job.

    Args:
        upload_id: Upload identifier

    Returns:
        dict: Extraction status information or None
    """
    try:
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id, upload_id, ufdr_filename, extraction_status,
                    total_messages, processed_messages,
                    started_at, completed_at, error_message, metadata
                FROM ufdr_extractions
                WHERE upload_id = $1
                """,
                upload_id
            )

            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get extraction status: {str(e)}", exc_info=True)
        return None


async def insert_whatsapp_call_log(
    upload_id: str,
    call_log: Dict[str, Any]
) -> int:
    """
    Insert a WhatsApp call log entry.

    Args:
        upload_id: Upload identifier
        call_log: Call log dictionary with all fields

    Returns:
        int: The call log ID
    """
    try:
        import json
        from datetime import datetime, timezone

        async with get_db_connection() as conn:
            # Convert timestamp to datetime if present
            timestamp_dt = None
            if call_log.get('timestamp'):
                try:
                    timestamp_dt = datetime.fromtimestamp(call_log['timestamp'] / 1000.0, tz=timezone.utc)
                except:
                    pass

            row = await conn.fetchrow(
                """
                INSERT INTO whatsapp_call_logs (
                    upload_id, call_id, from_jid, to_jid, from_me,
                    call_type, timestamp, timestamp_dt, duration, status,
                    call_result, bytes_transferred, is_group_call, raw_json
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (upload_id, call_id) DO NOTHING
                RETURNING id
                """,
                upload_id,
                call_log.get('call_id'),
                call_log.get('from_jid'),
                call_log.get('to_jid'),
                call_log.get('from_me', 0),
                call_log.get('call_type'),
                call_log.get('timestamp'),
                timestamp_dt,
                call_log.get('duration'),
                call_log.get('status'),
                call_log.get('call_result'),
                call_log.get('bytes_transferred'),
                call_log.get('is_group_call', 0),
                json.dumps(call_log.get('raw_json', call_log))
            )

            if row:
                return row['id']
            return 0  # Duplicate, not inserted
    except Exception as e:
        logger.error(f"Failed to insert WhatsApp call log: {str(e)}", exc_info=True)
        raise


async def get_whatsapp_messages(
    upload_id: str,
    chat_jid: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve WhatsApp messages for an upload.

    Args:
        upload_id: Upload identifier
        chat_jid: Optional chat JID to filter by
        limit: Maximum number of messages to return
        offset: Offset for pagination

    Returns:
        list: List of message dictionaries
    """
    try:
        async with get_db_connection() as conn:
            if chat_jid:
                rows = await conn.fetch(
                    """
                    SELECT * FROM whatsapp_messages_view
                    WHERE upload_id = $1 AND chat_jid = $2
                    ORDER BY timestamp DESC
                    LIMIT $3 OFFSET $4
                    """,
                    upload_id, chat_jid, limit, offset
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM whatsapp_messages_view
                    WHERE upload_id = $1
                    ORDER BY timestamp DESC
                    LIMIT $2 OFFSET $3
                    """,
                    upload_id, limit, offset
                )

            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get WhatsApp messages: {str(e)}", exc_info=True)
        return []


async def get_whatsapp_call_logs(
    upload_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve WhatsApp call logs for an upload.

    Args:
        upload_id: Upload identifier
        limit: Maximum number of call logs to return
        offset: Offset for pagination

    Returns:
        list: List of call log dictionaries
    """
    try:
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM whatsapp_call_logs
                WHERE upload_id = $1
                ORDER BY timestamp DESC
                LIMIT $2 OFFSET $3
                """,
                upload_id, limit, offset
            )

            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get WhatsApp call logs: {str(e)}", exc_info=True)
        return []
