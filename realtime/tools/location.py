"""
Location tool for forensic agent to query location data from the database.

This module provides a tool that allows the forensic agent to retrieve location data
based on various column filters.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum
from agents import function_tool
from utils.db.connection import get_db_connection
import logging

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Type of query being executed."""
    FILTER = "filter"  # Standard WHERE clause query
    AGGREGATE = "aggregate"  # Get all unique values for a column


class LocationRecord(BaseModel):
    """Represents a single location record from the database."""

    source_app: Optional[str] = Field(None, description="Application that recorded this location")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    accuracy: Optional[float] = Field(None, description="Horizontal accuracy in meters")
    location_type: Optional[str] = Field(None, description="Type of location recording")
    category: Optional[str] = Field(None, description="Semantic category of location")
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="State/province name")
    country: Optional[str] = Field(None, description="Country name")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    location_timestamp: Optional[int] = Field(None, description="Unix timestamp")
    location_timestamp_dt: Optional[str] = Field(None, description="ISO datetime string")
    device_name: Optional[str] = Field(None, description="Device name")
    platform: Optional[str] = Field(None, description="Operating system platform")
    deleted_state: Optional[str] = Field(None, description="Deletion state")
    decoding_confidence: Optional[str] = Field(None, description="Forensic decoding confidence")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "source_app": "WhatsApp",
                "latitude": 26.9124,
                "longitude": 75.7873,
                "city": "Jaipur",
                "country": "India",
                "location_timestamp_dt": "2023-06-15T14:30:00"
            }
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "LocationRecord":
        """Create LocationRecord from database row."""
        return cls(
            source_app=row.get('source_app'),
            latitude=float(row.get('latitude')) if row.get('latitude') is not None else None,
            longitude=float(row.get('longitude')) if row.get('longitude') is not None else None,
            altitude=float(row.get('altitude')) if row.get('altitude') is not None else None,
            accuracy=float(row.get('accuracy')) if row.get('accuracy') is not None else None,
            location_type=row.get('location_type'),
            category=row.get('category'),
            address=row.get('address'),
            city=row.get('city'),
            state=row.get('state'),
            country=row.get('country'),
            postal_code=row.get('postal_code'),
            location_timestamp=row.get('location_timestamp'),
            location_timestamp_dt=row.get('location_timestamp_dt').isoformat() if row.get('location_timestamp_dt') else None,
            device_name=row.get('device_name'),
            platform=row.get('platform'),
            deleted_state=row.get('deleted_state'),
            decoding_confidence=row.get('decoding_confidence'),
        )


class ColumnValueCount(BaseModel):
    """Represents a column value with its count (for aggregate queries)."""

    value: str = Field(..., description="The unique value in the column")
    count: int = Field(..., description="Number of locations with this value")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "value": "Jaipur",
                "count": 1523
            }
        }


