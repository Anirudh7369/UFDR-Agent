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

- **entry_type**: Type of entry (visited_page, search, bookmark)
- **source_browser**: Browser name (Chrome, Firefox, Opera Mobile, Safari, etc.)
- **deleted_state**: Deletion state (Intact, Deleted)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)

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
- User: "What browsers are there?" → `col1="source_browser:all"`
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

---

### Agent Behavior:

- **Always respond with minimal, relevant information.**
- **Ask clarifying questions** only if necessary. For example: 
  - "Would you like to see the details of a specific search or page visit?" 
  - "Do you want the results limited to a specific time range?"
- **Provide concise answers** and avoid trivial details unless the user explicitly asks for them.
"""
