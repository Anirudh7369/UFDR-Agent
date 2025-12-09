"""
Call logs tool for forensic agent to query call logs data from the database.

This module provides a tool that allows the forensic agent to retrieve call logs data
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


class CallLogRecord(BaseModel):
    """Represents a single call log record from the database."""

    source_app: Optional[str] = Field(None, description="App that made the call")
    direction: Optional[str] = Field(None, description="Incoming or Outgoing")
    call_type: Optional[str] = Field(None, description="Voice, Video, etc.")
    status: Optional[str] = Field(None, description="Established, Missed, Rejected, etc.")
    call_timestamp_dt: Optional[str] = Field(None, description="Call time as ISO datetime string")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    duration_string: Optional[str] = Field(None, description="Duration as string (00:01:17)")
    is_video_call: Optional[bool] = Field(None, description="Whether this is a video call")
    from_party_identifier: Optional[str] = Field(None, description="Caller phone number or user ID")
    from_party_name: Optional[str] = Field(None, description="Caller name")
    to_party_identifier: Optional[str] = Field(None, description="Recipient phone number or user ID")
    to_party_name: Optional[str] = Field(None, description="Recipient name")
    deleted_state: Optional[str] = Field(None, description="Intact, Deleted, etc.")
    decoding_confidence: Optional[str] = Field(None, description="High, Medium, Low")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "source_app": "WhatsApp",
                "direction": "Outgoing",
                "call_type": "Voice",
                "status": "Established",
                "call_timestamp_dt": "2023-06-15T14:30:00",
                "duration_seconds": 125,
                "from_party_name": "User"
            }
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "CallLogRecord":
        """Create CallLogRecord from database row."""
        return cls(
            source_app=row.get('source_app'),
            direction=row.get('direction'),
            call_type=row.get('call_type'),
            status=row.get('status'),
            call_timestamp_dt=row.get('call_timestamp_dt').isoformat() if row.get('call_timestamp_dt') else None,
            duration_seconds=row.get('duration_seconds'),
            duration_string=row.get('duration_string'),
            is_video_call=row.get('is_video_call'),
            from_party_identifier=row.get('from_party_identifier'),
            from_party_name=row.get('from_party_name'),
            to_party_identifier=row.get('to_party_identifier'),
            to_party_name=row.get('to_party_name'),
            deleted_state=row.get('deleted_state'),
            decoding_confidence=row.get('decoding_confidence'),
        )


class ColumnValueCount(BaseModel):
    """Represents a column value with its count (for aggregate queries)."""

    value: str = Field(..., description="The unique value in the column")
    count: int = Field(..., description="Number of call logs with this value")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "value": "WhatsApp",
                "count": 523
            }
        }


class CallLogFilterResult(BaseModel):
    """Result of a filtered call log query."""

    query_type: QueryType = Field(QueryType.FILTER, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    total_count: int = Field(..., description="Total number of matching call logs")
    returned_count: int = Field(..., description="Number of call logs returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    filters_applied: List[str] = Field(..., description="List of filters that were applied")
    call_logs: List[CallLogRecord] = Field(default_factory=list, description="List of call log records")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "filter",
                "success": True,
                "total_count": 523,
                "returned_count": 100,
                "query_description": "Get call logs where source_app=WhatsApp",
                "filters_applied": ["source_app=WhatsApp"],
                "call_logs": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"📞 Call Log Query Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Filters: {', '.join(self.filters_applied)}\n"
        summary += f"Total matches: {self.total_count:,}\n"
        summary += f"Returned: {self.returned_count:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_count == 0:
            summary += "⚠️  No call logs matched the query criteria.\n"
        else:
            summary += "Sample Call Logs:\n\n"
            for i, call in enumerate(self.call_logs[:10], 1):
                summary += f"{i}. "

                # Call type indicator
                call_icon = "📹" if call.is_video_call else "📞"
                summary += f"{call_icon} {call.direction or 'Unknown Direction'} {call.call_type or 'Call'}\n"

                # Parties
                if call.direction == "Outgoing":
                    if call.to_party_name or call.to_party_identifier:
                        summary += f"   👤 To: {call.to_party_name or call.to_party_identifier}\n"
                else:
                    if call.from_party_name or call.from_party_identifier:
                        summary += f"   👤 From: {call.from_party_name or call.from_party_identifier}\n"

                # Status and duration
                if call.status:
                    summary += f"   📊 Status: {call.status}\n"
                if call.duration_seconds is not None:
                    mins = call.duration_seconds // 60
                    secs = call.duration_seconds % 60
                    summary += f"   ⏱️  Duration: {mins}m {secs}s\n"

                # Time
                if call.call_timestamp_dt:
                    summary += f"   🕐 Time: {call.call_timestamp_dt}\n"

                # Source app
                if call.source_app:
                    summary += f"   📱 App: {call.source_app}\n"

                # State
                if call.deleted_state:
                    summary += f"   🗑️  State: {call.deleted_state}\n"

                summary += "\n"

            if self.total_count > 10:
                summary += f"... and {self.total_count - 10:,} more call logs.\n"

        return summary


class CallLogAggregateResult(BaseModel):
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
                "column_name": "source_app",
                "total_unique_values": 5,
                "returned_count": 5,
                "query_description": "Get all unique values for column 'source_app'",
                "values": [
                    {"value": "WhatsApp", "count": 523},
                    {"value": "Telegram", "count": 142}
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
            total_calls = sum(v.count for v in self.values)

            for i, val in enumerate(self.values[:20], 1):
                percentage = (val.count / total_calls * 100) if total_calls > 0 else 0
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length

                summary += f"{i:2d}. {val.value:30s} │ {val.count:6,} ({percentage:5.1f}%) {bar}\n"

            if self.total_unique_values > 20:
                remaining = self.total_unique_values - 20
                remaining_count = sum(v.count for v in self.values[20:])
                summary += f"\n... and {remaining:,} more values ({remaining_count:,} calls).\n"

            summary += f"\n📈 Total call logs analyzed: {total_calls:,}\n"

        return summary


# Union type for all result types
CallLogQueryResult = Union[CallLogFilterResult, CallLogAggregateResult]


class CallLogFilter(BaseModel):
    """Input model for call log query filters."""

    col1: str = Field(
        ...,
        description="First column filter in format 'column:value'. Example: 'source_app:WhatsApp' or 'source_app:all'",
        json_schema_extra={"example": "source_app:WhatsApp"}
    )
    col2: Optional[str] = Field(
        None,
        description="Optional second column filter in format 'column:value'",
        json_schema_extra={"example": "direction:Outgoing"}
    )
    col3: Optional[str] = Field(
        None,
        description="Optional third column filter in format 'column:value'",
        json_schema_extra={"example": "status:Missed"}
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return (1-1000)"
    )


async def query_call_logs(
    col1: str,
    col2: Optional[str] = None,
    col3: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query the call_logs table based on column filters.

    This tool retrieves call logs data from the forensic database based on specified column filters.
    Each column filter should be in the format "column_name:value".

    Special handling:
    - If value is "all" (e.g., "source_app:all"), returns all unique values for that column
    - Multiple filters are combined with AND logic
    - Results are limited to prevent overwhelming responses

    Available Columns:
    - source_app: App that made the call (WhatsApp, Telegram, Phone, Skype, Viber, etc.)
    - direction: Call direction (Incoming, Outgoing)
    - call_type: Type of call (Voice, Video)
    - status: Call status (Established, Missed, Rejected, Cancelled, etc.)
    - is_video_call: Boolean (true/false)
    - from_party_identifier: Caller phone number or user ID
    - to_party_identifier: Recipient phone number or user ID
    - deleted_state: Deletion state (Intact, Deleted)
    - decoding_confidence: Forensic confidence (High, Medium, Low)

    Args:
        col1: First column filter in format "column:value" (required).
              Example: "source_app:WhatsApp" or "direction:Outgoing" or "source_app:all"
        col2: Second optional column filter in format "column:value"
              Example: "status:Missed"
        col3: Third optional column filter in format "column:value"
              Example: "deleted_state:Intact"
        limit: Maximum number of results to return (default: 100, max: 1000)

    Returns:
        A formatted string containing the query results with call log details

    Examples:
        - query_call_logs("source_app:WhatsApp") - Get all WhatsApp calls
        - query_call_logs("direction:Incoming", "status:Missed") - Get all missed incoming calls
        - query_call_logs("source_app:all") - Get all unique apps with their call counts
        - query_call_logs("is_video_call:true") - Get all video calls
    """
    # Log tool invocation (both to logger and console)
    log_message = f"""
{'=' * 80}
🔧 CALL LOG TOOL CALLED
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
            result = CallLogFilterResult(
                success=False,
                total_count=0,
                returned_count=0,
                query_description="No filters provided",
                filters_applied=[],
                call_logs=[],
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
                result = CallLogFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid filter format: {filter_str}",
                    filters_applied=[],
                    call_logs=[],
                    error_message=f"Filter must be in format 'column:value', got '{filter_str}'"
                )
                return result.to_summary()

            column, value = filter_str.split(':', 1)
            column = column.strip()
            value = value.strip()

            # Validate column name (prevent SQL injection)
            valid_columns = {
                'source_app', 'direction', 'call_type', 'status',
                'is_video_call', 'from_party_identifier', 'to_party_identifier',
                'deleted_state', 'decoding_confidence'
            }

            if column not in valid_columns:
                result = CallLogFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid column: {column}",
                    filters_applied=[],
                    call_logs=[],
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
                    FROM call_logs
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

                result = CallLogAggregateResult(
                    success=True,
                    column_name=all_column,
                    total_unique_values=total_count,
                    returned_count=len(values),
                    query_description=query_description,
                    values=values
                )

                output = result.to_summary()
                success_msg = f"""