class LocationFilterResult(BaseModel):
    """Result of a filtered location query."""

    query_type: QueryType = Field(QueryType.FILTER, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    total_count: int = Field(..., description="Total number of matching locations")
    returned_count: int = Field(..., description="Number of locations returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    filters_applied: List[str] = Field(..., description="List of filters that were applied")
    locations: List[LocationRecord] = Field(default_factory=list, description="List of location records")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "filter",
                "success": True,
                "total_count": 1523,
                "returned_count": 100,
                "query_description": "Get locations where city=Jaipur AND source_app=WhatsApp",
                "filters_applied": ["city=Jaipur", "source_app=WhatsApp"],
                "locations": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"📍 Location Query Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Filters: {', '.join(self.filters_applied)}\n"
        summary += f"Total matches: {self.total_count:,}\n"
        summary += f"Returned: {self.returned_count:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_count == 0:
            summary += "⚠️  No locations matched the query criteria.\n"
        else:
            summary += "Sample Locations:\n\n"
            for i, loc in enumerate(self.locations[:10], 1):
                summary += f"{i}. "

                # Location identifier
                if loc.address:
                    summary += f"📍 {loc.address}\n"
                elif loc.city:
                    summary += f"📍 {loc.city}, {loc.state or loc.country or 'Unknown'}\n"
                else:
                    summary += f"📍 Location (no address)\n"

                # Coordinates
                if loc.latitude and loc.longitude:
                    summary += f"   🌐 Coordinates: ({loc.latitude:.6f}, {loc.longitude:.6f})\n"
                    if loc.accuracy:
                        summary += f"   📏 Accuracy: ±{loc.accuracy:.1f}m\n"

                # Source and time
                if loc.source_app:
                    summary += f"   📱 Source: {loc.source_app}\n"
                if loc.location_timestamp_dt:
                    summary += f"   🕐 Time: {loc.location_timestamp_dt}\n"

                # Additional context
                if loc.category:
                    summary += f"   🏷️  Category: {loc.category}\n"
                if loc.deleted_state:
                    summary += f"   🗑️  State: {loc.deleted_state}\n"

                summary += "\n"

            if self.total_count > 10:
                summary += f"... and {self.total_count - 10:,} more locations.\n"

        return summary


class LocationAggregateResult(BaseModel):
    """Result of an aggregate query (get all values in a column)."""

    query_type: QueryType = Field(QueryType.AGGREGATE, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    column_name: str = Field(..., description="Column that was aggregated")
    total_unique_values: int = Field(..., description="Total number of unique values")
    returned_count: int = Field(..., description="Number of values returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    values: List[ColumnValueCount] = Field(default_factory=list, description="List of values with counts")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "aggregate",
                "success": True,
                "column_name": "city",
                "total_unique_values": 45,
                "returned_count": 45,
                "query_description": "Get all unique values for column 'city'",
                "values": [
                    {"value": "Jaipur", "count": 1523},
                    {"value": "Delhi", "count": 890}
                ]
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"📊 Column Analysis: {self.column_name}\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Total unique values: {self.total_unique_values:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_unique_values == 0:
            summary += f"⚠️  No values found in column '{self.column_name}'.\n"
        else:
            summary += f"Top values in '{self.column_name}':\n\n"

            # Calculate total for percentage
            total_locations = sum(v.count for v in self.values)

            for i, val in enumerate(self.values[:20], 1):
                percentage = (val.count / total_locations * 100) if total_locations > 0 else 0
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length

                summary += f"{i:2d}. {val.value:30s} │ {val.count:6,} ({percentage:5.1f}%) {bar}\n"

            if self.total_unique_values > 20:
                remaining = self.total_unique_values - 20
                remaining_count = sum(v.count for v in self.values[20:])
                summary += f"\n... and {remaining:,} more values ({remaining_count:,} locations).\n"

            summary += f"\n📈 Total locations analyzed: {total_locations:,}\n"

        return summary


# Union type for all result types
LocationQueryResult = Union[LocationFilterResult, LocationAggregateResult]


class LocationFilter(BaseModel):
    """Input model for location query filters."""

    col1: str = Field(
        ...,
        description="First column filter in format 'column:value'. Example: 'city:Jaipur' or 'city:all'",
        json_schema_extra={"example": "city:Jaipur"}
    )
    col2: Optional[str] = Field(
        None,
        description="Optional second column filter in format 'column:value'",
        json_schema_extra={"example": "source_app:WhatsApp"}
    )
    col3: Optional[str] = Field(
        None,
        description="Optional third column filter in format 'column:value'",
        json_schema_extra={"example": "country:India"}
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return (1-1000)"
    )


async def query_locations(
    col1: str,
    col2: Optional[str] = None,
    col3: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query the locations table based on column filters.

    This tool retrieves location data from the forensic database based on specified column filters.
    Each column filter should be in the format "column_name:value".

    Special handling:
    - If value is "all" (e.g., "city:all"), returns all unique values for that column
    - Multiple filters are combined with AND logic
    - Results are limited to prevent overwhelming responses

    Available Columns:
    - source_app: Application that recorded the location (WhatsApp, Instagram, etc.)
    - city: City name
    - state: State/province name
    - country: Country name
    - address: Street address
    - category: Location category (Home, Work, Restaurant, etc.)
    - location_type: Type of recording (GPS, Network, WiFi, etc.)
    - platform: OS platform (Android, iOS)
    - device_name: Device name
    - deleted_state: Deletion state (Deleted, Active)
    - decoding_confidence: Forensic confidence (High, Medium, Low)
    - postal_code: ZIP/postal code
    - latitude, longitude, altitude, accuracy: Coordinate values

    Args:
        col1: First column filter in format "column:value" (required).
              Example: "city:Jaipur" or "source_app:WhatsApp" or "city:all"
        col2: Second optional column filter in format "column:value"
              Example: "source_app:WhatsApp"
        col3: Third optional column filter in format "column:value"
              Example: "country:India"
        limit: Maximum number of results to return (default: 100, max: 1000)

    Returns:
        A formatted string containing the query results with location details

    Examples:
        - query_locations("city:Jaipur") - Get all locations in Jaipur
        - query_locations("city:Jaipur", "source_app:WhatsApp") - Get WhatsApp locations in Jaipur
        - query_locations("city:all") - Get all unique cities with their location counts
        - query_locations("source_app:all") - Get all apps that recorded locations
        - query_locations("deleted_state:Deleted") - Get all deleted location entries
    """
    # Log tool invocation (both to logger and console)
    log_message = f"""
{'=' * 80}
🔧 LOCATION TOOL CALLED
{'=' * 80}
Input Parameters:
  col1: {col1}
  col2: {col2}
  col3: {col3}
  limit: {limit}
{'=' * 80}
"""
    print(log_message)  # Print to console
    logger.info(log_message)  # Log to file

    try:
        # Parse column filters
        filters = []
        for col_filter in [col1, col2, col3]:
            if col_filter:
                filters.append(col_filter)

        if not filters:
            result = LocationFilterResult(
                success=False,
                total_count=0,
                returned_count=0,
                query_description="No filters provided",
                filters_applied=[],
                locations=[],
                error_message="At least col1 must be provided"
            )
            return result.to_summary()

        # Parse each filter
        filter_conditions = []
        filter_params = []
        query_parts = []
        param_idx = 1

        # Check if this is a "get all values" query
        is_all_query = False
        all_column = None

        for filter_str in filters:
            if ':' not in filter_str:
                result = LocationFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid filter format: {filter_str}",
                    filters_applied=[],
                    locations=[],
                    error_message=f"Filter must be in format 'column:value', got '{filter_str}'"
                )
                return result.to_summary()

            column, value = filter_str.split(':', 1)
            column = column.strip()
            value = value.strip()

            # Validate column name (prevent SQL injection)
            valid_columns = {
                'source_app', 'latitude', 'longitude', 'altitude', 'accuracy',
                'location_type', 'category', 'address', 'city', 'state',
                'country', 'postal_code', 'location_timestamp', 'device_name',
                'platform', 'deleted_state', 'decoding_confidence'
            }

            if column not in valid_columns:
                result = LocationFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid column: {column}",
                    filters_applied=[],
                    locations=[],
                    error_message=f"Column '{column}' is not valid. Valid columns: {', '.join(sorted(valid_columns))}"
                )
                return result.to_summary()

            # Handle "all" special value
            if value.lower() == 'all':
                is_all_query = True
                all_column = column
                break

            # Add filter condition
            filter_conditions.append(f"{column} = ${param_idx}")
            filter_params.append(value)
            query_parts.append(f"{column}={value}")
            param_idx += 1

        # Limit validation
        if limit > 1000:
            limit = 1000
        elif limit < 1:
            limit = 100

        async with get_db_connection() as conn:
            if is_all_query:
                # Query to get all unique values for a column
                query = f"""
                    SELECT {all_column}, COUNT(*) as count
                    FROM locations
                    WHERE {all_column} IS NOT NULL
                    GROUP BY {all_column}
                    ORDER BY count DESC
                    LIMIT $1
                """
                rows = await conn.fetch(query, limit)

                total_count = len(rows)
                query_description = f"Get all unique values for column '{all_column}'"

                # Convert rows to ColumnValueCount objects
                values = [
                    ColumnValueCount(value=str(row[all_column]), count=row['count'])
                    for row in rows
                ]

                result = LocationAggregateResult(
                    success=True,
                    column_name=all_column,
                    total_unique_values=total_count,
                    returned_count=len(values),
                    query_description=query_description,
                    values=values
                )

                output = result.to_summary()
                success_msg = f"""
✅ LOCATION TOOL - Aggregate Query Success
Column: {all_column}, Unique Values: {total_count}
Output length: {len(output)} characters
{'=' * 80}
"""
                print(success_msg)
                logger.info(success_msg)
                return output

            else:
                # Build the WHERE clause
                where_clause = " AND ".join(filter_conditions)
                query_description = "Get locations where " + " AND ".join(query_parts)

                # Count total matching records
                count_query = f"SELECT COUNT(*) FROM locations WHERE {where_clause}"
                total_count = await conn.fetchval(count_query, *filter_params)

                # Fetch location records
                query = f"""
                    SELECT
                        source_app, latitude, longitude, altitude, accuracy,
                        location_type, category, address, city, state, country,
                        postal_code, location_timestamp, location_timestamp_dt,
                        device_name, platform, deleted_state, decoding_confidence
                    FROM locations
                    WHERE {where_clause}
                    ORDER BY location_timestamp_dt DESC
                    LIMIT ${param_idx}
                """
                filter_params.append(limit)

                rows = await conn.fetch(query, *filter_params)

                # Convert to LocationRecord objects
                locations = [LocationRecord.from_db_row(dict(row)) for row in rows]

                result = LocationFilterResult(
                    success=True,
                    total_count=total_count,
                    returned_count=len(locations),
                    query_description=query_description,
                    filters_applied=query_parts,
                    locations=locations
                )

                output = result.to_summary()
                success_msg = f"""
✅ LOCATION TOOL - Filter Query Success
Total Matches: {total_count}, Returned: {len(locations)}
Filters: {', '.join(query_parts)}
Output length: {len(output)} characters
{'=' * 80}
"""
                print(success_msg)
                logger.info(success_msg)
                return output

    except Exception as e:
        error_msg = f"""
{'=' * 80}
❌ LOCATION TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = LocationFilterResult(
            success=False,
            total_count=0,
            returned_count=0,
            query_description="Query failed",
            filters_applied=[],
            locations=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
location_tool = function_tool(
    query_locations,
    name_override="query_locations",
    description_override="Query location data from the forensic database based on column filters"
)
