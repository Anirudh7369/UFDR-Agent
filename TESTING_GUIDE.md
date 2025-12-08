# Quick Testing Guide for Installed Apps Extraction

## Step-by-Step Testing on Ananya's Laptop

### 1. Prerequisites Check

```bash
# Ensure you're in the project directory
cd /Users/aviothic/Desktop/UFDR-Agent

# Check if .env file exists
ls -la realtime/.env

# Verify Redis is running
redis-cli ping
# Should return: PONG

# If Redis not running:
brew services start redis

# Verify PostgreSQL is accessible
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -c "SELECT 1;"
# Should return: 1
```

### 2. Initialize Database Schema

```bash
# Initialize the installed apps schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -f /Users/aviothic/Desktop/UFDR-Agent/realtime/utils/db/installed_apps_schema.sql

# Verify tables were created
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "\dt" | grep -E "installed_apps|app_extractions"
```

Expected output:
```
 public | app_extractions              | table | ufdr_team
 public | installed_app_categories     | table | ufdr_team
 public | installed_app_permissions    | table | ufdr_team
 public | installed_apps               | table | ufdr_team
```

### 3. Run Test Extraction

```bash
# Run the extraction script
python scripts/run_apps_extraction.py \
    "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" \
    test-apps-001
```

Expected output:
```
================================================================================
UFDR Installed Apps Extraction Test
================================================================================
UFDR File: Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr
Upload ID: test-apps-001

[1/4] Initializing database schema...
✓ Schema initialized successfully

[2/4] Starting extraction...
[INFO] 2025-12-09 ... Extracting report.xml from ...
[INFO] 2025-12-09 ... Parsing installed applications from: ...
[INFO] 2025-12-09 ... Parsed 50 apps...
[INFO] 2025-12-09 ... Parsed 100 apps...
...
[INFO] 2025-12-09 ... Parsed 290 installed applications
[INFO] 2025-12-09 ... Total unique apps: 290
[INFO] 2025-12-09 ... Processed 50/290 apps
...
[INFO] 2025-12-09 ... Processed 290/290 apps
✓ Extraction completed successfully

[3/4] Retrieving extraction status...
✓ Status: completed
  Total apps: 290
  Processed apps: 290

[4/4] Getting app statistics...
================================================================================
EXTRACTION SUMMARY
================================================================================
Total Apps: 290
Apps with Install Timestamps: ~280
First Install: 2019-XX-XX...
Last Install: 2020-XX-XX...

Top 10 Categories:
--------------------------------------------------------------------------------
  1. SystemApplication: 120 apps
  2. Utilities: 45 apps
  3. SocialNetworking: 15 apps
  ...

Top 10 Permissions:
--------------------------------------------------------------------------------
  1. Network: 200 apps
  2. Storage: 180 apps
  3. Location: 85 apps
  ...

Sample Installed Apps (10 most recent):
--------------------------------------------------------------------------------
1. Skype - free IM & video calls
   Package: com.skype.raider
   Version: 8.61.0.96
   Installed: 2020-09-12T11:56:29
   Categories: SocialNetworking, ChatApplications
...

================================================================================
✓ Test completed successfully!
================================================================================
```

### 4. Verify Data in Database

```bash
# Check total apps extracted
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT COUNT(*) as total_apps FROM installed_apps WHERE upload_id = 'test-apps-001';"

# Expected: 290

# Check extraction status
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT * FROM app_extractions WHERE upload_id = 'test-apps-001';"

# Check sample apps with install timestamps
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT app_name, app_version, install_timestamp_dt FROM installed_apps WHERE upload_id = 'test-apps-001' AND install_timestamp_dt IS NOT NULL ORDER BY install_timestamp_dt DESC LIMIT 5;"
```

### 5. Test SQL Queries

