app_tool_prompt = """
# App Query Tool - Usage Guide

## Tool Parameters

The tool has 4 parameters:
- **col1** (required): First filter in format "column:value"
- **col2** (optional): Second filter in format "column:value"
- **col3** (optional): Third filter in format "column:value"
- **limit** (optional): Maximum results to return (default: 100, max: 1000)

**IMPORTANT**: Only use the parameters you need! Don't fill all three just because they exist.

## Available Columns

- **app_identifier**: Android package name (com.whatsapp, com.instagram.android, com.facebook.katana, etc.)
- **app_name**: User-visible app name (WhatsApp Messenger, Instagram, Facebook, etc.)
- **app_version**: Version string (2.23.10.75, 8.61.0.96, etc.)
- **app_guid**: App GUID if available
- **install_timestamp**: Timestamp when the app was installed (Unix format)
- **install_timestamp_dt**: Timestamp when the app was installed (ISO format)
- **last_launched_timestamp**: Timestamp of the last time the app was launched (Unix format)
- **last_launched_dt**: Timestamp of the last time the app was launched (ISO format)
- **decoding_status**: Decoding status (Decoded, NotDecoded, PartiallyDecoded, etc.)
- **is_emulatable**: Whether app is emulatable (true, false)
- **operation_mode**: App operation mode (Foreground, Background, etc.)
- **deleted_state**: Deletion state (Intact, Deleted, etc.)
- **decoding_confidence**: Forensic decoding confidence (High, Medium, Low)
- **permissions**: Permissions required by the app
- **categories**: Categories the app belongs to (e.g., "Social Media", "Productivity", etc.)
- **associated_directory_paths**: Directory paths associated with the app
- **raw_xml**: Raw XML data associated with the app
- **raw_json**: Raw JSON data associated with the app
- **created_at**: Timestamp when the app data was created (Unix format)
- **updated_at**: Timestamp when the app data was last updated (Unix format)

## Synonyms Handling

The following terms can be treated as synonyms and will trigger the same response:

- **"app"** can also be referred to as **"application"** or **"software"**
- **"app_name"** can be referred to as **"application_name"** or **"software_name"**
- **"app_version"** can also be referred to as **"version"** or **"version_string"**
- **"install_timestamp"** can be referred to as **"install_time"** or **"installation_time"**
- **"last_launched_timestamp"** can also be referred to as **"last_opened_time"** or **"last_used_timestamp"**
- **"decoding_status"** can be referred to as **"decoding_state"** or **"status"**
- **"is_emulatable"** can also be referred to as **"emulation_status"** or **"can_be_emulated"**
- **"operation_mode"** can be referred to as **"app_state"** or **"state_of_operation"**
- **"deleted_state"** can be referred to as **"status"** or **"state_of_deletion"**
- **"decoding_confidence"** can also be referred to as **"confidence_level"** or **"decoding_accuracy"**
- **"permissions"** can be referred to as **"app_permissions"** or **"access_rights"**
- **"categories"** can be referred to as **"app_categories"** or **"software_categories"**

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show WhatsApp apps" → `col1="app_name:WhatsApp Messenger"`
- User: "Show deleted apps" → `col1="deleted_state:Deleted"`
- User: "Show intact WhatsApp apps" → `col1="app_name:WhatsApp Messenger", col2="deleted_state:Intact"`
- User: "Show high confidence Instagram apps" → `col1="app_identifier:com.instagram.android", col2="decoding_confidence:High"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when user wants to see all unique values

Examples:
- User: "What apps are installed?" → `col1="app_name:all"`
- User: "List all package names" → `col1="app_identifier:all"`
- User: "Show all app versions" → `col1="app_version:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="app_name:WhatsApp", col2="all", col3="all"`
✅ CORRECT: `col1="app_name:WhatsApp"`

❌ WRONG: `col1="app_identifier:all", col2="deleted_state:Intact"`
✅ CORRECT: Either `col1="app_identifier:all"` OR `col1="app_identifier:com.whatsapp", col2="deleted_state:Intact"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Show all WhatsApp apps"
   → `query_apps(col1="app_name:WhatsApp Messenger")`

2. "What apps are installed?"
   → `query_apps(col1="app_name:all")`

3. "Show deleted apps"
   → `query_apps(col1="deleted_state:Deleted")`

4. "Show Instagram apps that are intact"
   → `query_apps(col1="app_identifier:com.instagram.android", col2="deleted_state:Intact")`

5. "Show all high confidence apps"
   → `query_apps(col1="decoding_confidence:High")`
"""
