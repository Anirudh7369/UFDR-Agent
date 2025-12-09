"""
App tool for forensic agent to query installed apps data from the database.

This module provides a tool that allows the forensic agent to retrieve installed apps data
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


class AppRecord(BaseModel):
    """Represents a single app record from the database."""

    app_identifier: Optional[str] = Field(None, description="Android package name")
    app_name: Optional[str] = Field(None, description="User-visible app name")
    app_version: Optional[str] = Field(None, description="App version string")
    app_guid: Optional[str] = Field(None, description="App GUID if available")
    install_timestamp: Optional[int] = Field(None, description="Install time (milliseconds since epoch)")
    install_timestamp_dt: Optional[str] = Field(None, description="Install time as ISO datetime string")
    last_launched_timestamp: Optional[int] = Field(None, description="Last launched time (milliseconds since epoch)")
    last_launched_dt: Optional[str] = Field(None, description="Last launched time as ISO datetime string")
    decoding_status: Optional[str] = Field(None, description="Decoded, NotDecoded, etc.")
    is_emulatable: Optional[bool] = Field(None, description="Whether app is emulatable")
    operation_mode: Optional[str] = Field(None, description="Foreground, Background, etc.")
    deleted_state: Optional[str] = Field(None, description="Intact, Deleted, etc.")
    decoding_confidence: Optional[str] = Field(None, description="High, Medium, Low")
    permissions: Optional[List[str]] = Field(None, description="List of permission categories")
    categories: Optional[List[str]] = Field(None, description="List of app categories")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "app_identifier": "com.whatsapp",
                "app_name": "WhatsApp Messenger",
                "app_version": "2.23.10.75",
                "install_timestamp_dt": "2023-06-15T14:30:00",
                "categories": ["Communication", "Social"]
            }
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "AppRecord":
        """Create AppRecord from database row."""
        return cls(
            app_identifier=row.get('app_identifier'),
            app_name=row.get('app_name'),
            app_version=row.get('app_version'),
            app_guid=row.get('app_guid'),
            install_timestamp=row.get('install_timestamp'),
            install_timestamp_dt=row.get('install_timestamp_dt').isoformat() if row.get('install_timestamp_dt') else None,
            last_launched_timestamp=row.get('last_launched_timestamp'),
            last_launched_dt=row.get('last_launched_dt').isoformat() if row.get('last_launched_dt') else None,
            decoding_status=row.get('decoding_status'),
            is_emulatable=row.get('is_emulatable'),
            operation_mode=row.get('operation_mode'),
            deleted_state=row.get('deleted_state'),
            decoding_confidence=row.get('decoding_confidence'),
            permissions=row.get('permissions'),
            categories=row.get('categories'),
        )


class ColumnValueCount(BaseModel):
    """Represents a column value with its count (for aggregate queries)."""

    value: str = Field(..., description="The unique value in the column")
    count: int = Field(..., description="Number of apps with this value")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "value": "WhatsApp Messenger",
                "count": 1
            }
        }


class AppFilterResult(BaseModel):
    """Result of a filtered app query."""

    query_type: QueryType = Field(QueryType.FILTER, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    total_count: int = Field(..., description="Total number of matching apps")
    returned_count: int = Field(..., description="Number of apps returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    filters_applied: List[str] = Field(..., description="List of filters that were applied")
    apps: List[AppRecord] = Field(default_factory=list, description="List of app records")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "filter",
                "success": True,
                "total_count": 150,
                "returned_count": 100,
                "query_description": "Get apps where deleted_state=Deleted",
                "filters_applied": ["deleted_state=Deleted"],
                "apps": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"📱 App Query Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Filters: {', '.join(self.filters_applied)}\n"
        summary += f"Total matches: {self.total_count:,}\n"
        summary += f"Returned: {self.returned_count:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_count == 0:
            summary += "⚠️  No apps matched the query criteria.\n"
        else:
            summary += "Sample Apps:\n\n"
            for i, app in enumerate(self.apps[:10], 1):
                summary += f"{i}. "

                # App identifier
                if app.app_name:
                    summary += f"📱 {app.app_name}\n"
                elif app.app_identifier:
                    summary += f"📱 {app.app_identifier}\n"
                else:
                    summary += f"📱 Unknown App\n"

                # Package name
                if app.app_identifier:
                    summary += f"   📦 Package: {app.app_identifier}\n"

                # Version
                if app.app_version:
                    summary += f"   🔢 Version: {app.app_version}\n"

                # Install date
                if app.install_timestamp_dt:
                    summary += f"   📅 Installed: {app.install_timestamp_dt}\n"

                # Last launched
                if app.last_launched_dt:
                    summary += f"   🕐 Last Launched: {app.last_launched_dt}\n"

                # Categories
                if app.categories:
                    summary += f"   🏷️  Categories: {', '.join(app.categories)}\n"

                # State
                if app.deleted_state:
                    summary += f"   🗑️  State: {app.deleted_state}\n"

                # Permissions count
                if app.permissions:
                    summary += f"   🔐 Permissions: {len(app.permissions)}\n"

                summary += "\n"

            if self.total_count > 10:
                summary += f"... and {self.total_count - 10:,} more apps.\n"

        return summary


class AppAggregateResult(BaseModel):
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
                "column_name": "app_name",
                "total_unique_values": 150,
                "returned_count": 150,
                "query_description": "Get all unique values for column 'app_name'",
                "values": [
                    {"value": "WhatsApp Messenger", "count": 1},
                    {"value": "Instagram", "count": 1}
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
            total_apps = sum(v.count for v in self.values)

            for i, val in enumerate(self.values[:20], 1):
                percentage = (val.count / total_apps * 100) if total_apps > 0 else 0
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length

                summary += f"{i:2d}. {val.value:30s} │ {val.count:6,} ({percentage:5.1f}%) {bar}\n"

            if self.total_unique_values > 20:
                remaining = self.total_unique_values - 20
                remaining_count = sum(v.count for v in self.values[20:])
                summary += f"\n... and {remaining:,} more values ({remaining_count:,} apps).\n"

            summary += f"\n📈 Total apps analyzed: {total_apps:,}\n"

        return summary


# Union type for all result types
AppQueryResult = Union[AppFilterResult, AppAggregateResult]


class AppFilter(BaseModel):
    """Input model for app query filters."""

    col1: str = Field(
        ...,
        description="First column filter in format 'column:value'. Example: 'app_name:WhatsApp' or 'app_name:all'",
        json_schema_extra={"example": "app_name:WhatsApp"}
    )
    col2: Optional[str] = Field(
        None,
        description="Optional second column filter in format 'column:value'",
        json_schema_extra={"example": "deleted_state:Intact"}
    )
    col3: Optional[str] = Field(
        None,
        description="Optional third column filter in format 'column:value'",
        json_schema_extra={"example": "decoding_confidence:High"}
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return (1-1000)"
    )


async def query_apps(
    col1: str,
    col2: Optional[str] = None,
    col3: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query the installed_apps table based on column filters.

    This tool retrieves installed apps data from the forensic database based on specified column filters.
    Each column filter should be in the format "column_name:value".

    Special handling:
    - If value is "all" (e.g., "app_name:all"), returns all unique values for that column
    - Multiple filters are combined with AND logic
    - Results are limited to prevent overwhelming responses

    Available Columns:
    - app_identifier: Android package name (e.g., com.whatsapp, com.instagram.android)
    - app_name: User-visible app name (e.g., "WhatsApp Messenger", "Instagram")
    - app_version: Version string (e.g., "2.23.10.75")
    - app_guid: App GUID if available
    - decoding_status: Decoded, NotDecoded, etc.
    - is_emulatable: Boolean (true/false)
    - operation_mode: Foreground, Background
    - deleted_state: Intact, Deleted
    - decoding_confidence: High, Medium, Low

    Args:
        col1: First column filter in format "column:value" (required).
              Example: "app_name:WhatsApp" or "deleted_state:Deleted" or "app_name:all"
        col2: Second optional column filter in format "column:value"
              Example: "deleted_state:Intact"
        col3: Third optional column filter in format "column:value"
              Example: "decoding_confidence:High"
        limit: Maximum number of results to return (default: 100, max: 1000)

    Returns:
        A formatted string containing the query results with app details

    Examples:
        - query_apps("app_name:WhatsApp") - Get all WhatsApp apps
        - query_apps("deleted_state:Deleted") - Get all deleted apps
        - query_apps("app_name:all") - Get all unique app names with their counts
        - query_apps("decoding_confidence:High", "deleted_state:Intact") - Get high confidence intact apps
    """
    # Log tool invocation (both to logger and console)
    log_message = f"""
{'=' * 80}
🔧 APP TOOL CALLED
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
            result = AppFilterResult(
                success=False,
                total_count=0,
                returned_count=0,
                query_description="No filters provided",
                filters_applied=[],
                apps=[],
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
                result = AppFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid filter format: {filter_str}",
                    filters_applied=[],
                    apps=[],
                    error_message=f"Filter must be in format 'column:value', got '{filter_str}'"
                )
                return result.to_summary()

            column, value = filter_str.split(':', 1)
            column = column.strip()
            value = value.strip()

            # Validate column name (prevent SQL injection)
            valid_columns = {
                'app_identifier', 'app_name', 'app_version', 'app_guid',
                'install_timestamp', 'last_launched_timestamp',
                'decoding_status', 'is_emulatable', 'operation_mode',
                'deleted_state', 'decoding_confidence'
            }

            if column not in valid_columns:
                result = AppFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid column: {column}",
                    filters_applied=[],
                    apps=[],
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
                    FROM installed_apps
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

                result = AppAggregateResult(
                    success=True,
                    column_name=all_column,
                    total_unique_values=total_count,
                    returned_count=len(values),
                    query_description=query_description,
                    values=values
                )

                output = result.to_summary()
                success_msg = f"""
