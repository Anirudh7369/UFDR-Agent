# WhatsApp Data Extraction from UFDR Files

## Overview

This document describes the WhatsApp data extraction pipeline that processes Cellebrite UFDR files and extracts WhatsApp chat data into PostgreSQL for forensic analysis.

## Architecture

The extraction pipeline consists of the following components:

1. **Database Schema** ([realtime/utils/db/whatsapp_schema.sql](../realtime/utils/db/whatsapp_schema.sql))
   - PostgreSQL tables for WhatsApp messages, chats, contacts, and metadata
   - Optimized indexes for fast querying
   - View for easy data access

2. **Database Operations** ([realtime/utils/db/whatsapp_operations.py](../realtime/utils/db/whatsapp_operations.py))
   - Async database operations using asyncpg
   - Bulk insert capabilities
   - Status tracking for extraction jobs

3. **UFDR Extractor** ([realtime/worker/ufdr_whatsapp_extractor.py](../realtime/worker/ufdr_whatsapp_extractor.py))
   - Extracts WhatsApp SQLite databases from UFDR files
   - Parses multiple WhatsApp database schemas
   - Handles message deduplication

4. **Integration with Upload Workflow** ([realtime/worker/ingest_worker.py](../realtime/worker/ingest_worker.py))
   - Automatically detects UFDR files
   - Triggers WhatsApp extraction after upload completes

## Database Schema

### Main Tables

#### `whatsapp_messages`
Stores all WhatsApp messages with complete metadata:
- Message ID, chat JID, sender information
- Message text and type
- Timestamps (milliseconds since epoch + datetime)
- Media information (URL, path, MIME type, size)
- Location data (latitude/longitude)
- Raw JSON for complete forensic data

#### `whatsapp_chats`
Stores chat/conversation metadata:
- Chat JID (Jabber ID)
- Subject/name
- Archive status
- Timestamp information
- Message counts

#### `whatsapp_jids`
Lookup table for WhatsApp identifiers (phone numbers, group IDs):
- Raw JID string
- User and server parts
- JID type

#### `whatsapp_contacts`
Contact information:
- JID
- Display name
- Phone number
- Business account flag

#### `whatsapp_call_logs`
Stores WhatsApp call history:
- Call ID
- Participant JIDs (from/to)
- Call type (voice/video)
- Direction (from_me flag)
- Timestamp and duration
- Call status (completed, missed, rejected, cancelled)
- Bytes transferred
- Group call indicator
- Raw JSON for complete data

#### `ufdr_extractions`
Tracks extraction jobs:
- Upload ID
- Status (pending, processing, completed, failed)
- Progress counters
- Error messages

### View

#### `whatsapp_messages_view`
Convenient view joining messages with chats and contacts for easy querying.

## Usage

### Manual Extraction

To manually extract WhatsApp data from a UFDR file:

```bash
python scripts/run_whatsapp_extraction.py <ufdr_file_path> <upload_id>
```

Example:
```bash
python scripts/run_whatsapp_extraction.py \
    realtime/uploads/ufdr_files/report.ufdr \
    investigation-2024-001
```

### Automatic Extraction

When files are uploaded through the API:

1. Upload is initiated via `/api/uploads/init`
2. File is uploaded to MinIO/S3 in parts
3. Upload is completed via `/api/uploads/{upload_id}/complete`
4. Ingest worker processes the file
5. If UFDR format is detected, WhatsApp extraction runs automatically
6. Data is inserted into PostgreSQL

Progress can be monitored via `/api/uploads/{upload_id}/ingest-progress`

## Querying the Data

### Get all messages for an upload

```sql
SELECT * FROM whatsapp_messages_view
WHERE upload_id = 'your-upload-id'
ORDER BY timestamp DESC
LIMIT 100;
```

### Get messages from a specific chat

```sql
SELECT * FROM whatsapp_messages_view
WHERE upload_id = 'your-upload-id'
  AND chat_jid = '1234567890@s.whatsapp.net'
ORDER BY timestamp ASC;
```

### Get message statistics

```sql
SELECT
    chat_jid,
    COUNT(*) as message_count,
    SUM(CASE WHEN from_me = 1 THEN 1 ELSE 0 END) as sent_messages,
    SUM(CASE WHEN from_me = 0 THEN 1 ELSE 0 END) as received_messages,
    MIN(timestamp_dt) as first_message,
    MAX(timestamp_dt) as last_message
FROM whatsapp_messages
WHERE upload_id = 'your-upload-id'
GROUP BY chat_jid;
```

### Get messages with media

```sql
SELECT * FROM whatsapp_messages_view
WHERE upload_id = 'your-upload-id'
  AND media_mimetype IS NOT NULL
ORDER BY timestamp DESC;
```

### Search for keywords in messages

```sql
SELECT * FROM whatsapp_messages_view
WHERE upload_id = 'your-upload-id'
  AND message_text ILIKE '%keyword%'
ORDER BY timestamp DESC;
```

### Get call logs

```sql
SELECT * FROM whatsapp_call_logs
WHERE upload_id = 'your-upload-id'
ORDER BY timestamp DESC
LIMIT 50;
```

### Get call statistics

