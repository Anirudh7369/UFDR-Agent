"""
Database operations for call logs extracted from UFDR files.

This module provides async functions to interact with the call_logs tables.
"""

import asyncpg
import os
import json
from typing import List, Dict, Any, Optional
import logging
from .connection import get_db_connection, get_db_pool

logger = logging.getLogger(__name__)


async def init_call_logs_schema():
    """Initialize the call logs database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        'call_logs_schema.sql'
    )

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    async with get_db_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Call logs schema initialized successfully")


async def create_call_log_extraction_job(upload_id: str, ufdr_filename: str):
    """Create a new call log extraction job."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO call_log_extractions (upload_id, ufdr_filename, extraction_status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (upload_id) DO UPDATE
            SET ufdr_filename = EXCLUDED.ufdr_filename,
                updated_at = CURRENT_TIMESTAMP
        """, upload_id, ufdr_filename)

    logger.info(f"Created call log extraction job for upload_id: {upload_id}")


async def update_call_log_extraction_status(
    upload_id: str,
    status: str,
    total_calls: Optional[int] = None,
    processed_calls: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Update the status of a call log extraction job."""
    async with get_db_connection() as conn:
        updates = ["extraction_status = $2", "updated_at = CURRENT_TIMESTAMP"]
        params = [upload_id, status]
        param_idx = 3

        if total_calls is not None:
            updates.append(f"total_calls = ${param_idx}")
            params.append(total_calls)
            param_idx += 1

        if processed_calls is not None:
            updates.append(f"processed_calls = ${param_idx}")
            params.append(processed_calls)
            param_idx += 1

        if error_message is not None:
            updates.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query = f"""
            UPDATE call_log_extractions
            SET {', '.join(updates)}
            WHERE upload_id = $1
        """

        await conn.execute(query, *params)

    logger.info(f"Updated call log extraction status for {upload_id}: {status}")


async def bulk_insert_call_logs(upload_id: str, calls: List[Dict[str, Any]]):
    """Bulk insert call logs."""
    if not calls:
        return

    async with get_db_connection() as conn:
        # Prepare call records
        call_records = []
        party_records = []

        for call in calls:
            # Prepare raw_json by converting datetime to string
            call_json = call.copy()
            if call_json.get('call_timestamp_dt'):
                call_json['call_timestamp_dt'] = call_json['call_timestamp_dt'].isoformat()

            # Prepare main call record
            record = (
                upload_id,
                call.get('call_id'),
                call.get('source_app'),
                call.get('direction'),
                call.get('call_type'),
                call.get('status'),
                call.get('call_timestamp'),
                call.get('call_timestamp_dt'),  # Keep as datetime for database
                call.get('duration_seconds'),
                call.get('duration_string'),
                call.get('country_code'),
                call.get('network_code'),
                call.get('network_name'),
                call.get('account'),
                call.get('is_video_call', False),
                call.get('from_party_identifier'),
                call.get('from_party_name'),
                call.get('from_party_is_owner', False),
                call.get('to_party_identifier'),
                call.get('to_party_name'),
                call.get('to_party_is_owner', False),
                call.get('deleted_state'),
                call.get('decoding_confidence'),
                call.get('raw_xml'),
                json.dumps(call_json),  # raw_json with datetime converted to string
            )
            call_records.append(record)

        # Insert calls
        await conn.executemany("""
            INSERT INTO call_logs (
                upload_id, call_id, source_app, direction, call_type, status,
                call_timestamp, call_timestamp_dt, duration_seconds, duration_string,
                country_code, network_code, network_name, account, is_video_call,
                from_party_identifier, from_party_name, from_party_is_owner,
                to_party_identifier, to_party_name, to_party_is_owner,
                deleted_state, decoding_confidence, raw_xml, raw_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                      $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)
        """, call_records)

        # Get call IDs for inserted records
        call_ids = await conn.fetch("""
            SELECT id, call_id FROM call_logs
            WHERE upload_id = $1 AND call_id = ANY($2)
        """, upload_id, [call['call_id'] for call in calls])

        call_id_map = {row['call_id']: row['id'] for row in call_ids}

        # Prepare party records
        for call in calls:
            call_log_id = call_id_map.get(call['call_id'])
            if call_log_id and call.get('parties'):
                for party in call['parties']:
                    party_records.append((
                        call_log_id,
                        upload_id,
                        party.get('identifier'),
                        party.get('name'),
                        party.get('role'),
                        party.get('is_phone_owner', False),
                        json.dumps(party),
                    ))

        # Insert parties
        if party_records:
            await conn.executemany("""
                INSERT INTO call_log_parties (
                    call_log_id, upload_id, party_identifier, party_name,
                    party_role, is_phone_owner, raw_json
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, party_records)

    logger.info(f"Bulk inserted {len(calls)} call logs for upload_id: {upload_id}")


async def get_call_log_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a call log extraction job."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM call_log_extractions
            WHERE upload_id = $1
        """, upload_id)

        if row:
            return dict(row)
        return None