✅ APP TOOL - Aggregate Query Success
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
                query_description = "Get apps where " + " AND ".join(query_parts)

                # Count total matching records
                count_query = f"SELECT COUNT(*) FROM installed_apps WHERE {where_clause}"
                total_count = await conn.fetchval(count_query, *filter_params)

                # Fetch app records
                query = f"""
                    SELECT
                        app_identifier, app_name, app_version, app_guid,
                        install_timestamp, install_timestamp_dt,
                        last_launched_timestamp, last_launched_dt,
                        decoding_status, is_emulatable, operation_mode,
                        deleted_state, decoding_confidence,
                        permissions, categories
                    FROM installed_apps
                    WHERE {where_clause}
                    ORDER BY install_timestamp_dt DESC
                    LIMIT ${param_idx}
                """
                filter_params.append(limit)

                rows = await conn.fetch(query, *filter_params)

                # Convert to AppRecord objects
                apps = [AppRecord.from_db_row(dict(row)) for row in rows]

                result = AppFilterResult(
                    success=True,
                    total_count=total_count,
                    returned_count=len(apps),
                    query_description=query_description,
                    filters_applied=query_parts,
                    apps=apps
                )

                output = result.to_summary()
                success_msg = f"""
✅ APP TOOL - Filter Query Success
Total Matches: {total_count}, Returned: {len(apps)}
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
❌ APP TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = AppFilterResult(
            success=False,
            total_count=0,
            returned_count=0,
            query_description="Query failed",
            filters_applied=[],
            apps=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
app_tool = function_tool(
    query_apps,
    name_override="query_apps",
    description_override="Query installed apps data from the forensic database based on column filters"
)
