browsing_history_tool_prompt = """
# Browsing History Query Tool - Usage Guide

## Tool Parameters

The tool has 4 parameters:
- **col1** (required): First filter in format "column:value"
- **col2** (optional): Second filter in format "column:value"
- **col3** (optional): Third filter in format "column:value"
- **limit** (optional): Maximum results to return (default: 100, max: 1000)

**IMPORTANT**: Only use the parameters you need! Don't fill all three just because they exist.

## Available Columns

- **entry_id**: Unique identifier for the entry
- **entry_type**: Type of entry (visited_page, search, bookmark)
- **source_browser**: Browser name (Chrome, Firefox, Opera Mobile, Safari, etc.)
- **url**: URL of the visited page
- **title**: Title of the page visited
- **search_query**: Search query associated with the entry
- **bookmark_path**: Path of the bookmark, if available
- **last_visited**: Last visit timestamp (Unix format)
- **last_visited_dt**: Last visit timestamp (ISO format)
- **visit_count**: Number of times the URL was visited
- **url_cache_file**: File holding the cached URL data
- **deleted_state**: Deletion state (Intact, Deleted)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)
- **raw_xml**: Raw XML data associated with the entry
- **raw_json**: Raw JSON data associated with the entry
- **created_at**: Timestamp when the browsing history entry was created (Unix format)
- **updated_at**: Timestamp when the browsing history entry was last updated (Unix format)

## Synonyms Handling

The following terms can be treated as synonyms and will trigger the same response:

- **"entry"** can also be referred to as **"history_entry"**, **"log"**, or **"visit"**
- **"source_browser"** can also be referred to as **"browser"**, **"web_browser"**, or **"app"**
- **"entry_type"** can also be referred to as **"type_of_entry"**, **"visit_type"**, or **"log_type"**
- **"url"** can also be referred to as **"web_address"** or **"link"**
- **"deleted_state"** can also be referred to as **"status"** or **"state_of_deletion"**
- **"decoding_confidence"** can also be referred to as **"confidence_level"**, **"decoding_accuracy"**, or **"forensic_confidence"**
- **"visit_count"** can be referred to as **"number_of_visits"** or **"frequency_of_visit"**
- **"search_query"** can also be referred to as **"query"** or **"search_term"**
- **"last_visited"** can be referred to as **"last_visit_timestamp"** or **"last_visited_time"**

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show Chrome browsing history" → `col1="source_browser:Chrome"`
- User: "Show search history" → `col1="entry_type:search"`
- User: "Show Firefox bookmarks" → `col1="entry_type:bookmark", col2="source_browser:Firefox"`
- User: "Show deleted browsing history" → `col1="deleted_state:Deleted"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when user wants to see all unique values

Examples:
- User: "What browsers have history?" → `col1="source_browser:all"`
- User: "Show all entry types" → `col1="entry_type:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="source_browser:Chrome", col2="all", col3="all"`
✅ CORRECT: `col1="source_browser:Chrome"`

❌ WRONG: `col1="entry_type:all", col2="source_browser:Chrome"`
✅ CORRECT: Either `col1="entry_type:all"` OR `col1="entry_type:visited_page", col2="source_browser:Chrome"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Show all Chrome browsing history"
   → `query_browsing_history(col1="source_browser:Chrome")`

2. "What browsers have history?"
   → `query_browsing_history(col1="source_browser:all")`

3. "Show all search history"
   → `query_browsing_history(col1="entry_type:search")`

4. "Show all bookmarks"
   → `query_browsing_history(col1="entry_type:bookmark")`

5. "Show deleted Firefox history"
   → `query_browsing_history(col1="source_browser:Firefox", col2="deleted_state:Deleted")`
"""
