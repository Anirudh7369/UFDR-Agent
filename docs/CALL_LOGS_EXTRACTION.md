# UFDR Call Logs Extraction - Complete Guide

## Overview

This module extracts **all call logs from multiple messaging and calling apps** from Cellebrite UFDR files into a unified PostgreSQL database. Instead of separate tables for each app, all calls are stored in a single `call_logs` table with a `source_app` column indicating which app made the call.

## Supported Apps

The system extracts call logs from:
- **Phone** (native dialer)
- **WhatsApp**
- **Telegram**
- **Skype**
- **Facebook Messenger**
- **Viber**
- **Line**
- **Instagram**
- **TextNow**
- **Wickr Pro**
- And any other app with Call models in the UFDR report

## Database Schema

### Tables

#### 1. `call_log_extractions`
Tracks extraction jobs and their status.

```sql
CREATE TABLE call_log_extractions (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL UNIQUE,
    ufdr_filename VARCHAR(500),
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    total_calls INTEGER DEFAULT 0,
    processed_calls INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. `call_logs` (Main Unified Table)
Stores all call logs from all apps.

```sql
CREATE TABLE call_logs (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- CRITICAL: App identification
    call_id VARCHAR(500),
    source_app VARCHAR(200), -- WhatsApp, Telegram, Phone, Skype, etc.

    -- Call details
    direction VARCHAR(50), -- Incoming, Outgoing
    call_type VARCHAR(50), -- Voice, Video
    status VARCHAR(100), -- Established, Missed, Rejected, Cancelled

    -- Timestamps (milliseconds since epoch)
    call_timestamp BIGINT,
    call_timestamp_dt TIMESTAMP, -- Converted for easy querying

    -- Duration
    duration_seconds INTEGER,
    duration_string VARCHAR(50), -- Original format: "00:01:17"

    -- Network/Account info
    country_code VARCHAR(10),
    network_code VARCHAR(50),
    network_name VARCHAR(200),
    account VARCHAR(500),

    -- Call properties
    is_video_call BOOLEAN DEFAULT FALSE,

    -- Main parties
    from_party_identifier VARCHAR(500), -- Phone number or user ID
    from_party_name VARCHAR(500),
    from_party_is_owner BOOLEAN DEFAULT FALSE,

    to_party_identifier VARCHAR(500),
    to_party_name VARCHAR(500),
    to_party_is_owner BOOLEAN DEFAULT FALSE,

    -- Metadata
    deleted_state VARCHAR(50), -- Intact, Deleted
    decoding_confidence VARCHAR(50), -- High, Medium, Low

    -- Forensic data
    raw_xml TEXT, -- Original XML
    raw_json JSONB, -- Complete parsed data

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (upload_id) REFERENCES call_log_extractions(upload_id) ON DELETE CASCADE
);
```

#### 3. `call_log_parties`
Stores all parties involved in each call (supports group/conference calls).

```sql
CREATE TABLE call_log_parties (
    id SERIAL PRIMARY KEY,
    call_log_id INTEGER NOT NULL,
    upload_id VARCHAR(255) NOT NULL,

    party_identifier VARCHAR(500), -- Phone number, user ID
    party_name VARCHAR(500),
    party_role VARCHAR(50), -- From, To
    is_phone_owner BOOLEAN DEFAULT FALSE,

    raw_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (call_log_id) REFERENCES call_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES call_log_extractions(upload_id) ON DELETE CASCADE
);
```

### Indexes

Performance-optimized indexes on frequently queried columns:

```sql
CREATE INDEX idx_call_logs_upload_id ON call_logs(upload_id);
CREATE INDEX idx_call_logs_source_app ON call_logs(source_app);
CREATE INDEX idx_call_logs_direction ON call_logs(direction);
CREATE INDEX idx_call_logs_status ON call_logs(status);
CREATE INDEX idx_call_logs_timestamp ON call_logs(call_timestamp);
CREATE INDEX idx_call_logs_timestamp_dt ON call_logs(call_timestamp_dt);
CREATE INDEX idx_call_logs_from_party ON call_logs(from_party_identifier);
CREATE INDEX idx_call_logs_to_party ON call_logs(to_party_identifier);
CREATE INDEX idx_call_logs_is_video ON call_logs(is_video_call);
```

### View

Convenient view joining extraction status:

```sql
CREATE OR REPLACE VIEW call_logs_view AS
SELECT
    c.id,
    c.upload_id,
    c.source_app,
    c.direction,
    c.call_type,
    c.status,
    c.call_timestamp_dt,
    c.duration_seconds,
    c.is_video_call,
    c.from_party_name,
    c.from_party_identifier,
    c.to_party_name,
    c.to_party_identifier,
    e.ufdr_filename,
    e.extraction_status
