"""
Contacts tool for forensic agent to query contacts data from the database.

This module provides a tool that allows the forensic agent to retrieve contacts data
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


class ContactRecord(BaseModel):
    """Represents a single contact record from the database."""

    name: Optional[str] = Field(None, description="Contact name")
    source_app: Optional[str] = Field(None, description="Source app")
    contact_type: Optional[str] = Field(None, description="Contact type")
    account: Optional[str] = Field(None, description="Associated account")
    contact_group: Optional[str] = Field(None, description="Contact group")
    time_created_dt: Optional[str] = Field(None, description="Creation time as ISO datetime string")
    deleted_state: Optional[str] = Field(None, description="Intact, Deleted, etc.")
    decoding_confidence: Optional[str] = Field(None, description="High, Medium, Low")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "source_app": "WhatsApp",
                "contact_type": "ChatParticipant",
                "time_created_dt": "2023-06-15T14:30:00"
            }
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "ContactRecord":
        """Create ContactRecord from database row."""
        return cls(
            name=row.get('name'),
            source_app=row.get('source_app'),
            contact_type=row.get('contact_type'),
            account=row.get('account'),
            contact_group=row.get('contact_group'),
            time_created_dt=row.get('time_created_dt').isoformat() if row.get('time_created_dt') else None,
            deleted_state=row.get('deleted_state'),
            decoding_confidence=row.get('decoding_confidence'),
        )


class ColumnValueCount(BaseModel):
    """Represents a column value with its count (for aggregate queries)."""

    value: str = Field(..., description="The unique value in the column")
    count: int = Field(..., description="Number of contacts with this value")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "value": "WhatsApp",
                "count": 342
            }
        }


class ContactFilterResult(BaseModel):
    """Result of a filtered contact query."""

    query_type: QueryType = Field(QueryType.FILTER, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    total_count: int = Field(..., description="Total number of matching contacts")
    returned_count: int = Field(..., description="Number of contacts returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    filters_applied: List[str] = Field(..., description="List of filters that were applied")
    contacts: List[ContactRecord] = Field(default_factory=list, description="List of contact records")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "filter",
                "success": True,
                "total_count": 342,
                "returned_count": 100,
                "query_description": "Get contacts where source_app=WhatsApp",
                "filters_applied": ["source_app=WhatsApp"],
                "contacts": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"👥 Contact Query Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Filters: {', '.join(self.filters_applied)}\n"
        summary += f"Total matches: {self.total_count:,}\n"
        summary += f"Returned: {self.returned_count:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_count == 0:
            summary += "⚠️  No contacts matched the query criteria.\n"
        else:
            summary += "Sample Contacts:\n\n"
            for i, contact in enumerate(self.contacts[:10], 1):
                summary += f"{i}. "

                # Contact name
                if contact.name:
                    summary += f"👤 {contact.name}\n"
                else:
                    summary += f"👤 Unknown Contact\n"

                # Source app
                if contact.source_app:
                    summary += f"   📱 Source: {contact.source_app}\n"

                # Contact type
                if contact.contact_type:
                    summary += f"   🏷️  Type: {contact.contact_type}\n"

                # Account
                if contact.account:
                    summary += f"   📧 Account: {contact.account}\n"

                # Group
                if contact.contact_group:
                    summary += f"   👥 Group: {contact.contact_group}\n"

                # Time
                if contact.time_created_dt:
                    summary += f"   🕐 Created: {contact.time_created_dt}\n"

                # State
                if contact.deleted_state:
                    summary += f"   🗑️  State: {contact.deleted_state}\n"

                summary += "\n"

            if self.total_count > 10:
                summary += f"... and {self.total_count - 10:,} more contacts.\n"

        return summary


class ContactAggregateResult(BaseModel):
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
                    {"value": "WhatsApp", "count": 342},
                    {"value": "Phone Book", "count": 215}
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
            total_contacts = sum(v.count for v in self.values)

            for i, val in enumerate(self.values[:20], 1):
                percentage = (val.count / total_contacts * 100) if total_contacts > 0 else 0
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length

                summary += f"{i:2d}. {val.value:30s} │ {val.count:6,} ({percentage:5.1f}%) {bar}\n"

            if self.total_unique_values > 20:
                remaining = self.total_unique_values - 20
                remaining_count = sum(v.count for v in self.values[20:])
                summary += f"\n... and {remaining:,} more values ({remaining_count:,} contacts).\n"

            summary += f"\n📈 Total contacts analyzed: {total_contacts:,}\n"

        return summary


# Union type for all result types
ContactQueryResult = Union[ContactFilterResult, ContactAggregateResult]


class ContactFilter(BaseModel):
    """Input model for contact query filters."""

    col1: str = Field(
        ...,
        description="First column filter in format 'column:value'. Example: 'source_app:WhatsApp' or 'source_app:all'",
        json_schema_extra={"example": "source_app:WhatsApp"}
    )
    col2: Optional[str] = Field(
        None,
        description="Optional second column filter in format 'column:value'",
        json_schema_extra={"example": "contact_type:ChatParticipant"}
    )
    col3: Optional[str] = Field(
        None,
        description="Optional third column filter in format 'column:value'",
        json_schema_extra={"example": "deleted_state:Intact"}
    )
    limit: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return (1-1000)"
    )


async def query_contacts(
    col1: str,
    col2: Optional[str] = None,
    col3: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query the contacts table based on column filters.

    This tool retrieves contacts data from the forensic database based on specified column filters.
    Each column filter should be in the format "column_name:value".

    Special handling:
    - If value is "all" (e.g., "source_app:all"), returns all unique values for that column
    - Multiple filters are combined with AND logic
    - Results are limited to prevent overwhelming responses

    Available Columns:
    - source_app: Source app (WhatsApp, Facebook Messenger, Kik, Skype, Viber, Phone Book, etc.)
    - contact_type: Contact type (PhoneBook, ChatParticipant, etc.)
    - contact_group: Contact group name
    - deleted_state: Deletion state (Intact, Deleted)
    - decoding_confidence: Forensic confidence (High, Medium, Low)

    Args:
        col1: First column filter in format "column:value" (required).
              Example: "source_app:WhatsApp" or "contact_type:PhoneBook" or "source_app:all"
        col2: Second optional column filter in format "column:value"
              Example: "contact_type:ChatParticipant"
        col3: Third optional column filter in format "column:value"
              Example: "deleted_state:Intact"
        limit: Maximum number of results to return (default: 100, max: 1000)

    Returns:
        A formatted string containing the query results with contact details

    Examples:
        - query_contacts("source_app:WhatsApp") - Get all WhatsApp contacts
        - query_contacts("contact_type:PhoneBook") - Get all phone book contacts
        - query_contacts("source_app:all") - Get all unique source apps with their contact counts
        - query_contacts("deleted_state:Deleted") - Get all deleted contacts
    """
    # Log tool invocation (both to logger and console)
    log_message = f"""
{'=' * 80}
🔧 CONTACT TOOL CALLED
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
            result = ContactFilterResult(
                success=False,
                total_count=0,
                returned_count=0,
                query_description="No filters provided",
                filters_applied=[],
                contacts=[],
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
                result = ContactFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid filter format: {filter_str}",
                    filters_applied=[],
                    contacts=[],
                    error_message=f"Filter must be in format 'column:value', got '{filter_str}'"
                )
                return result.to_summary()

            column, value = filter_str.split(':', 1)
            column = column.strip()
            value = value.strip()

            # Validate column name (prevent SQL injection)
            valid_columns = {
                'source_app', 'contact_type', 'contact_group',
                'deleted_state', 'decoding_confidence'
            }

            if column not in valid_columns:
                result = ContactFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid column: {column}",
                    filters_applied=[],
                    contacts=[],
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
                    FROM contacts
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

                result = ContactAggregateResult(
                    success=True,
                    column_name=all_column,
                    total_unique_values=total_count,
                    returned_count=len(values),
                    query_description=query_description,
                    values=values
                )

                output = result.to_summary()
                success_msg = f"""
