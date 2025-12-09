"""
Database operations for location data extracted from UFDR files.

This module provides async functions to interact with the locations tables.
"""

import asyncpg
import os
import json
from typing import List, Dict, Any, Optional
import logging
from .connection import get_db_connection, get_db_pool

logger = logging.getLogger(__name__)


async def init_locations_schema():
    """Initialize the locations database schema."""
    schema_path = os.path.join(
        os.path.dirname(__file__),
        'locations_schema.sql'
    )

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    async with get_db_connection() as conn:
        await conn.execute(schema_sql)
        logger.info("Locations schema initialized successfully")


async def create_location_extraction_job(upload_id: str, ufdr_filename: str):
    """Create a new location extraction job."""
    async with get_db_connection() as conn:
        await conn.execute("""
            INSERT INTO location_extractions (upload_id, ufdr_filename, extraction_status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (upload_id) DO UPDATE
            SET ufdr_filename = EXCLUDED.ufdr_filename,
                updated_at = CURRENT_TIMESTAMP
        """, upload_id, ufdr_filename)

    logger.info(f"Created location extraction job for upload_id: {upload_id}")


async def update_location_extraction_status(
    upload_id: str,
    status: str,
    total_locations: Optional[int] = None,
    processed_locations: Optional[int] = None,
    error_message: Optional[str] = None
):
    """Update the status of a location extraction job."""
    async with get_db_connection() as conn:
        updates = ["extraction_status = $2", "updated_at = CURRENT_TIMESTAMP"]
        params = [upload_id, status]
        param_idx = 3

        if total_locations is not None:
            updates.append(f"total_locations = ${param_idx}")
            params.append(total_locations)
            param_idx += 1

        if processed_locations is not None:
            updates.append(f"processed_locations = ${param_idx}")
            params.append(processed_locations)
            param_idx += 1

        if error_message is not None:
            updates.append(f"error_message = ${param_idx}")
            params.append(error_message)
            param_idx += 1

        query = f"""
            UPDATE location_extractions
            SET {', '.join(updates)}
            WHERE upload_id = $1
        """

        await conn.execute(query, *params)

    logger.info(f"Updated location extraction status for {upload_id}: {status}")


async def bulk_insert_locations(upload_id: str, locations: List[Dict[str, Any]]):
    """Bulk insert locations."""
    if not locations:
        return

    async with get_db_connection() as conn:
        # Prepare location records
        location_records = []

        for location in locations:
            # Prepare raw_json by converting datetime to string
            location_json = location.copy()
            if location_json.get('location_timestamp_dt'):
                location_json['location_timestamp_dt'] = location_json['location_timestamp_dt'].isoformat()

            # Prepare main location record
            record = (
                upload_id,
                location.get('location_id'),
                location.get('source_app'),
                location.get('latitude'),
                location.get('longitude'),
                location.get('altitude'),
                location.get('accuracy'),
                location.get('vertical_accuracy'),
                location.get('bearing'),
                location.get('speed'),
                location.get('location_type'),
                location.get('category'),
                location.get('address'),
                location.get('city'),
                location.get('state'),
                location.get('country'),
                location.get('postal_code'),
                location.get('location_timestamp'),
                location.get('location_timestamp_dt'),  # Keep as datetime for database
                location.get('device_name'),
                location.get('platform'),
                location.get('confidence'),
                location.get('activity_type'),
                location.get('activity_confidence'),
                location.get('deleted_state'),
                location.get('decoding_confidence'),
                location.get('raw_xml'),
                json.dumps(location_json),  # raw_json with datetime converted to string
            )
            location_records.append(record)

        # Insert locations
        await conn.executemany("""
            INSERT INTO locations (
                upload_id, location_id, source_app, latitude, longitude, altitude,
                accuracy, vertical_accuracy, bearing, speed, location_type, category,
                address, city, state, country, postal_code,
                location_timestamp, location_timestamp_dt,
                device_name, platform, confidence,
                activity_type, activity_confidence,
                deleted_state, decoding_confidence, raw_xml, raw_json
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15,
                      $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28)
        """, location_records)

    logger.info(f"Bulk inserted {len(locations)} locations for upload_id: {upload_id}")


