"""
Database operations for browsing history extracted from UFDR files.

This module provides async functions to interact with the browsing_history tables.
"""

import asyncpg
import os
import json
from typing import List, Dict, Any, Optional
import logging
from .connection import get_db_connection, get_db_pool

logger = logging.getLogger(__name__)


async def init_browsing_schema():
    """Initialize the browsing history database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        'browsing_schema.sql'
    )

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    async with get_db_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Browsing history schema initialized successfully")


async def create_browsing_extraction_job(upload_id: str, ufdr_filename: str):
    """Create a new browsing extraction job."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO browsing_extractions (upload_id, ufdr_filename, extraction_status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (upload_id) DO UPDATE
            SET ufdr_filename = EXCLUDED.ufdr_filename,
                updated_at = CURRENT_TIMESTAMP
        """, upload_id, ufdr_filename)

    logger.info(f"Created browsing extraction job for upload_id: {upload_id}")


async def update_browsing_extraction_status(
    upload_id: str,
    status: str,
    total_entries: Optional[int] = None,
    processed_entries: Optional[int] = None,
    visited_pages_count: Optional[int] = None,
    searched_items_count: Optional[int] = None,
    bookmarks_count: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Update the status of a browsing extraction job."""
    async with get_db_connection() as conn:
        updates = ["extraction_status = $2", "updated_at = CURRENT_TIMESTAMP"]
        params = [upload_id, status]
        param_idx = 3

        if total_entries is not None:
            updates.append(f"total_entries = ${param_idx}")
            params.append(total_entries)
            param_idx += 1

        if processed_entries is not None:
            updates.append(f"processed_entries = ${param_idx}")
            params.append(processed_entries)
            param_idx += 1

        if visited_pages_count is not None:
            updates.append(f"visited_pages_count = ${param_idx}")
            params.append(visited_pages_count)
            param_idx += 1

        if searched_items_count is not None:
            updates.append(f"searched_items_count = ${param_idx}")
            params.append(searched_items_count)
            param_idx += 1

        if bookmarks_count is not None:
            updates.append(f"bookmarks_count = ${param_idx}")
            params.append(bookmarks_count)
            param_idx += 1

        if error_message is not None:
            updates.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query = f"""
            UPDATE browsing_extractions
            SET {', '.join(updates)}
            WHERE upload_id = $1
        """

        await conn.execute(query, *params)

    logger.info(f"Updated browsing extraction status for {upload_id}: {status}")


async def bulk_insert_browsing_history(upload_id: str, entries: List[Dict[str, Any]]):
    """Bulk insert browsing history entries."""
    if not entries:
        return

    async with get_db_connection() as conn:
        # Prepare entry records
        entry_records = []

        for entry in entries:
            # Prepare raw_json by converting datetime to string
            entry_json = entry.copy()
            if entry_json.get('last_visited_dt'):
                entry_json['last_visited_dt'] = entry_json['last_visited_dt'].isoformat()

            # Prepare main entry record
            record = (
                upload_id,
                entry.get('entry_id'),
                entry.get('entry_type'),
                entry.get('source_browser'),
                entry.get('url'),
                entry.get('title'),
                entry.get('search_query'),
                entry.get('bookmark_path'),
                entry.get('last_visited'),
                entry.get('last_visited_dt'),  # Keep as datetime for database
                entry.get('visit_count'),
                entry.get('url_cache_file'),
                entry.get('deleted_state'),
                entry.get('decoding_confidence'),
                entry.get('raw_xml'),
                json.dumps(entry_json),  # raw_json with datetime converted to string
            )
            entry_records.append(record)

        # Insert entries
        await conn.executemany("""
            INSERT INTO browsing_history (
                upload_id, entry_id, entry_type, source_browser, url, title,
                search_query, bookmark_path, last_visited, last_visited_dt,
                visit_count, url_cache_file, deleted_state, decoding_confidence,
                raw_xml, raw_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        """, entry_records)

    logger.info(f"Bulk inserted {len(entries)} browsing entries for upload_id: {upload_id}")


async def get_browsing_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a browsing extraction job."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM browsing_extractions
            WHERE upload_id = $1
        """, upload_id)

        if row:
            return dict(row)
        return None


async def get_browsing_history(
    upload_id: str,
    entry_type: Optional[str] = None,
    source_browser: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get browsing history with optional filtering."""
    query = "SELECT * FROM browsing_history WHERE upload_id = $1"
    params = [upload_id]
    param_idx = 2

    if entry_type:
        query += f" AND entry_type = ${param_idx}"
        params.append(entry_type)
        param_idx += 1

    if source_browser:
        query += f" AND source_browser = ${param_idx}"
        params.append(source_browser)
        param_idx += 1

    if search_text:
        query += f" AND (url ILIKE ${param_idx} OR title ILIKE ${param_idx} OR search_query ILIKE ${param_idx})"
        params.append(f'%{search_text}%')
        param_idx += 1

    query += f" ORDER BY last_visited_dt DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_browsing_statistics(upload_id: str) -> Dict[str, Any]:
    """Get statistics about browsing history."""
    async with get_db_connection() as conn:
        # Total entries
        total_entries = await conn.fetchval("""
            SELECT COUNT(*) FROM browsing_history
            WHERE upload_id = $1
        """, upload_id)

        # Entries by type
        type_stats = await conn.fetch("""
            SELECT entry_type, COUNT(*) as count
            FROM browsing_history
            WHERE upload_id = $1
            GROUP BY entry_type
            ORDER BY count DESC
        """, upload_id)

        # Entries by browser
        browser_stats = await conn.fetch("""
            SELECT source_browser, COUNT(*) as count
            FROM browsing_history
            WHERE upload_id = $1
            GROUP BY source_browser
            ORDER BY count DESC
        """, upload_id)

        # Top visited sites (most visit count)
        top_sites = await conn.fetch("""
            SELECT url, title, source_browser, visit_count
            FROM browsing_history
            WHERE upload_id = $1 AND entry_type = 'visited_page' AND visit_count IS NOT NULL
            ORDER BY visit_count DESC
            LIMIT 10
        """, upload_id)

        # Top searches
        top_searches = await conn.fetch("""
            SELECT search_query, source_browser, last_visited_dt
            FROM browsing_history
            WHERE upload_id = $1 AND entry_type = 'search' AND search_query IS NOT NULL
            ORDER BY last_visited_dt DESC
            LIMIT 10
        """, upload_id)

        # Date range
        date_range = await conn.fetchrow("""
            SELECT
                MIN(last_visited_dt) as first_activity,
                MAX(last_visited_dt) as last_activity
            FROM browsing_history
            WHERE upload_id = $1 AND last_visited_dt IS NOT NULL
        """, upload_id)

        return {
            'total_entries': total_entries,
            'first_activity_date': date_range['first_activity'].isoformat() if date_range and date_range['first_activity'] else None,
            'last_activity_date': date_range['last_activity'].isoformat() if date_range and date_range['last_activity'] else None,
            'by_type': [dict(row) for row in type_stats],
            'by_browser': [dict(row) for row in browser_stats],
            'top_visited_sites': [dict(row) for row in top_sites],
            'top_searches': [dict(row) for row in top_searches],
        }
