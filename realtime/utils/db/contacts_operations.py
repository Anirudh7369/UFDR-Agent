"""
Database operations for contacts extracted from UFDR files.

This module provides async functions to interact with the contacts tables.
"""

import asyncpg
import os
import json
from typing import List, Dict, Any, Optional
import logging
from .connection import get_db_connection, get_db_pool

logger = logging.getLogger(__name__)


async def init_contacts_schema():
    """Initialize the contacts database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        'contacts_schema.sql'
    )

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    async with get_db_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Contacts schema initialized successfully")


async def create_contact_extraction_job(upload_id: str, ufdr_filename: str):
    """Create a new contact extraction job."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO contact_extractions (upload_id, ufdr_filename, extraction_status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (upload_id) DO UPDATE
            SET ufdr_filename = EXCLUDED.ufdr_filename,
                updated_at = CURRENT_TIMESTAMP
        """, upload_id, ufdr_filename)

    logger.info(f"Created contact extraction job for upload_id: {upload_id}")


async def update_contact_extraction_status(
    upload_id: str,
    status: str,
    total_contacts: Optional[int] = None,
    processed_contacts: Optional[int] = None,
    total_entries: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Update the status of a contact extraction job."""
    async with get_db_connection() as conn:
        updates = ["extraction_status = $2", "updated_at = CURRENT_TIMESTAMP"]
        params = [upload_id, status]
        param_idx = 3

        if total_contacts is not None:
            updates.append(f"total_contacts = ${param_idx}")
            params.append(total_contacts)
            param_idx += 1

        if processed_contacts is not None:
            updates.append(f"processed_contacts = ${param_idx}")
            params.append(processed_contacts)
            param_idx += 1

        if total_entries is not None:
            updates.append(f"total_entries = ${param_idx}")
            params.append(total_entries)
            param_idx += 1

        if error_message is not None:
            updates.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query = f"""
            UPDATE contact_extractions
            SET {', '.join(updates)}
            WHERE upload_id = $1
        """

        await conn.execute(query, *params)

    logger.info(f"Updated contact extraction status for {upload_id}: {status}")


async def bulk_insert_contacts(upload_id: str, contacts: List[Dict[str, Any]]):
    """Bulk insert contacts with their entries."""
    if not contacts:
        return

    async with get_db_connection() as conn:
        # Start a transaction
        async with conn.transaction():
            for contact in contacts:
                # Prepare contact data
                contact_json = contact.copy()
                if contact_json.get('time_created_dt'):
                    contact_json['time_created_dt'] = contact_json['time_created_dt'].isoformat()

                # Remove entries from JSON (they'll be in separate table)
                entries = contact_json.pop('entries', [])

                # Insert main contact record
                contact_db_id = await conn.fetchval("""
                    INSERT INTO contacts (
                        upload_id, contact_id, source_app, service_identifier,
                        name, account, contact_type, contact_group,
                        time_created, time_created_dt, notes, interaction_statuses,
                        user_tags, deleted_state, decoding_confidence,
                        raw_xml, raw_json
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    RETURNING id
                """,
                    upload_id,
                    contact.get('contact_id'),
                    contact.get('source_app'),
                    contact.get('service_identifier'),
                    contact.get('name'),
                    contact.get('account'),
                    contact.get('contact_type'),
                    contact.get('contact_group'),
                    contact.get('time_created'),
                    contact.get('time_created_dt'),
                    contact.get('notes', []),
                    contact.get('interaction_statuses', []),
                    contact.get('user_tags', []),
                    contact.get('deleted_state'),
                    contact.get('decoding_confidence'),
                    contact.get('raw_xml'),
                    json.dumps(contact_json)
                )

                # Insert contact entries
                if entries:
                    entry_records = []
                    for entry in entries:
                        entry_json = entry.copy()

                        entry_record = (
                            contact_db_id,
                            upload_id,
                            entry.get('entry_id'),
                            entry.get('entry_type'),
                            entry.get('category'),
                            entry.get('value'),
                            entry.get('domain'),
                            entry.get('deleted_state'),
                            entry.get('decoding_confidence'),
                            entry.get('raw_xml'),
                            json.dumps(entry_json)
                        )
                        entry_records.append(entry_record)

                    await conn.executemany("""
                        INSERT INTO contact_entries (
                            contact_id, upload_id, entry_id, entry_type,
                            category, value, domain, deleted_state,
                            decoding_confidence, raw_xml, raw_json
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """, entry_records)

    logger.info(f"Bulk inserted {len(contacts)} contacts for upload_id: {upload_id}")