async def get_location_extraction_status(upload_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a location extraction job."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM location_extractions
            WHERE upload_id = $1
        """, upload_id)

        if row:
            return dict(row)
        return None


async def get_locations(
    upload_id: str,
    source_app: Optional[str] = None,
    location_type: Optional[str] = None,
    activity_type: Optional[str] = None,
    min_latitude: Optional[float] = None,
    max_latitude: Optional[float] = None,
    min_longitude: Optional[float] = None,
    max_longitude: Optional[float] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get locations with optional filtering."""
    query = "SELECT * FROM locations WHERE upload_id = $1"
    params = [upload_id]
    param_idx = 2

    if source_app:
        query += f" AND source_app = ${param_idx}"
        params.append(source_app)
        param_idx += 1

    if location_type:
        query += f" AND location_type = ${param_idx}"
        params.append(location_type)
        param_idx += 1

    if activity_type:
        query += f" AND activity_type = ${param_idx}"
        params.append(activity_type)
        param_idx += 1

    if min_latitude is not None:
        query += f" AND latitude >= ${param_idx}"
        params.append(min_latitude)
        param_idx += 1

    if max_latitude is not None:
        query += f" AND latitude <= ${param_idx}"
        params.append(max_latitude)
        param_idx += 1

    if min_longitude is not None:
        query += f" AND longitude >= ${param_idx}"
        params.append(min_longitude)
        param_idx += 1

    if max_longitude is not None:
        query += f" AND longitude <= ${param_idx}"
        params.append(max_longitude)
        param_idx += 1

    query += f" ORDER BY location_timestamp_dt DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    async with get_db_connection() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_location_statistics(upload_id: str) -> Dict[str, Any]:
    """Get statistics about locations."""
    async with get_db_connection() as conn:
        # Total locations
        total_locations = await conn.fetchval("""
            SELECT COUNT(*) FROM locations
            WHERE upload_id = $1
        """, upload_id)

        # Locations by app
        app_stats = await conn.fetch("""
            SELECT source_app, COUNT(*) as count
            FROM locations
            WHERE upload_id = $1
            GROUP BY source_app
            ORDER BY count DESC
        """, upload_id)

        # Locations by type
        type_stats = await conn.fetch("""
            SELECT location_type, COUNT(*) as count
            FROM locations
            WHERE upload_id = $1
            GROUP BY location_type
            ORDER BY count DESC
        """, upload_id)

        # Locations by activity
        activity_stats = await conn.fetch("""
            SELECT activity_type, COUNT(*) as count
            FROM locations
            WHERE upload_id = $1 AND activity_type IS NOT NULL
            GROUP BY activity_type
            ORDER BY count DESC
        """, upload_id)

        # Geographic bounds
        bounds = await conn.fetchrow("""
            SELECT
                MIN(latitude) as min_lat,
                MAX(latitude) as max_lat,
                MIN(longitude) as min_lng,
                MAX(longitude) as max_lng
            FROM locations
            WHERE upload_id = $1 AND latitude IS NOT NULL AND longitude IS NOT NULL
        """, upload_id)

        # Date range
        date_range = await conn.fetchrow("""
            SELECT
                MIN(location_timestamp_dt) as first_location,
                MAX(location_timestamp_dt) as last_location
            FROM locations
            WHERE upload_id = $1 AND location_timestamp_dt IS NOT NULL
        """, upload_id)

        # Locations with addresses
        address_stats = await conn.fetchrow("""
            SELECT
                SUM(CASE WHEN address IS NOT NULL AND address != '' THEN 1 ELSE 0 END) as with_address,
                SUM(CASE WHEN address IS NULL OR address = '' THEN 1 ELSE 0 END) as without_address
            FROM locations
            WHERE upload_id = $1
        """, upload_id)

        return {
            'total_locations': total_locations,
            'with_address': address_stats['with_address'] if address_stats else 0,
            'without_address': address_stats['without_address'] if address_stats else 0,
            'first_location_date': date_range['first_location'].isoformat() if date_range and date_range['first_location'] else None,
            'last_location_date': date_range['last_location'].isoformat() if date_range and date_range['last_location'] else None,
            'geographic_bounds': {
                'min_latitude': float(bounds['min_lat']) if bounds and bounds['min_lat'] else None,
                'max_latitude': float(bounds['max_lat']) if bounds and bounds['max_lat'] else None,
                'min_longitude': float(bounds['min_lng']) if bounds and bounds['min_lng'] else None,
                'max_longitude': float(bounds['max_lng']) if bounds and bounds['max_lng'] else None,
            } if bounds else None,
            'by_app': [dict(row) for row in app_stats],
            'by_type': [dict(row) for row in type_stats],
            'by_activity': [dict(row) for row in activity_stats],
        }