```bash
# Get apps by category
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT category, COUNT(*) as count FROM installed_app_categories WHERE upload_id = 'test-apps-001' GROUP BY category ORDER BY count DESC LIMIT 10;"

# Get apps with location permission
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT DISTINCT a.app_name FROM installed_apps a JOIN installed_app_permissions p ON a.id = p.app_id WHERE a.upload_id = 'test-apps-001' AND p.permission_category = 'Location' LIMIT 10;"

# Get installation timeline
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent \
    -c "SELECT DATE(install_timestamp_dt) as date, COUNT(*) as apps_installed FROM installed_apps WHERE upload_id = 'test-apps-001' AND install_timestamp_dt IS NOT NULL GROUP BY DATE(install_timestamp_dt) ORDER BY date DESC LIMIT 10;"
```

## Testing with Upload Workflow (Automatic Extraction)

### 1. Start RQ Worker

```bash
# In a separate terminal window
cd /Users/aviothic/Desktop/UFDR-Agent

# Start RQ worker with macOS fork safety
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest --url redis://localhost:6379/0
```

### 2. Upload UFDR File via API

```bash
# Use the API to upload (or use the web interface)
# The worker will automatically detect UFDR and extract apps

# Monitor worker logs for:
# [worker] Detected UFDR file (Cellebrite format)
# [worker] Starting Installed Apps extraction from UFDR...
# [apps_extractor] Loaded .env from: ...
# [INFO] ... Parsing installed applications from: ...
# [INFO] ... Parsed 290 installed applications
# [worker] Installed Apps extraction completed successfully
```

### 3. Check Progress via Redis

```bash
# Get upload ID from API response, then:
redis-cli HGETALL "ingest_progress:your-upload-id"
```

Expected fields:
```
"status" -> "done"
"apps_extracted" -> "true"
```

## Common Issues and Solutions

### Issue: "relation 'installed_apps' does not exist"
**Solution:** Initialize the schema first:
```bash
psql $DATABASE_URL -f realtime/utils/db/installed_apps_schema.sql
```

### Issue: "DATABASE_URL environment variable is not set"
**Solution:** Check `.env` file exists and contains DATABASE_URL:
```bash
cat realtime/.env | grep DATABASE_URL
```

### Issue: "No apps extracted"
**Solution:** Check if UFDR file contains report.xml:
```bash
unzip -l "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" | grep report.xml
```

### Issue: Worker crashes with "fork() was called"
**Solution:** Run worker with fork safety disabled:
```bash
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest --url redis://localhost:6379/0
```

### Issue: "Connection refused to Redis"
**Solution:** Start Redis:
```bash
brew services start redis
# Or manually:
redis-server
```

## Success Criteria

✅ Schema initialized without errors
✅ Test script completes successfully
✅ 290 apps extracted from sample UFDR file
✅ Apps have installation timestamps populated
✅ Categories and permissions are extracted
✅ SQL queries return expected results
✅ Automatic extraction works via upload workflow

## Files to Check

After successful test:
- Database tables populated: `installed_apps`, `app_extractions`
- Logs show successful parsing
- No error messages in `app_extractions.error_message`

## Next Steps After Successful Testing

1. Clean up test data:
   ```sql
   DELETE FROM app_extractions WHERE upload_id = 'test-apps-001';
   -- This will cascade delete apps due to foreign key
   ```

2. Ready for production use!

## Quick Commands Reference

```bash
# Start Redis
brew services start redis

# Start RQ Worker
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest --url redis://localhost:6379/0

# Initialize Schema
psql $DATABASE_URL -f realtime/utils/db/installed_apps_schema.sql

# Run Test
python scripts/run_apps_extraction.py "path/to/file.ufdr" upload-id

# Check Results
psql $DATABASE_URL -c "SELECT COUNT(*) FROM installed_apps WHERE upload_id = 'upload-id';"

# Clean Test Data
psql $DATABASE_URL -c "DELETE FROM app_extractions WHERE upload_id = 'upload-id';"
```

## Expected Test Results

From the Google Pixel 3 UFDR file:
- **Total Apps**: 290
- **Apps with Timestamps**: ~280-290
- **Top Categories**: SystemApplication, Utilities, SocialNetworking
- **Top Permissions**: Network, Storage, Location
- **Sample Apps**: Skype, WhatsApp, Chrome, Maps, Gmail
- **Date Range**: Apps installed between 2019-2020

Good luck with testing! 🚀
