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

- **contact_id**: Unique identifier for the contact
- **source_app**: Source app (WhatsApp, Facebook Messenger, Kik, Skype, Viber, Phone Book, etc.)
- **service_identifier**: Identifier for the service (e.g., phone number, user ID)
- **name**: Name of the contact
- **account**: Account associated with the contact
- **contact_type**: Contact type (PhoneBook, ChatParticipant, etc.)
- **contact_group**: Contact group name
- **time_created**: Timestamp when the contact was created (Unix format)
- **time_created_dt**: Timestamp when the contact was created (ISO format)
- **notes**: Notes associated with the contact
- **interaction_statuses**: Statuses of interactions with the contact (e.g., "active", "inactive")
- **user_tags**: Tags associated with the contact (e.g., "family", "work")
- **deleted_state**: Deletion state (Intact, Deleted)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)
- **raw_xml**: Raw XML data associated with the contact
- **raw_json**: Raw JSON data associated with the contact
- **created_at**: Timestamp when the contact data was created (Unix format)
- **updated_at**: Timestamp when the contact data was last updated (Unix format)

## Synonyms Handling

The following terms can be treated as synonyms and will trigger the same response:

- **"contact"** can also be referred to as **"entry"**, **"person"**, or **"user"**
- **"source_app"** can also be referred to as **"app"**, **"application"**, or **"service"**
- **"contact_type"** can also be referred to as **"type_of_contact"**, **"entry_type"**, or **"contact_category"**
- **"contact_group"** can also be referred to as **"group"** or **"category"**
- **"deleted_state"** can be referred to as **"status"** or **"state_of_deletion"**
- **"decoding_confidence"** can also be referred to as **"confidence_level"**, **"decoding_accuracy"**, or **"forensic_confidence"**
- **"interaction_statuses"** can also be referred to as **"status_of_interaction"** or **"interaction_state"**
- **"service_identifier"** can be referred to as **"service_id"**, **"identifier"**, or **"account_identifier"**

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
---

### Agent Behavior:

- **Provide clear, concise answers**. Focus on delivering the essential information.
"""
