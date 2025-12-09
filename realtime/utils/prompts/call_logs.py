call_log_tool_prompt = """
# Call Log Query Tool - Usage Guide

## Tool Parameters

The tool has 4 parameters:
- **col1** (required): First filter in format "column:value"
- **col2** (optional): Second filter in format "column:value"
- **col3** (optional): Third filter in format "column:value"
- **limit** (optional): Maximum results to return (default: 100, max: 1000)

**IMPORTANT**: Only use the parameters you need! Don't fill all three just because they exist.

## Available Columns

- **source_app**: App that made the call (WhatsApp, Telegram, Phone, Skype, Viber, etc.)
- **direction**: Call direction (Incoming, Outgoing)
- **call_type**: Type of call (Voice, Video)
- **status**: Call status (Established, Missed, Rejected, Cancelled, etc.)
- **is_video_call**: Whether this is a video call (true, false)
- **from_party_identifier**: Caller phone number or user ID
- **to_party_identifier**: Recipient phone number or user ID
- **deleted_state**: Deletion state (Intact, Deleted)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show WhatsApp calls" → `col1="source_app:WhatsApp"`
- User: "Show missed calls" → `col1="status:Missed"`
- User: "Show incoming WhatsApp calls" → `col1="source_app:WhatsApp", col2="direction:Incoming"`
- User: "Show video calls from Telegram" → `col1="source_app:Telegram", col2="is_video_call:true"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when user wants to see all unique values

Examples:
- User: "What apps have call logs?" → `col1="source_app:all"`
- User: "Show all call statuses" → `col1="status:all"`
- User: "What directions are there?" → `col1="direction:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="source_app:WhatsApp", col2="all", col3="all"`
✅ CORRECT: `col1="source_app:WhatsApp"`

❌ WRONG: `col1="status:all", col2="direction:Incoming"`
✅ CORRECT: Either `col1="status:all"` OR `col1="status:Missed", col2="direction:Incoming"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Show all WhatsApp calls"
   → `query_call_logs(col1="source_app:WhatsApp")`

2. "What apps have call logs?"
   → `query_call_logs(col1="source_app:all")`

3. "Show all missed incoming calls"
   → `query_call_logs(col1="status:Missed", col2="direction:Incoming")`

4. "Show video calls"
   → `query_call_logs(col1="is_video_call:true")`

5. "Show deleted Telegram calls"
   → `query_call_logs(col1="source_app:Telegram", col2="deleted_state:Deleted")`
"""
