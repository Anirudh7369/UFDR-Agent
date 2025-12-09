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

- **location_id**: Unique identifier for the location entry
- **source_app**: Application that recorded the location (WhatsApp, Telegram, Instagram, Google Maps, Facebook, etc.)
- **latitude**: Latitude coordinate (decimal degrees)
- **longitude**: Longitude coordinate (decimal degrees)
- **altitude**: Altitude in meters
- **location_type**: Type of location - "Shared", "Visited", or "Other Party Visited"
- **category**: Location category (Home, Work, Restaurant, Airport, Hotel, etc.)
- **city**: City name
- **state**: State or province name
- **country**: Country name
- **postal_code**: ZIP or postal code
- **location_timestamp**: Unix timestamp of when the location was recorded
- **location_timestamp_dt**: ISO datetime string of when the location was recorded
- **device_name**: Device that recorded the location
- **platform**: Operating system (Android, iOS, etc.)
- **confidence**: Location confidence (High, Medium, Low)
- **activity_type**: Activity type associated with the location (e.g., "Walking", "Driving")
- **activity_confidence**: Confidence level of the activity type
- **deleted_state**: Whether the location entry is deleted (Deleted, Active, Intact)
- **decoding_confidence**: Forensic confidence (High, Medium, Low)

## Synonyms Handling

The following terms can be treated as synonyms and will trigger the same response:

- **"location"** can also be referred to as **"entry"** or **"geolocation"**
- **"deleted_state"** can be referred to as **"status"** or **"state"**
- **"decoding_confidence"** can also be referred to as **"confidence level"** or **"decoding accuracy"**
- **"activity_type"** can also be referred to as **"activity"** or **"movement type"**
- **"latitude"** can be referred to as **"lat"** or **"geo_latitude"**
- **"longitude"** can be referred to as **"long"** or **"geo_longitude"**
- **"city"** can also be referred to as **"town"** or **"municipality"**
- **"postal_code"** can be referred to as **"zipcode"** or **"postal"**

## How to Fill Parameters Based on Query

### For WHERE queries (filter by specific values):
Use format: `column:value`

Examples:
- User: "Show all Google Maps locations" → `col1="source_app:Google Maps"`
- User: "Locations in Jaipur" → `col1="city:Jaipur"`
- User: "Shared locations from WhatsApp" → `col1="location_type:Shared", col2="source_app:WhatsApp"`
- User: "Instagram locations in Delhi, India" → `col1="source_app:Instagram", col2="city:Delhi", col3="country:India"`

### For getting ALL values from a column:
Use format: `column:all` - ONLY when user wants to see all unique values

Examples:
- User: "What apps have location data?" → `col1="source_app:all"`
- User: "Which cities are in the data?" → `col1="city:all"`
- User: "Show all location types" → `col1="location_type:all"`

**NOTE**: When using `:all`, ONLY use col1. Do NOT add col2 or col3.

## Common Mistakes to Avoid

❌ WRONG: `col1="source_app:Google Maps", col2="all", col3="all"`
✅ CORRECT: `col1="source_app:Google Maps"`

❌ WRONG: `col1="city:all", col2="source_app:WhatsApp"`
✅ CORRECT: Either `col1="city:all"` OR `col1="city:Jaipur", col2="source_app:WhatsApp"`

❌ WRONG: Using all 3 parameters when only 1 is needed
✅ CORRECT: Only use parameters that match the user's query

## Query Examples

1. "Show all Google Maps locations"
   → `query_locations(col1="source_app:Google Maps")`

2. "What cities have location data?"
   → `query_locations(col1="city:all")`

3. "Show all shared locations"
   → `query_locations(col1="location_type:Shared")`

4. "Locations in Mumbai from Instagram"
   → `query_locations(col1="city:Mumbai", col2="source_app:Instagram")`

5. "Show deleted locations"
   → `query_locations(col1="deleted_state:Deleted")`
"""
