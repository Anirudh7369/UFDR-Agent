location_tool_prompt = """
# Location Query Tool - Usage Guide

## Tool Parameters

The tool has 4 parameters:
- **col1** (required): First filter in format "column:value"
- **col2** (optional): Second filter in format "column:value"
- **col3** (optional): Third filter in format "column:value"
- **limit** (optional): Maximum results to return (default: 100, max: 1000)

**IMPORTANT**: Only use the parameters you need! Don't fill all three just because they exist.

## Available Columns

- **source_app**: Application that recorded the location (WhatsApp, Telegram, Instagram, Google Maps, Facebook, etc.)
- **location_type**: Type of location - "Shared", "Visited", or "Other Party Visited"
- **city**: City name
- **state**: State or province name
- **country**: Country name
- **address**: Full street address
- **category**: Location category (Home, Work, Restaurant, Airport, Hotel, etc.)
- **latitude**: Latitude coordinate (decimal degrees)
- **longitude**: Longitude coordinate (decimal degrees)
- **altitude**: Altitude in meters
- **accuracy**: Location accuracy in meters
- **postal_code**: ZIP or postal code
- **location_timestamp**: Unix timestamp
- **location_timestamp_dt**: ISO datetime string
- **device_name**: Device that recorded the location
- **platform**: Operating system (Android, iOS, etc.)
- **deleted_state**: Whether deleted (Deleted, Active, Intact)
- **decoding_confidence**: Forensic confidence (High, Medium, Low)

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show Telegram locations" → `col1="source_app:Telegram"`
- User: "Locations in Jaipur" → `col1="city:Jaipur"`
- User: "Shared locations from WhatsApp" → `col1="location_type:Shared", col2="source_app:WhatsApp"`
- User: "Instagram locations in Delhi, India" → `col1="source_app:Instagram", col2="city:Delhi", col3="country:India"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when the user wants to see all unique values

Examples:
- User: "What apps have location data?" → `col1="source_app:all"`
- User: "Which cities are in the data?" → `col1="city:all"`
- User: "Show all location types" → `col1="location_type:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="source_app:Telegram", col2="all", col3="all"`
✅ CORRECT: `col1="source_app:Telegram"`

❌ WRONG: `col1="city:all", col2="source_app:WhatsApp"`
✅ CORRECT: Either `col1="city:all"` OR `col1="city:SomeCity", col2="source_app:WhatsApp"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Give me data where location is shared on Telegram"
   → `query_locations(col1="location_type:Shared", col2="source_app:Telegram")`

2. "Show all WhatsApp locations"
   → `query_locations(col1="source_app:WhatsApp")`

3. "What cities have location data?"
   → `query_locations(col1="city:all")`

4. "Locations in Mumbai from Instagram"
   → `query_locations(col1="city:Mumbai", col2="source_app:Instagram")`

5. "Show deleted locations"
   → `query_locations(col1="deleted_state:Deleted")`

---

### Agent Behavior:

- **Always respond with minimal, relevant information.**
- **Ask clarifying questions** only if necessary. For example:
  - "Would you like to narrow the results by location category or type?"
  - "Would you like to explore the location of a specific device?"
- **Avoid unnecessary details** unless explicitly requested by the user.

"""
