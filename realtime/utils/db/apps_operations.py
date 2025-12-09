"""
Database operations for installed applications extracted from UFDR files.

This module provides async functions to interact with the installed_apps tables.
"""

import asyncpg
import os
import json
from typing import List, Dict, Any, Optional
import logging
from .connection import get_db_connection, get_db_pool

logger = logging.getLogger(__name__)


async def init_apps_schema():
    """Initialize the installed apps database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        'installed_apps_schema.sql'
    )

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    async with get_db_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Installed apps schema initialized successfully")


async def create_app_extraction_job(upload_id: str, ufdr_filename: str):
    """
    Create a new app extraction job.

    Args:
        upload_id: Unique identifier for the upload
        ufdr_filename: Name of the UFDR file
    """
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO app_extractions (upload_id, ufdr_filename, extraction_status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (upload_id) DO UPDATE
            SET ufdr_filename = EXCLUDED.ufdr_filename,
                updated_at = CURRENT_TIMESTAMP
        """, upload_id, ufdr_filename)

    logger.info(f"Created app extraction job for upload_id: {upload_id}")


async def update_app_extraction_status(
    upload_id: str,
    status: str,
    total_apps: Optional[int] = None,
    processed_apps: Optional[int] = None,
    error_message: Optional[str] = None
):
    """
    Update the status of an app extraction job.

    Args:
        upload_id: Unique identifier for the upload
        status: Status (pending, processing, completed, failed)
        total_apps: Total number of apps to process
        processed_apps: Number of apps processed so far
        error_message: Error message if failed
    """
    async with get_db_connection() as conn:
        # Build update query dynamically
        updates = ["extraction_status = $2", "updated_at = CURRENT_TIMESTAMP"]
        params = [upload_id, status]
        param_idx = 3

        if total_apps is not None:
            updates.append(f"total_apps = ${param_idx}")
            params.append(total_apps)
            param_idx += 1

        if processed_apps is not None:
            updates.append(f"processed_apps = ${param_idx}")
            params.append(processed_apps)
            param_idx += 1

        if error_message is not None:
            updates.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query = f"""
            UPDATE app_extractions
            SET {', '.join(updates)}
            WHERE upload_id = $1
        """

        await conn.execute(query, *params)

    logger.info(f"Updated app extraction status for {upload_id}: {status}")


async def bulk_insert_apps(upload_id: str, apps: List[Dict[str, Any]]):
    """
    Bulk insert installed apps.

    Args:
        upload_id: Unique identifier for the upload
        apps: List of app dictionaries
    """
    if not apps:
        return

    async with get_db_connection() as conn:
        # Prepare data for bulk insert
        records = []
        permission_records = []
        category_records = []

        for app in apps:
            # Convert timestamps to datetime strings if they're integers
            install_dt = None
            if app.get('install_timestamp'):
                from datetime import datetime
                install_dt = datetime.fromtimestamp(app['install_timestamp'] / 1000)

            last_launched_dt = None
            if app.get('last_launched_timestamp'):
                from datetime import datetime
                last_launched_dt = datetime.fromtimestamp(app['last_launched_timestamp'] / 1000)

            # Prepare main app record
            record = (
                upload_id,
                app.get('app_identifier'),
                app.get('app_name'),
                app.get('app_version'),
                app.get('app_guid'),
                app.get('install_timestamp'),
                install_dt,
                app.get('last_launched_timestamp'),
                last_launched_dt,
                app.get('decoding_status'),
                app.get('is_emulatable', False),
                app.get('operation_mode'),
                app.get('deleted_state'),
                app.get('decoding_confidence'),
                json.dumps(app.get('permissions', [])),  # JSONB
                json.dumps(app.get('categories', [])),  # JSONB
                json.dumps(app.get('associated_directory_paths', [])),  # JSONB
                app.get('raw_xml'),
                json.dumps(app),  # raw_json
            )
            records.append(record)

        # Insert apps
        await conn.executemany("""
            INSERT INTO installed_apps (
                upload_id, app_identifier, app_name, app_version, app_guid,
                install_timestamp, install_timestamp_dt,
                last_launched_timestamp, last_launched_dt,
                decoding_status, is_emulatable, operation_mode,
                deleted_state, decoding_confidence,
                permissions, categories, associated_directory_paths,
                raw_xml, raw_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            ON CONFLICT (upload_id, app_identifier) DO UPDATE
            SET app_name = EXCLUDED.app_name,
                app_version = EXCLUDED.app_version,
                install_timestamp = EXCLUDED.install_timestamp,
                install_timestamp_dt = EXCLUDED.install_timestamp_dt,
                updated_at = CURRENT_TIMESTAMP
        """, records)

        # Now insert normalized permissions and categories
        # Get app IDs first
        app_ids = await conn.fetch("""
            SELECT id, app_identifier FROM installed_apps
            WHERE upload_id = $1 AND app_identifier = ANY($2)
        """, upload_id, [app['app_identifier'] for app in apps])

        app_id_map = {row['app_identifier']: row['id'] for row in app_ids}

        # Prepare permission records
        for app in apps:
            app_id = app_id_map.get(app['app_identifier'])
            if app_id:
                for permission in app.get('permissions', []):
                    permission_records.append((
                        app_id,
                        upload_id,
                        app['app_identifier'],
                        permission
                    ))

                for category in app.get('categories', []):
                    category_records.append((
                        app_id,
                        upload_id,
                        app['app_identifier'],
                        category
                    ))

        # Insert permissions
        if permission_records:
            await conn.executemany("""
                INSERT INTO installed_app_permissions (app_id, upload_id, app_identifier, permission_category)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, permission_records)

        # Insert categories
        if category_records:
            await conn.executemany("""
                INSERT INTO installed_app_categories (app_id, upload_id, app_identifier, category)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, category_records)

    logger.info(f"Bulk inserted {len(apps)} apps for upload_id: {upload_id}")


