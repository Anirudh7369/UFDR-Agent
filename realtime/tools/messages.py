"""
Messages tool for forensic agent to query messages data from the database.

This module provides a tool that allows the forensic agent to retrieve messages data
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


class MessageRecord(BaseModel):
    """Represents a single message record from the database."""

    source_app: Optional[str] = Field(None, description="App that sent the message")
    message_type: Optional[str] = Field(None, description="AppMessage, SMS, MMS, etc.")
    platform: Optional[str] = Field(None, description="Mobile, Desktop, etc.")
    body: Optional[str] = Field(None, description="Message text content")
    message_timestamp_dt: Optional[str] = Field(None, description="Message time as ISO datetime string")
    from_party_identifier: Optional[str] = Field(None, description="Sender phone number or user ID")
    from_party_name: Optional[str] = Field(None, description="Sender name")
    to_party_identifier: Optional[str] = Field(None, description="Recipient phone number or user ID")
    to_party_name: Optional[str] = Field(None, description="Recipient name")
    has_attachments: Optional[bool] = Field(None, description="Whether message has attachments")
    attachment_count: Optional[int] = Field(None, description="Number of attachments")
    deleted_state: Optional[str] = Field(None, description="Intact, Deleted, etc.")
    decoding_confidence: Optional[str] = Field(None, description="High, Medium, Low")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "source_app": "WhatsApp",
                "message_type": "AppMessage",
                "body": "Hello, how are you?",
                "message_timestamp_dt": "2023-06-15T14:30:00",
                "from_party_name": "John",
                "to_party_name": "Jane"
            }
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "MessageRecord":
        """Create MessageRecord from database row."""
        return cls(
            source_app=row.get('source_app'),
            message_type=row.get('message_type'),
            platform=row.get('platform'),
            body=row.get('body'),
            message_timestamp_dt=row.get('message_timestamp_dt').isoformat() if row.get('message_timestamp_dt') else None,
            from_party_identifier=row.get('from_party_identifier'),
            from_party_name=row.get('from_party_name'),
            to_party_identifier=row.get('to_party_identifier'),
            to_party_name=row.get('to_party_name'),
            has_attachments=row.get('has_attachments'),
            attachment_count=row.get('attachment_count'),
            deleted_state=row.get('deleted_state'),
            decoding_confidence=row.get('decoding_confidence'),
        )


class ColumnValueCount(BaseModel):
    """Represents a column value with its count (for aggregate queries)."""

    value: str = Field(..., description="The unique value in the column")
    count: int = Field(..., description="Number of messages with this value")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "value": "WhatsApp",
                "count": 15234
            }
        }


class MessageFilterResult(BaseModel):
    """Result of a filtered message query."""

    query_type: QueryType = Field(QueryType.FILTER, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    total_count: int = Field(..., description="Total number of matching messages")
    returned_count: int = Field(..., description="Number of messages returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    filters_applied: List[str] = Field(..., description="List of filters that were applied")
    messages: List[MessageRecord] = Field(default_factory=list, description="List of message records")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "filter",
                "success": True,
                "total_count": 15234,
                "returned_count": 100,
                "query_description": "Get messages where source_app=WhatsApp",
                "filters_applied": ["source_app=WhatsApp"],
                "messages": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"💬 Message Query Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Filters: {', '.join(self.filters_applied)}\n"
        summary += f"Total matches: {self.total_count:,}\n"
        summary += f"Returned: {self.returned_count:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_count == 0:
            summary += "⚠️  No messages matched the query criteria.\n"
        else:
            summary += "Sample Messages:\n\n"
            for i, msg in enumerate(self.messages[:10], 1):
                summary += f"{i}. "

                # Message type
                summary += f"💬 {msg.message_type or 'Message'}\n"

                # Parties
                if msg.from_party_name or msg.from_party_identifier:
                    summary += f"   👤 From: {msg.from_party_name or msg.from_party_identifier}\n"
                if msg.to_party_name or msg.to_party_identifier:
                    summary += f"   👤 To: {msg.to_party_name or msg.to_party_identifier}\n"

                # Message body (truncated)
                if msg.body:
                    body_preview = msg.body[:100] + "..." if len(msg.body) > 100 else msg.body
                    summary += f"   📝 Message: {body_preview}\n"

                # Attachments
                if msg.has_attachments and msg.attachment_count:
                    summary += f"   📎 Attachments: {msg.attachment_count}\n"

                # Time
                if msg.message_timestamp_dt:
                    summary += f"   🕐 Time: {msg.message_timestamp_dt}\n"

                # Source app
                if msg.source_app:
                    summary += f"   📱 App: {msg.source_app}\n"

                # State
                if msg.deleted_state:
                    summary += f"   🗑️  State: {msg.deleted_state}\n"

                summary += "\n"

            if self.total_count > 10:
                summary += f"... and {self.total_count - 10:,} more messages.\n"

        return summary


class MessageAggregateResult(BaseModel):
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
                "total_unique_values": 8,
                "returned_count": 8,
                "query_description": "Get all unique values for column 'source_app'",
                "values": [
                    {"value": "WhatsApp", "count": 15234},
                    {"value": "Telegram", "count": 4521}
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
            total_messages = sum(v.count for v in self.values)

            for i, val in enumerate(self.values[:20], 1):
                percentage = (val.count / total_messages * 100) if total_messages > 0 else 0
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length

                summary += f"{i:2d}. {val.value:30s} │ {val.count:6,} ({percentage:5.1f}%) {bar}\n"

            if self.total_unique_values > 20:
                remaining = self.total_unique_values - 20
                remaining_count = sum(v.count for v in self.values[20:])
                summary += f"\n... and {remaining:,} more values ({remaining_count:,} messages).\n"

            summary += f"\n📈 Total messages analyzed: {total_messages:,}\n"

        return summary


# Union type for all result types
MessageQueryResult = Union[MessageFilterResult, MessageAggregateResult]


class MessageFilter(BaseModel):
    """Input model for message query filters."""

    col1: str = Field(
        ...,
        description="First column filter in format 'column:value'. Example: 'source_app:WhatsApp' or 'source_app:all'",
        json_schema_extra={"example": "source_app:WhatsApp"}
    )
    col2: Optional[str] = Field(
        None,
        description="Optional second column filter in format 'column:value'",
        json_schema_extra={"example": "message_type:AppMessage"}
    )
    col3: Optional[str] = Field(
        None,
        description="Optional third column filter in format 'column:value'",
        json_schema_extra={"example": "has_attachments:true"}
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return (1-1000)"
    )


async def query_messages(
    col1: str,
    col2: Optional[str] = None,
    col3: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query the messages table based on column filters.

    This tool retrieves messages data from the forensic database based on specified column filters.
    Each column filter should be in the format "column_name:value".

    Special handling:
    - If value is "all" (e.g., "source_app:all"), returns all unique values for that column
    - Multiple filters are combined with AND logic
    - Results are limited to prevent overwhelming responses

    Available Columns:
    - source_app: App that sent the message (WhatsApp, Telegram, Facebook Messenger, SMS, Instagram, etc.)
    - message_type: Type of message (AppMessage, SMS, MMS, etc.)
    - platform: Platform (Mobile, Desktop)
    - from_party_identifier: Sender phone number or user ID
    - to_party_identifier: Recipient phone number or user ID
    - has_attachments: Boolean (true/false)
    - deleted_state: Deletion state (Intact, Deleted)
    - decoding_confidence: Forensic confidence (High, Medium, Low)

    Args:
        col1: First column filter in format "column:value" (required).
              Example: "source_app:WhatsApp" or "has_attachments:true" or "source_app:all"
        col2: Second optional column filter in format "column:value"
              Example: "message_type:AppMessage"
        col3: Third optional column filter in format "column:value"
              Example: "deleted_state:Intact"
        limit: Maximum number of results to return (default: 100, max: 1000)

    Returns:
        A formatted string containing the query results with message details

    Examples:
        - query_messages("source_app:WhatsApp") - Get all WhatsApp messages
        - query_messages("has_attachments:true") - Get all messages with attachments
        - query_messages("source_app:all") - Get all unique apps with their message counts
        - query_messages("deleted_state:Deleted", "source_app:Telegram") - Get deleted Telegram messages
    """
    # Log tool invocation (both to logger and console)
    log_message = f"""
{'=' * 80}
🔧 MESSAGE TOOL CALLED
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
            result = MessageFilterResult(
                success=False,
                total_count=0,
                returned_count=0,
                query_description="No filters provided",
                filters_applied=[],
                messages=[],
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
                result = MessageFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid filter format: {filter_str}",
                    filters_applied=[],
                    messages=[],
                    error_message=f"Filter must be in format 'column:value', got '{filter_str}'"
                )
                return result.to_summary()

            column, value = filter_str.split(':', 1)
            column = column.strip()
            value = value.strip()

            # Validate column name (prevent SQL injection)
            valid_columns = {
                'source_app', 'message_type', 'platform',
                'from_party_identifier', 'to_party_identifier',
                'has_attachments', 'deleted_state', 'decoding_confidence'
            }

            if column not in valid_columns:
                result = MessageFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid column: {column}",
                    filters_applied=[],
                    messages=[],
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
                    FROM messages
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

                result = MessageAggregateResult(
                    success=True,
                    column_name=all_column,
                    total_unique_values=total_count,
                    returned_count=len(values),
                    query_description=query_description,
                    values=values
                )

                output = result.to_summary()
                success_msg = f"""
