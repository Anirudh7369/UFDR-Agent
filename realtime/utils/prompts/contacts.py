contact_tool_prompt = """
# Contact Query Tool - Usage Guide

## Tool Parameters

The tool has 4 parameters:
- **col1** (required): First filter in format "column:value"
- **col2** (optional): Second filter in format "column:value"
- **col3** (optional): Third filter in format "column:value"
- **limit** (optional): Maximum results to return (default: 100, max: 1000)

**IMPORTANT**: Only use the parameters you need! Don't fill all three just because they exist.

## Available Columns

- **source_app**: Source app (WhatsApp, Facebook Messenger, Kik, Skype, Viber, Phone Book, etc.)
- **contact_type**: Contact type (PhoneBook, ChatParticipant, etc.)
- **contact_group**: Contact group name
- **deleted_state**: Deletion state (Intact, Deleted)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show WhatsApp contacts" → `col1="source_app:WhatsApp"`
- User: "Show phone book contacts" → `col1="contact_type:PhoneBook"`
- User: "Show WhatsApp chat participants" → `col1="source_app:WhatsApp", col2="contact_type:ChatParticipant"`
- User: "Show deleted contacts" → `col1="deleted_state:Deleted"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when user wants to see all unique values

Examples:
- User: "What apps have contacts?" → `col1="source_app:all"`
- User: "Show all contact types" → `col1="contact_type:all"`
- User: "What contact groups exist?" → `col1="contact_group:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="source_app:WhatsApp", col2="all", col3="all"`
✅ CORRECT: `col1="source_app:WhatsApp"`

❌ WRONG: `col1="source_app:all", col2="contact_type:PhoneBook"`
✅ CORRECT: Either `col1="source_app:all"` OR `col1="source_app:WhatsApp", col2="contact_type:PhoneBook"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Show all WhatsApp contacts"
   → `query_contacts(col1="source_app:WhatsApp")`

2. "What apps have contacts?"
   → `query_contacts(col1="source_app:all")`

3. "Show phone book contacts"
   → `query_contacts(col1="contact_type:PhoneBook")`

4. "Show deleted WhatsApp contacts"
   → `query_contacts(col1="source_app:WhatsApp", col2="deleted_state:Deleted")`

5. "Show all contact types"
   → `query_contacts(col1="contact_type:all")`
"""
