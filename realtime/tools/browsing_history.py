"""
Browsing history tool for forensic agent to query browsing history data from the database.

This module provides a tool that allows the forensic agent to retrieve browsing history data
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


class BrowsingHistoryRecord(BaseModel):
    """Represents a single browsing history record from the database."""

    entry_type: Optional[str] = Field(None, description="visited_page, search, or bookmark")
    source_browser: Optional[str] = Field(None, description="Browser name")
    url: Optional[str] = Field(None, description="Full URL")
    title: Optional[str] = Field(None, description="Page title or bookmark title")
    search_query: Optional[str] = Field(None, description="Search query text")
    bookmark_path: Optional[str] = Field(None, description="Bookmark folder path")
    last_visited_dt: Optional[str] = Field(None, description="Last visit time as ISO datetime string")
    visit_count: Optional[int] = Field(None, description="Number of visits")
    deleted_state: Optional[str] = Field(None, description="Intact, Deleted, etc.")
    decoding_confidence: Optional[str] = Field(None, description="High, Medium, Low")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "entry_type": "visited_page",
                "source_browser": "Chrome",
                "url": "https://www.example.com",
                "title": "Example Domain",
                "last_visited_dt": "2023-06-15T14:30:00",
                "visit_count": 5
            }
        }

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "BrowsingHistoryRecord":
        """Create BrowsingHistoryRecord from database row."""
        return cls(
            entry_type=row.get('entry_type'),
            source_browser=row.get('source_browser'),
            url=row.get('url'),
            title=row.get('title'),
            search_query=row.get('search_query'),
            bookmark_path=row.get('bookmark_path'),
            last_visited_dt=row.get('last_visited_dt').isoformat() if row.get('last_visited_dt') else None,
            visit_count=row.get('visit_count'),
            deleted_state=row.get('deleted_state'),
            decoding_confidence=row.get('decoding_confidence'),
        )


class ColumnValueCount(BaseModel):
    """Represents a column value with its count (for aggregate queries)."""

    value: str = Field(..., description="The unique value in the column")
    count: int = Field(..., description="Number of browsing history entries with this value")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "value": "Chrome",
                "count": 8234
            }
        }


class BrowsingHistoryFilterResult(BaseModel):
    """Result of a filtered browsing history query."""

    query_type: QueryType = Field(QueryType.FILTER, description="Type of query executed")
    success: bool = Field(..., description="Whether the query succeeded")
    total_count: int = Field(..., description="Total number of matching entries")
    returned_count: int = Field(..., description="Number of entries returned (limited)")
    query_description: str = Field(..., description="Human-readable query description")
    filters_applied: List[str] = Field(..., description="List of filters that were applied")
    browsing_history: List[BrowsingHistoryRecord] = Field(default_factory=list, description="List of browsing history records")
    error_message: Optional[str] = Field(None, description="Error message if query failed")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "query_type": "filter",
                "success": True,
                "total_count": 8234,
                "returned_count": 100,
                "query_description": "Get browsing history where source_browser=Chrome",
                "filters_applied": ["source_browser=Chrome"],
                "browsing_history": []
            }
        }

    def to_summary(self) -> str:
        """Generate a human-readable summary for the agent."""
        if not self.success:
            return f"❌ Query failed: {self.error_message}"

        summary = f"🌐 Browsing History Query Results\n"
        summary += f"{'=' * 60}\n"
        summary += f"Query: {self.query_description}\n"
        summary += f"Filters: {', '.join(self.filters_applied)}\n"
        summary += f"Total matches: {self.total_count:,}\n"
        summary += f"Returned: {self.returned_count:,}\n"
        summary += f"{'=' * 60}\n\n"

        if self.total_count == 0:
            summary += "⚠️  No browsing history entries matched the query criteria.\n"
        else:
            summary += "Sample Browsing History:\n\n"
            for i, entry in enumerate(self.browsing_history[:10], 1):
                summary += f"{i}. "

                # Entry type icon
                if entry.entry_type == "search":
                    icon = "🔍"
                elif entry.entry_type == "bookmark":
                    icon = "⭐"
                else:
                    icon = "🌐"

                summary += f"{icon} {entry.entry_type or 'Entry'}\n"

                # Title or search query
                if entry.entry_type == "search" and entry.search_query:
                    summary += f"   🔍 Query: {entry.search_query}\n"
                elif entry.title:
                    title_preview = entry.title[:80] + "..." if len(entry.title) > 80 else entry.title
                    summary += f"   📄 Title: {title_preview}\n"

                # URL
                if entry.url:
                    url_preview = entry.url[:80] + "..." if len(entry.url) > 80 else entry.url
                    summary += f"   🔗 URL: {url_preview}\n"

                # Bookmark path
                if entry.bookmark_path:
                    summary += f"   📁 Path: {entry.bookmark_path}\n"

                # Visit info
                if entry.visit_count:
                    summary += f"   📊 Visits: {entry.visit_count}\n"

                # Time
                if entry.last_visited_dt:
                    summary += f"   🕐 Last Visit: {entry.last_visited_dt}\n"

                # Source browser
                if entry.source_browser:
                    summary += f"   🌐 Browser: {entry.source_browser}\n"

                # State
                if entry.deleted_state:
                    summary += f"   🗑️  State: {entry.deleted_state}\n"

                summary += "\n"

            if self.total_count > 10:
                summary += f"... and {self.total_count - 10:,} more entries.\n"

        return summary


class BrowsingHistoryAggregateResult(BaseModel):
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
                "column_name": "source_browser",
                "total_unique_values": 3,
                "returned_count": 3,
                "query_description": "Get all unique values for column 'source_browser'",
                "values": [
                    {"value": "Chrome", "count": 8234},
                    {"value": "Firefox", "count": 1523}
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
            total_entries = sum(v.count for v in self.values)

            for i, val in enumerate(self.values[:20], 1):
                percentage = (val.count / total_entries * 100) if total_entries > 0 else 0
                bar_length = int(percentage / 2)  # Scale to 50 chars max
                bar = "█" * bar_length

                summary += f"{i:2d}. {val.value:30s} │ {val.count:6,} ({percentage:5.1f}%) {bar}\n"

            if self.total_unique_values > 20:
                remaining = self.total_unique_values - 20
                remaining_count = sum(v.count for v in self.values[20:])
                summary += f"\n... and {remaining:,} more values ({remaining_count:,} entries).\n"

            summary += f"\n📈 Total browsing entries analyzed: {total_entries:,}\n"

        return summary


# Union type for all result types
BrowsingHistoryQueryResult = Union[BrowsingHistoryFilterResult, BrowsingHistoryAggregateResult]


class BrowsingHistoryFilter(BaseModel):
    """Input model for browsing history query filters."""

    col1: str = Field(
        ...,
        description="First column filter in format 'column:value'. Example: 'source_browser:Chrome' or 'source_browser:all'",
        json_schema_extra={"example": "source_browser:Chrome"}
    )
    col2: Optional[str] = Field(
        None,
        description="Optional second column filter in format 'column:value'",
        json_schema_extra={"example": "entry_type:visited_page"}
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


async def query_browsing_history(
    col1: str,
    col2: Optional[str] = None,
    col3: Optional[str] = None,
    limit: int = 100
) -> str:
    """
    Query the browsing_history table based on column filters.

    This tool retrieves browsing history data from the forensic database based on specified column filters.
    Each column filter should be in the format "column_name:value".

    Special handling:
    - If value is "all" (e.g., "source_browser:all"), returns all unique values for that column
    - Multiple filters are combined with AND logic
    - Results are limited to prevent overwhelming responses

    Available Columns:
    - entry_type: Type of entry (visited_page, search, bookmark)
    - source_browser: Browser name (Chrome, Firefox, Opera Mobile, Safari, etc.)
    - deleted_state: Deletion state (Intact, Deleted)
    - decoding_confidence: Forensic confidence (High, Medium, Low)

    Args:
        col1: First column filter in format "column:value" (required).
              Example: "source_browser:Chrome" or "entry_type:search" or "source_browser:all"
        col2: Second optional column filter in format "column:value"
              Example: "entry_type:visited_page"
        col3: Third optional column filter in format "column:value"
              Example: "deleted_state:Intact"
        limit: Maximum number of results to return (default: 100, max: 1000)

    Returns:
        A formatted string containing the query results with browsing history details

    Examples:
        - query_browsing_history("source_browser:Chrome") - Get all Chrome browsing history
        - query_browsing_history("entry_type:search") - Get all search history
        - query_browsing_history("source_browser:all") - Get all unique browsers with their entry counts
        - query_browsing_history("entry_type:bookmark") - Get all bookmarks
    """
    # Log tool invocation (both to logger and console)
    log_message = f"""
{'=' * 80}
🔧 BROWSING HISTORY TOOL CALLED
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
            result = BrowsingHistoryFilterResult(
                success=False,
                total_count=0,
                returned_count=0,
                query_description="No filters provided",
                filters_applied=[],
                browsing_history=[],
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
                result = BrowsingHistoryFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid filter format: {filter_str}",
                    filters_applied=[],
                    browsing_history=[],
                    error_message=f"Filter must be in format 'column:value', got '{filter_str}'"
                )
                return result.to_summary()

            column, value = filter_str.split(':', 1)
            column = column.strip()
            value = value.strip()

            # Validate column name (prevent SQL injection)
            valid_columns = {
                'entry_type', 'source_browser',
                'deleted_state', 'decoding_confidence'
            }

            if column not in valid_columns:
                result = BrowsingHistoryFilterResult(
                    success=False,
                    total_count=0,
                    returned_count=0,
                    query_description=f"Invalid column: {column}",
                    filters_applied=[],
                    browsing_history=[],
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
                    FROM browsing_history
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

                result = BrowsingHistoryAggregateResult(
                    success=True,
                    column_name=all_column,
                    total_unique_values=total_count,
                    returned_count=len(values),
                    query_description=query_description,
                    values=values
                )

                output = result.to_summary()
                success_msg = f"""
✅ BROWSING HISTORY TOOL - Aggregate Query Success
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
                query_description = "Get browsing history where " + " AND ".join(query_parts)

                # Count total matching records
                count_query = f"SELECT COUNT(*) FROM browsing_history WHERE {where_clause}"
                total_count = await conn.fetchval(count_query, *filter_params)

                # Fetch browsing history records
                query = f"""
                    SELECT
                        entry_type, source_browser, url, title,
                        search_query, bookmark_path,
                        last_visited_dt, visit_count,
                        deleted_state, decoding_confidence
                    FROM browsing_history
                    WHERE {where_clause}
                    ORDER BY last_visited_dt DESC
                    LIMIT ${param_idx}
                """
                filter_params.append(limit)

                rows = await conn.fetch(query, *filter_params)

                # Convert to BrowsingHistoryRecord objects
                browsing_history = [BrowsingHistoryRecord.from_db_row(dict(row)) for row in rows]

                result = BrowsingHistoryFilterResult(
                    success=True,
                    total_count=total_count,
                    returned_count=len(browsing_history),
                    query_description=query_description,
                    filters_applied=query_parts,
                    browsing_history=browsing_history
                )

                output = result.to_summary()
                success_msg = f"""
✅ BROWSING HISTORY TOOL - Filter Query Success
Total Matches: {total_count}, Returned: {len(browsing_history)}
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
❌ BROWSING HISTORY TOOL - Error occurred
Error: {str(e)}
{'=' * 80}
"""
        print(error_msg)
        logger.error(error_msg)
        logger.error(f"Full traceback:", exc_info=True)

        result = BrowsingHistoryFilterResult(
            success=False,
            total_count=0,
            returned_count=0,
            query_description="Query failed",
            filters_applied=[],
            browsing_history=[],
            error_message=str(e)
        )
        output = result.to_summary()
        print(f"Error output:\n{output}")
        print("=" * 80)
        return output


# Create the tool for the agent
browsing_history_tool = function_tool(
    query_browsing_history,
    name_override="query_browsing_history",
    description_override="Query browsing history data from the forensic database based on column filters"
)