async def get_app_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the status of an app extraction job.

    Args:
        upload_id: Unique identifier for the upload

    Returns:
        Dictionary with extraction status or None if not found
    """
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM app_extractions
            WHERE upload_id = $1
        """, upload_id)

        if row:
            return dict(row)
        return None


async def get_installed_apps(
    upload_id: str,
    app_identifier: Optional[str] = None,
    category: Optional[str] = None,
    permission: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Get installed apps with optional filtering.

    Args:
        upload_id: Upload identifier
        app_identifier: Filter by specific app identifier
        category: Filter by category
        permission: Filter by permission
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of app dictionaries
    """
    query = """
        SELECT DISTINCT a.* FROM installed_apps a
        WHERE a.upload_id = $1
    """
    params = [upload_id]
    param_idx = 2

    if app_identifier:
        query += f" AND a.app_identifier = ${param_idx}"
        params.append(app_identifier)
        param_idx += 1

    if category:
        query += f"""
            AND EXISTS (
                SELECT 1 FROM installed_app_categories c
                WHERE c.app_id = a.id AND c.category = ${param_idx}
            )
        """
        params.append(category)
        param_idx += 1

    if permission:
        query += f"""
            AND EXISTS (
                SELECT 1 FROM installed_app_permissions p
                WHERE p.app_id = a.id AND p.permission_category = ${param_idx}
            )
        """
        params.append(permission)
        param_idx += 1

    query += f" ORDER BY a.install_timestamp_dt DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_app_statistics(upload_id: str) -> Dict[str, Any]:
    """
    Get statistics about installed apps.

    Args:
        upload_id: Upload identifier

    Returns:
        Dictionary with statistics
    """
    async with get_db_connection() as conn:
        # Total apps
        total_apps = await conn.fetchval("""
            SELECT COUNT(*) FROM installed_apps
            WHERE upload_id = $1
        """, upload_id)

        # Apps by category
        category_stats = await conn.fetch("""
            SELECT category, COUNT(*) as count
            FROM installed_app_categories
            WHERE upload_id = $1
            GROUP BY category
            ORDER BY count DESC
            LIMIT 20
        """, upload_id)

        # Apps by permission
        permission_stats = await conn.fetch("""
            SELECT permission_category, COUNT(*) as count
            FROM installed_app_permissions
            WHERE upload_id = $1
            GROUP BY permission_category
            ORDER BY count DESC
            LIMIT 20
        """, upload_id)

        # Apps with install timestamps
        apps_with_timestamps = await conn.fetchval("""
            SELECT COUNT(*) FROM installed_apps
            WHERE upload_id = $1 AND install_timestamp IS NOT NULL
        """, upload_id)

        # First and last install dates
        date_range = await conn.fetchrow("""
            SELECT
                MIN(install_timestamp_dt) as first_install,
                MAX(install_timestamp_dt) as last_install
            FROM installed_apps
            WHERE upload_id = $1 AND install_timestamp_dt IS NOT NULL
        """, upload_id)

        return {
            'total_apps': total_apps,
            'apps_with_install_timestamps': apps_with_timestamps,
            'first_install_date': date_range['first_install'].isoformat() if date_range['first_install'] else None,
            'last_install_date': date_range['last_install'].isoformat() if date_range['last_install'] else None,
            'categories': [dict(row) for row in category_stats],
            'permissions': [dict(row) for row in permission_stats],
        }


async def search_apps(
    upload_id: str,
    search_term: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search apps by name or identifier.

    Args:
        upload_id: Upload identifier
        search_term: Search term
        limit: Maximum results

    Returns:
        List of matching apps
    """
    async with get_db_connection() as conn:
        rows = await conn.fetch("""
            SELECT * FROM installed_apps
            WHERE upload_id = $1
              AND (app_name ILIKE $2 OR app_identifier ILIKE $2)
            ORDER BY install_timestamp_dt DESC
            LIMIT $3
        """, upload_id, f'%{search_term}%', limit)

        return [dict(row) for row in rows]