✅ CALL LOG TOOL - Aggregate Query Success
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
                query_description = "Get call logs where " + " AND ".join(query_parts)

                # Count total matching records
                count_query = f"SELECT COUNT(*) FROM call_logs WHERE {where_clause}"
                total_count = await conn.fetchval(count_query, *filter_params)

                # Fetch call log records
                query = f"""
                    SELECT
                        source_app, direction, call_type, status,
                        call_timestamp_dt, duration_seconds, duration_string,
                        is_video_call,
                        from_party_identifier, from_party_name,
                        to_party_identifier, to_party_name,
                        deleted_state, decoding_confidence
                    FROM call_logs
                    WHERE {where_clause}
                    ORDER BY call_timestamp_dt DESC
                    LIMIT ${param_idx}
                """
                filter_params.append(limit)

                rows = await conn.fetch(query, *filter_params)

                # Convert to CallLogRecord objects
                call_logs = [CallLogRecord.from_db_row(dict(row)) for row in rows]

                result = CallLogFilterResult(
                    success=True,
                    total_count=total_count,
                    returned_count=len(call_logs),
                    query_description=query_description,
                    filters_applied=query_parts,
                    call_logs=call_logs
                )

                output = result.to_summary()
                success_msg = f"""
✅ CALL LOG TOOL - Filter Query Success
Total Matches: {total_count}, Returned: {len(call_logs)}
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
❌ CALL LOG TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = CallLogFilterResult(
            success=False,
            total_count=0,
            returned_count=0,
            query_description="Query failed",
            filters_applied=[],
            call_logs=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
call_log_tool = function_tool(
    query_call_logs,
    name_override="query_call_logs",
    description_override="Query call logs data from the forensic database based on column filters"
)
