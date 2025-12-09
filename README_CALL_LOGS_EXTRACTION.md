# Quick Start: UFDR Call Logs Extraction

## What It Does

Extracts **all call logs from all apps** (WhatsApp, Telegram, Skype, Phone, Facebook Messenger, Viber, Line, Instagram, etc.) from Cellebrite UFDR files into a **single unified PostgreSQL table** with a `source_app` column.

## Quick Test

```bash
# 1. Initialize schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -f realtime/utils/db/call_logs_schema.sql

# 2. Run extraction
python scripts/run_call_logs_extraction.py \
    "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" \
    test-calls-001

# 3. Check results
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT source_app, COUNT(*) FROM call_logs WHERE upload_id = 'test-calls-001' GROUP BY source_app;"
```

## Expected Results (Google Pixel 3 UFDR)

```
 source_app          | count
--------------------+-------
 Telegram           |     8
 Facebook Messenger |     8
 Skype              |     5
 WhatsApp           |     4
 Viber              |     4
 Line               |     4
 Instagram          |     4
 TextNow            |     3
 Wickr Pro          |     2
Total: 56 calls
```

## Key Features

✅ **Unified Table** - All apps in one table with `source_app` column
✅ **56 calls** extracted from 9 different apps
✅ **Complete metadata** - timestamps, duration, parties, status
✅ **Automatic extraction** - runs on UFDR upload
✅ **Video/Voice detection** - `is_video_call` flag
✅ **Party tracking** - supports group/conference calls

## Database Schema

### Main Table: `call_logs`

```sql
-- Key columns
source_app          -- WhatsApp, Telegram, Phone, Skype, etc.
direction           -- Incoming, Outgoing
call_type           -- Voice, Video
status              -- Established, Missed, Rejected, Cancelled
call_timestamp_dt   -- When the call was made
duration_seconds    -- Call duration
is_video_call       -- TRUE/FALSE
from_party_name     -- Caller name
to_party_name       -- Recipient name
```

## Sample Queries

### All WhatsApp calls
```sql
SELECT direction, call_type, status, call_timestamp_dt, duration_seconds
FROM call_logs
WHERE source_app = 'WhatsApp'
ORDER BY call_timestamp_dt DESC;
```

### Missed calls
```sql
SELECT source_app, call_timestamp_dt, from_party_name
FROM call_logs
WHERE status = 'Missed'
ORDER BY call_timestamp_dt DESC;
```

### Video calls
```sql
SELECT source_app, direction, call_timestamp_dt, duration_seconds
FROM call_logs
WHERE is_video_call = TRUE
ORDER BY call_timestamp_dt DESC;
```

### Calls by app
```sql
SELECT source_app, COUNT(*) as call_count,
       SUM(duration_seconds) as total_duration
FROM call_logs
GROUP BY source_app
ORDER BY call_count DESC;
```

## Python API

```python
from realtime.utils.db import call_logs_operations

# Get statistics
stats = await call_logs_operations.get_call_log_statistics(upload_id)
print(f"Total calls: {stats['total_calls']}")

# WhatsApp calls only
calls = await call_logs_operations.get_call_logs(
    upload_id,
    source_app='WhatsApp'
)

# Incoming video calls
video = await call_logs_operations.get_call_logs(
    upload_id,
    direction='Incoming',
    is_video=True
)
```

## Files

- **Schema**: `realtime/utils/db/call_logs_schema.sql`
- **Extractor**: `realtime/worker/ufdr_call_logs_extractor.py`
- **Operations**: `realtime/utils/db/call_logs_operations.py`
- **Test Script**: `scripts/run_call_logs_extraction.py`
- **Docs**: `docs/CALL_LOGS_EXTRACTION.md`

## Automatic Extraction

When you upload a UFDR file via the API, call logs are automatically extracted:

1. Upload UFDR file
2. Worker detects UFDR format
3. Extracts installed apps
4. **Extracts call logs from all apps**
5. Data ready to query

## Troubleshooting

**No calls extracted?**
```bash
# Check if UFDR has Call models
unzip -p "file.ufdr" report.xml | grep -c '<model type="Call"'
```

**Table doesn't exist?**
```bash
# Initialize schema
psql $DATABASE_URL -f realtime/utils/db/call_logs_schema.sql
```

**Worker crashes?**
```bash
# Run with fork safety disabled
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest --url redis://localhost:6379/0
```

## Benefits of Unified Table

- ✅ Single query for all call activity
- ✅ Easy cross-app communication analysis
- ✅ Simple timeline of all calls
- ✅ No complex UNION queries
- ✅ Easy filtering by app
- ✅ Fast contact searches

## What's Extracted

- Call timestamps
- Call duration
- Caller/recipient names and identifiers
- Call type (Voice/Video)
- Call direction (Incoming/Outgoing)
- Call status (Established/Missed/Rejected)
- App that made the call
- Network information
- All parties (supports group calls)
- Raw XML/JSON for forensics

---

**Ready to test!** See [CALL_LOGS_EXTRACTION.md](docs/CALL_LOGS_EXTRACTION.md) for full documentation.
