message_tool_prompt = """
# Message Query Tool - Usage Guide

## Tool Parameters

The tool has 4 parameters:
- **col1** (required): First filter in format "column:value"
- **col2** (optional): Second filter in format "column:value"
- **col3** (optional): Third filter in format "column:value"
- **limit** (optional): Maximum results to return (default: 100, max: 1000)

**IMPORTANT**: Only use the parameters you need! Don't fill all three just because they exist.

## Available Columns

- **source_app**: App that sent the message (WhatsApp, Telegram, Facebook Messenger, SMS, Instagram, Twitter, etc.)
- **message_type**: Type of message (AppMessage, SMS, MMS, etc.)
- **platform**: Platform (Mobile, Desktop)
- **from_party_identifier**: Sender phone number or user ID
- **to_party_identifier**: Recipient phone number or user ID
- **has_attachments**: Whether message has attachments (true, false)
- **deleted_state**: Deletion state (Intact, Deleted)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show WhatsApp messages" → `col1="source_app:WhatsApp"`
- User: "Show messages with attachments" → `col1="has_attachments:true"`
- User: "Show deleted WhatsApp messages" → `col1="source_app:WhatsApp", col2="deleted_state:Deleted"`
- User: "Show Instagram messages with attachments" → `col1="source_app:Instagram", col2="has_attachments:true"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when user wants to see all unique values

Examples:
- User: "What apps have messages?" → `col1="source_app:all"`
- User: "Show all message types" → `col1="message_type:all"`
- User: "What platforms are there?" → `col1="platform:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="source_app:WhatsApp", col2="all", col3="all"`
✅ CORRECT: `col1="source_app:WhatsApp"`

❌ WRONG: `col1="source_app:all", col2="has_attachments:true"`
✅ CORRECT: Either `col1="source_app:all"` OR `col1="source_app:WhatsApp", col2="has_attachments:true"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Show all WhatsApp messages"
   → `query_messages(col1="source_app:WhatsApp")`

2. "What apps have messages?"
   → `query_messages(col1="source_app:all")`

3. "Show messages with attachments"
   → `query_messages(col1="has_attachments:true")`

4. "Show deleted Telegram messages"
   → `query_messages(col1="source_app:Telegram", col2="deleted_state:Deleted")`

5. "Show SMS messages"
   → `query_messages(col1="message_type:SMS")`
"""