FROM call_logs c
LEFT JOIN call_log_extractions e ON c.upload_id = e.upload_id;
```

## Data Fields Extracted

### Core Identification
- **call_id**: Unique call identifier from UFDR
- **source_app**: App that made the call (WhatsApp, Telegram, Phone, etc.)

### Call Details
- **direction**: Incoming or Outgoing
- **call_type**: Voice, Video, or other type
- **status**: Established, Missed, Rejected, Cancelled, etc.

### Timestamps
- **call_timestamp**: Milliseconds since epoch
- **call_timestamp_dt**: PostgreSQL timestamp for easy querying

### Duration
- **duration_seconds**: Duration in seconds
- **duration_string**: Original duration format (e.g., "00:01:17")

### Network Information
- **country_code**: Country code
- **network_code**: Mobile network code
- **network_name**: Network provider name
- **account**: Account/SIM identifier

### Call Properties
- **is_video_call**: Boolean flag for video calls

### Parties
- **from_party_identifier**: Caller's phone number or user ID
- **from_party_name**: Caller's display name
- **from_party_is_owner**: Whether caller is device owner
- **to_party_identifier**: Recipient's phone number or user ID
- **to_party_name**: Recipient's display name
- **to_party_is_owner**: Whether recipient is device owner

### Metadata
- **deleted_state**: Intact or Deleted
- **decoding_confidence**: High, Medium, or Low

### Forensic Data
- **raw_xml**: Original XML from report.xml
- **raw_json**: Complete parsed JSON representation

## Usage

### Automatic Extraction (Production)

When a UFDR file is uploaded via the API, call logs are automatically extracted:

1. Upload UFDR file: `POST /api/uploads/init`
2. Complete upload: `PUT /api/uploads/{id}/complete`
3. Worker automatically:
   - Detects UFDR format
   - Extracts installed apps
   - **Extracts call logs from all apps**
4. Query data via SQL or Python API

### Manual Extraction (Testing/Development)

```bash
# Initialize schema first
psql $DATABASE_URL -f realtime/utils/db/call_logs_schema.sql

# Run extraction
python scripts/run_call_logs_extraction.py \
    "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" \
    test-calls-001
```

## Python API

```python
from realtime.utils.db import call_logs_operations

# Get statistics
stats = await call_logs_operations.get_call_log_statistics(upload_id)
print(f"Total calls: {stats['total_calls']}")
print(f"Video calls: {stats['video_calls']}")
print(f"Voice calls: {stats['voice_calls']}")

# Calls by app
for app_stat in stats['by_app']:
    print(f"{app_stat['source_app']}: {app_stat['count']} calls")

# Get calls from specific app
whatsapp_calls = await call_logs_operations.get_call_logs(
    upload_id,
    source_app='WhatsApp',
    limit=50
)

for call in whatsapp_calls:
    print(f"{call['direction']} {call['call_type']} - {call['status']}")
    print(f"Duration: {call['duration_seconds']}s")

# Get incoming video calls
video_calls = await call_logs_operations.get_call_logs(
    upload_id,
    direction='Incoming',
    is_video=True,
    limit=20
)

# Get missed calls
missed_calls = await call_logs_operations.get_call_logs(
    upload_id,
    status='Missed',
    limit=20
)
```

## SQL Query Examples

### Get all calls with timestamps

```sql
SELECT source_app, direction, call_type, status, call_timestamp_dt, duration_seconds
FROM call_logs
WHERE upload_id = 'your-upload-id'
ORDER BY call_timestamp_dt DESC;
```

### Calls by app

```sql
SELECT source_app, COUNT(*) as call_count
FROM call_logs
WHERE upload_id = 'your-upload-id'
GROUP BY source_app
ORDER BY call_count DESC;
```

### WhatsApp calls only

```sql
SELECT direction, call_type, status, call_timestamp_dt, duration_seconds,
       from_party_name, to_party_name
FROM call_logs
WHERE upload_id = 'your-upload-id'
  AND source_app = 'WhatsApp'
ORDER BY call_timestamp_dt DESC;
```

### Incoming video calls

```sql
SELECT source_app, call_timestamp_dt, from_party_name, duration_seconds
FROM call_logs
WHERE upload_id = 'your-upload-id'
  AND direction = 'Incoming'
  AND is_video_call = TRUE
ORDER BY call_timestamp_dt DESC;
```

### Missed calls

```sql
SELECT source_app, call_timestamp_dt, from_party_name
FROM call_logs
WHERE upload_id = 'your-upload-id'
  AND status = 'Missed'
ORDER BY call_timestamp_dt DESC;
```

### Call timeline

```sql
SELECT
    DATE(call_timestamp_dt) as call_date,
    COUNT(*) as calls_made,
    SUM(CASE WHEN is_video_call THEN 1 ELSE 0 END) as video_calls,
    SUM(duration_seconds) as total_duration_seconds
FROM call_logs
WHERE upload_id = 'your-upload-id'
  AND call_timestamp_dt IS NOT NULL
GROUP BY DATE(call_timestamp_dt)
ORDER BY call_date DESC;
```

### Calls with specific contact

```sql
SELECT source_app, direction, call_timestamp_dt, duration_seconds, status
FROM call_logs
WHERE upload_id = 'your-upload-id'
  AND (from_party_identifier LIKE '%1234567890%'
       OR to_party_identifier LIKE '%1234567890%')