✅ CONTACT TOOL - Aggregate Query Success
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
                query_description = "Get contacts where " + " AND ".join(query_parts)

                # Count total matching records
                count_query = f"SELECT COUNT(*) FROM contacts WHERE {where_clause}"
                total_count = await conn.fetchval(count_query, *filter_params)

                # Fetch contact records
                query = f"""
                    SELECT
                        name, source_app, contact_type, account,
                        contact_group, time_created_dt,
                        deleted_state, decoding_confidence
                    FROM contacts
                    WHERE {where_clause}
                    ORDER BY time_created_dt DESC
                    LIMIT ${param_idx}
                """
                filter_params.append(limit)

                rows = await conn.fetch(query, *filter_params)

                # Convert to ContactRecord objects
                contacts = [ContactRecord.from_db_row(dict(row)) for row in rows]

                result = ContactFilterResult(
                    success=True,
                    total_count=total_count,
                    returned_count=len(contacts),
                    query_description=query_description,
                    filters_applied=query_parts,
                    contacts=contacts
                )

                output = result.to_summary()
                success_msg = f"""
✅ CONTACT TOOL - Filter Query Success
Total Matches: {total_count}, Returned: {len(contacts)}
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
❌ CONTACT TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = ContactFilterResult(
            success=False,
            total_count=0,
            returned_count=0,
            query_description="Query failed",
            filters_applied=[],
            contacts=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
contact_tool = function_tool(
    query_contacts,
    name_override="query_contacts",
    description_override="Query contacts data from the forensic database based on column filters"
)