async def get_contact_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a contact extraction job."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM contact_extractions
            WHERE upload_id = $1
        """, upload_id)

        if row:
            return dict(row)
        return None


async def get_contacts(
    upload_id: str,
    source_app: Optional[str] = None,
    contact_type: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get contacts with optional filtering."""
    query = """
        SELECT c.*,
               json_agg(
                   json_build_object(
                       'entry_type', ce.entry_type,
                       'category', ce.category,
                       'value', ce.value,
                       'domain', ce.domain
                   )
               ) FILTER (WHERE ce.id IS NOT NULL) as entries
        FROM contacts c
        LEFT JOIN contact_entries ce ON c.id = ce.contact_id
        WHERE c.upload_id = $1
    """
    params = [upload_id]
    param_idx = 2

    if source_app:
        query += f" AND c.source_app = ${param_idx}"
        params.append(source_app)
        param_idx += 1

    if contact_type:
        query += f" AND c.contact_type = ${param_idx}"
        params.append(contact_type)
        param_idx += 1

    if search_text:
        query += f" AND (c.name ILIKE ${param_idx} OR c.account ILIKE ${param_idx})"
        params.append(f'%{search_text}%')
        param_idx += 1

    query += f" GROUP BY c.id ORDER BY c.time_created_dt DESC NULLS LAST LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_phone_contacts(
    upload_id: str,
    search_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get contacts with phone numbers."""
    query = """
        SELECT DISTINCT ON (c.id)
            c.id, c.name, c.source_app, c.contact_type, c.account,
            ce.value as phone_number, ce.category as phone_type,
            c.time_created_dt
        FROM contacts c
        INNER JOIN contact_entries ce ON c.id = ce.contact_id
        WHERE c.upload_id = $1 AND ce.entry_type = 'PhoneNumber'
    """
    params = [upload_id]
    param_idx = 2

    if search_text:
        query += f" AND (c.name ILIKE ${param_idx} OR ce.value ILIKE ${param_idx})"
        params.append(f'%{search_text}%')
        param_idx += 1

    query += f" ORDER BY c.id, c.time_created_dt DESC NULLS LAST LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_email_contacts(
    upload_id: str,
    search_text: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get contacts with email addresses."""
    query = """
        SELECT DISTINCT ON (c.id)
            c.id, c.name, c.source_app, c.contact_type, c.account,
            ce.value as email_address, ce.category as email_type,
            c.time_created_dt
        FROM contacts c
        INNER JOIN contact_entries ce ON c.id = ce.contact_id
        WHERE c.upload_id = $1 AND ce.entry_type = 'EmailAddress'
    """
    params = [upload_id]
    param_idx = 2

    if search_text:
        query += f" AND (c.name ILIKE ${param_idx} OR ce.value ILIKE ${param_idx})"
        params.append(f'%{search_text}%')
        param_idx += 1

    query += f" ORDER BY c.id, c.time_created_dt DESC NULLS LAST LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_contact_statistics(upload_id: str) -> Dict[str, Any]:
    """Get statistics about contacts."""
    async with get_db_connection() as conn:
        # Total contacts
        total_contacts = await conn.fetchval("""
            SELECT COUNT(*) FROM contacts
            WHERE upload_id = $1
        """, upload_id)

        # Contacts by source app
        app_stats = await conn.fetch("""
            SELECT source_app, COUNT(*) as count
            FROM contacts
            WHERE upload_id = $1
            GROUP BY source_app
            ORDER BY count DESC
        """, upload_id)

        # Contacts by type
        type_stats = await conn.fetch("""
            SELECT contact_type, COUNT(*) as count
            FROM contacts
            WHERE upload_id = $1
            GROUP BY contact_type
            ORDER BY count DESC
        """, upload_id)

        # Entry type distribution
        entry_stats = await conn.fetch("""
            SELECT entry_type, COUNT(*) as count
            FROM contact_entries
            WHERE upload_id = $1
            GROUP BY entry_type
            ORDER BY count DESC
        """, upload_id)

        # Contacts with phone numbers
        phone_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT contact_id)
            FROM contact_entries
            WHERE upload_id = $1 AND entry_type = 'PhoneNumber'
        """, upload_id)

        # Contacts with emails
        email_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT contact_id)
            FROM contact_entries
            WHERE upload_id = $1 AND entry_type = 'EmailAddress'
        """, upload_id)

        return {
            'total_contacts': total_contacts,
            'by_source_app': [dict(row) for row in app_stats],
            'by_contact_type': [dict(row) for row in type_stats],
            'by_entry_type': [dict(row) for row in entry_stats],
            'contacts_with_phone': phone_count,
            'contacts_with_email': email_count,
        }