ORDER BY call_timestamp_dt DESC;
```

### Most contacted people

```sql
SELECT
    COALESCE(from_party_name, from_party_identifier) as contact,
    COUNT(*) as call_count,
    SUM(duration_seconds) as total_duration
FROM call_logs
WHERE upload_id = 'your-upload-id'
  AND direction = 'Outgoing'
GROUP BY COALESCE(from_party_name, from_party_identifier)
ORDER BY call_count DESC
LIMIT 10;
```

### Cross-app communication

```sql
SELECT
    c1.source_app as app1,
    c2.source_app as app2,
    COUNT(*) as calls_between_apps
FROM call_logs c1
JOIN call_logs c2 ON c1.upload_id = c2.upload_id
    AND c1.from_party_identifier = c2.to_party_identifier
    AND c1.to_party_identifier = c2.from_party_identifier
    AND c1.source_app != c2.source_app
WHERE c1.upload_id = 'your-upload-id'
GROUP BY c1.source_app, c2.source_app
ORDER BY calls_between_apps DESC;
```

## Architecture

### Memory Efficiency
- Uses `iterparse` to process large XML files without loading entire file into memory
- XML elements cleared during parsing to minimize memory usage
- Streaming file download from MinIO

### Performance Optimization
- Batch inserts (20 calls per batch) for optimal database performance
- Comprehensive indexing on frequently queried columns
- Normalized parties table for efficient contact queries

### Deduplication
- Uses call_id for unique identification
- Handles duplicate entries in UFDR XML if present

### Error Handling
- Comprehensive try/catch at every level
- Failed extractions tracked in database with error messages
- Non-blocking integration (won't fail upload job)
- Automatic temp file cleanup even on errors

### Forensic Integrity
- Raw XML stored for every call
- Complete JSON representation preserved
- No data loss during extraction
- Timestamps preserved with millisecond precision

## Sample Data

From the Google Pixel 3 UFDR file, 56 calls were extracted:

### By App
- **Telegram**: 8 calls
- **Facebook Messenger**: 8 calls
- **Skype**: 5 calls
- **WhatsApp**: 4 calls
- **Viber**: 4 calls
- **Line**: 4 calls
- **Instagram**: 4 calls
- **TextNow**: 3 calls
- **Wickr Pro**: 2 calls

### Sample Calls
```
1. Telegram - Voice (Incoming)
   Status: Established
   Time: 2020-09-18T08:15:23
   Duration: 125s
   From: +1234567890

2. Skype - Video (Outgoing)
   Status: Established
   Time: 2020-09-17T14:30:45
   Duration: 1847s
   To: john.doe@example.com
```

## Files Created

1. [realtime/utils/db/call_logs_schema.sql](../realtime/utils/db/call_logs_schema.sql) - Database schema
2. [realtime/worker/ufdr_call_logs_extractor.py](../realtime/worker/ufdr_call_logs_extractor.py) - Extraction logic
3. [realtime/utils/db/call_logs_operations.py](../realtime/utils/db/call_logs_operations.py) - Database operations
4. [scripts/run_call_logs_extraction.py](../scripts/run_call_logs_extraction.py) - Testing script
5. [realtime/worker/ingest_worker.py](../realtime/worker/ingest_worker.py) - Updated with call logs trigger

## Testing

```bash
# Prerequisites
brew services start redis
psql $DATABASE_URL -f realtime/utils/db/call_logs_schema.sql

# Run extraction test
python scripts/run_call_logs_extraction.py \
    "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" \
    test-calls-001

# Verify data
psql $DATABASE_URL -c \
    "SELECT source_app, COUNT(*) FROM call_logs WHERE upload_id = 'test-calls-001' GROUP BY source_app;"
```

## Troubleshooting

### Issue: "relation 'call_logs' does not exist"
**Solution:** Initialize the schema:
```bash
psql $DATABASE_URL -f realtime/utils/db/call_logs_schema.sql
```

### Issue: "No calls extracted"
**Solution:** Check if UFDR file contains Call models:
```bash
unzip -p "file.ufdr" report.xml | grep -c '<model type="Call"'
```

### Issue: Worker crashes with "fork() was called"
**Solution:** Run worker with fork safety disabled:
```bash
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest --url redis://localhost:6379/0
```

## Future Enhancements

- Call duration analytics (average, total by app)
- Contact frequency analysis
- Call patterns and timing analysis
- Suspicious call detection (unusual hours, blocked numbers)
- Export to CSV/JSON formats
- Timeline visualization
- Voice vs video call ratio analysis
- Cross-reference with contact data from other apps
- Geolocation correlation (if location data available)

## Conclusion

The UFDR Call Logs extraction pipeline provides a **unified view of all call activity** across multiple messaging and calling apps. By storing all calls in a single table with a `source_app` discriminator, investigators can:

- Analyze communication patterns across apps
- Track contact frequency and duration
- Identify primary communication channels
- Detect anomalies in call behavior
- Build comprehensive contact timelines

The system seamlessly integrates with the existing UFDR processing pipeline, extracting call logs alongside installed apps data for complete device analysis.