async def get_call_logs(
    upload_id: str,
    source_app: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    is_video: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get call logs with optional filtering."""
    query = "SELECT * FROM call_logs WHERE upload_id = $1"
    params = [upload_id]
    param_idx = 2

    if source_app:
        query += f" AND source_app = ${param_idx}"
        params.append(source_app)
        param_idx += 1

    if direction:
        query += f" AND direction = ${param_idx}"
        params.append(direction)
        param_idx += 1

    if status:
        query += f" AND status = ${param_idx}"
        params.append(status)
        param_idx += 1

    if is_video is not None:
        query += f" AND is_video_call = ${param_idx}"
        params.append(is_video)
        param_idx += 1

    query += f" ORDER BY call_timestamp_dt DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_call_log_statistics(upload_id: str) -> Dict[str, Any]:
    """Get statistics about call logs."""
    async with get_db_connection() as conn:
        # Total calls
        total_calls = await conn.fetchval("""
            SELECT COUNT(*) FROM call_logs
            WHERE upload_id = $1
        """, upload_id)

        # Calls by app
        app_stats = await conn.fetch("""
            SELECT source_app, COUNT(*) as count
            FROM call_logs
            WHERE upload_id = $1
            GROUP BY source_app
            ORDER BY count DESC
        """, upload_id)

        # Calls by direction
        direction_stats = await conn.fetch("""
            SELECT direction, COUNT(*) as count
            FROM call_logs
            WHERE upload_id = $1
            GROUP BY direction
        """, upload_id)

        # Calls by status
        status_stats = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM call_logs
            WHERE upload_id = $1
            GROUP BY status
            ORDER BY count DESC
        """, upload_id)

        # Video vs voice
        video_stats = await conn.fetchrow("""
            SELECT
                SUM(CASE WHEN is_video_call THEN 1 ELSE 0 END) as video_calls,
                SUM(CASE WHEN NOT is_video_call THEN 1 ELSE 0 END) as voice_calls
            FROM call_logs
            WHERE upload_id = $1
        """, upload_id)

        # Date range
        date_range = await conn.fetchrow("""
            SELECT
                MIN(call_timestamp_dt) as first_call,
                MAX(call_timestamp_dt) as last_call
            FROM call_logs
            WHERE upload_id = $1 AND call_timestamp_dt IS NOT NULL
        """, upload_id)

        return {
            'total_calls': total_calls,
            'video_calls': video_stats['video_calls'] if video_stats else 0,
            'voice_calls': video_stats['voice_calls'] if video_stats else 0,
            'first_call_date': date_range['first_call'].isoformat() if date_range and date_range['first_call'] else None,
            'last_call_date': date_range['last_call'].isoformat() if date_range and date_range['last_call'] else None,
            'by_app': [dict(row) for row in app_stats],
            'by_direction': [dict(row) for row in direction_stats],
            'by_status': [dict(row) for row in status_stats],
        }