```sql
SELECT
    call_type,
    status,
    COUNT(*) as call_count,
    SUM(duration) as total_duration_seconds,
    AVG(duration) as avg_duration_seconds
FROM whatsapp_call_logs
WHERE upload_id = 'your-upload-id'
GROUP BY call_type, status
ORDER BY call_count DESC;
```

### Get missed calls

```sql
SELECT * FROM whatsapp_call_logs
WHERE upload_id = 'your-upload-id'
  AND status = 'missed'
ORDER BY timestamp DESC;
```

### Get all contacts

```sql
SELECT * FROM whatsapp_contacts
WHERE upload_id = 'your-upload-id'
ORDER BY jid;
```

## Python API

### Using Database Operations

```python
from realtime.utils.db import whatsapp_operations

# Initialize schema
await whatsapp_operations.init_whatsapp_schema()

# Get extraction status
status = await whatsapp_operations.get_extraction_status(upload_id)
print(f"Status: {status['extraction_status']}")
print(f"Messages: {status['processed_messages']}/{status['total_messages']}")

# Get messages
messages = await whatsapp_operations.get_whatsapp_messages(
    upload_id,
    chat_jid='1234567890@s.whatsapp.net',
    limit=50
)

for msg in messages:
    print(f"{msg['sender_name']}: {msg['message_text']}")

# Get call logs
call_logs = await whatsapp_operations.get_whatsapp_call_logs(
    upload_id,
    limit=50
)

for call in call_logs:
    direction = "Outgoing" if call['from_me'] else "Incoming"
    print(f"{direction} {call['call_type']} call - {call['duration']}s - {call['status']}")
```

### Using the Extractor Directly

```python
from realtime.worker.ufdr_whatsapp_extractor import UFDRWhatsAppExtractor
from realtime.utils.db import whatsapp_operations

# Create extractor
extractor = UFDRWhatsAppExtractor(ufdr_path, upload_id)

# Run extraction
await extractor.extract_and_load(whatsapp_operations)
```

## Supported WhatsApp Database Schemas

The extractor supports multiple WhatsApp database schemas:

1. **Older Schema** - `messages` table with direct columns
2. **Newer Schema** - `message` table with separate `message_media`, `jid`, `chat` tables

The extractor automatically detects the schema and extracts data accordingly.

## WhatsApp Database Files

The extractor looks for the following databases in UFDR files:

- `files/Database/msgstore.db` - Main WhatsApp messages database
- `files/Database/msgstore-YYYY-MM-DD.*.db` - Backup databases
- `files/Database/wa.db` - WhatsApp application database

## Data Fields

### Message Fields

- **msg_id**: Unique message identifier
- **chat_jid**: Chat/conversation identifier (phone number or group ID)
- **sender_jid**: Sender's WhatsApp ID (for received messages)
- **from_me**: 1 if sent by device owner, 0 if received
- **message_text**: Text content of the message
- **message_type**: Type of message (0 = text, other values for media/system messages)
- **timestamp**: Message timestamp in milliseconds since epoch
- **timestamp_dt**: Converted timestamp as PostgreSQL datetime
- **media_***: Media file information (URL, path, MIME type, size, duration)
- **latitude/longitude**: Location data for location messages
- **starred**: 1 if message is starred
- **forwarded**: 1 if message was forwarded
- **raw_json**: Complete SQLite row data as JSON for forensic purposes

## Performance Considerations

- Messages are inserted in batches of 100 for optimal performance
- Database indexes are created on frequently queried columns
- Deduplication is performed during extraction to avoid duplicate messages
- Temp files are cleaned up automatically after extraction

## Error Handling

The extraction pipeline includes comprehensive error handling:

1. **Schema Initialization**: Verifies database connectivity
2. **File Extraction**: Validates UFDR structure
3. **Database Parsing**: Handles various SQLite schemas
4. **Data Insertion**: Uses PostgreSQL transactions
5. **Cleanup**: Always removes temporary files

Extraction status is tracked in the `ufdr_extractions` table with detailed error messages.

## Troubleshooting

### Extraction Failed

Check the `ufdr_extractions` table for error messages:

```sql
SELECT * FROM ufdr_extractions
WHERE upload_id = 'your-upload-id';
```

### No Messages Extracted

Some WhatsApp databases may be empty or encrypted. Check logs for:
- "Parsed 0 messages" - Database is empty
- SQLite errors - Database may be corrupted

### Performance Issues

For large UFDR files (>1GB):
- Extraction may take several minutes
- Monitor Redis progress via `/api/uploads/{upload_id}/ingest-progress`
- Check RQ worker logs for detailed progress

## Future Enhancements

Potential improvements to the extraction pipeline:

1. **Media Extraction**: Extract media files (images, videos, audio) from UFDR
2. **Additional Apps**: Support for other messaging apps (Telegram, Signal, etc.)
3. **Encryption Handling**: Support for encrypted WhatsApp databases
4. **Group Analysis**: Enhanced group chat metadata and participant tracking
5. **Timeline Visualization**: Generate visual timelines of message activity
6. **Export Formats**: Export to JSONL, CSV, or forensic report formats

## See Also

- [ufdr2dir.py](../ufdr2dir.py) - Original UFDR extraction script
- [UFDR-TO-DIR.md](../UFDR-TO-DIR.md) - Documentation for UFDR file format
- Database operations: [realtime/utils/db/](../realtime/utils/db/)