✅ MESSAGE TOOL - Aggregate Query Success
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
                query_description = "Get messages where " + " AND ".join(query_parts)

                # Count total matching records
                count_query = f"SELECT COUNT(*) FROM messages WHERE {where_clause}"
                total_count = await conn.fetchval(count_query, *filter_params)

                # Fetch message records
                query = f"""
                    SELECT
                        source_app, message_type, platform, body,
                        message_timestamp_dt,
                        from_party_identifier, from_party_name,
                        to_party_identifier, to_party_name,
                        has_attachments, attachment_count,
                        deleted_state, decoding_confidence
                    FROM messages
                    WHERE {where_clause}
                    ORDER BY message_timestamp_dt DESC
                    LIMIT ${param_idx}
                """
                filter_params.append(limit)

                rows = await conn.fetch(query, *filter_params)

                # Convert to MessageRecord objects
                messages = [MessageRecord.from_db_row(dict(row)) for row in rows]

                result = MessageFilterResult(
                    success=True,
                    total_count=total_count,
                    returned_count=len(messages),
                    query_description=query_description,
                    filters_applied=query_parts,
                    messages=messages
                )

                output = result.to_summary()
                success_msg = f"""
✅ MESSAGE TOOL - Filter Query Success
Total Matches: {total_count}, Returned: {len(messages)}
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
❌ MESSAGE TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = MessageFilterResult(
            success=False,
            total_count=0,
            returned_count=0,
            query_description="Query failed",
            filters_applied=[],
            messages=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
message_tool = function_tool(
    query_messages,
    name_override="query_messages",
    description_override="Query messages data from the forensic database based on column filters"
)
