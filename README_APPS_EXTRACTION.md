# UFDR Installed Apps Extraction System

## Overview

This system extracts installed application data from Cellebrite UFDR files and stores it in PostgreSQL with installation timestamps, permissions, categories, and complete metadata.

## What This System Does

When a UFDR file is uploaded:
1. **Detects** UFDR format (Cellebrite extraction)
2. **Downloads** file from MinIO (cloud storage)
3. **Extracts** report.xml from the UFDR archive
4. **Parses** all InstalledApplication models
5. **Stores** 290+ apps with installation timestamps in PostgreSQL

## Key Features

✅ **Installation Timestamps** - Every app has install date/time
✅ **Permissions Tracking** - What permissions each app uses
✅ **Category Classification** - Apps grouped by type (Social, Productivity, etc.)
✅ **Automatic Extraction** - Runs automatically on upload
✅ **MinIO Integration** - Downloads from cloud storage
✅ **Efficient Parsing** - Memory-efficient XML processing

## File Structure

```
UFDR-Agent/
├── realtime/
│   ├── worker/
│   │   ├── ingest_worker.py          # Main upload processor
│   │   └── ufdr_apps_extractor.py    # Apps extraction logic
│   └── utils/
│       └── db/
│           ├── connection.py          # Database connection pool
│           ├── apps_operations.py     # Database operations
│           └── installed_apps_schema.sql  # Database schema
├── scripts/
│   └── run_apps_extraction.py         # Test script
├── docs/
│   ├── INSTALLED_APPS_EXTRACTION.md   # User guide
│   └── APPS_IMPLEMENTATION_SUMMARY.md # Implementation details
└── TESTING_GUIDE.md                   # Testing instructions
```

## Database Tables

### `app_extractions`
Tracks extraction jobs with status and progress.

### `installed_apps`
Main table with all app data:
- Package name, display name, version
- **Install timestamp** (milliseconds + datetime)
- Last launched timestamp
- Permissions (JSONB array)
- Categories (JSONB array)
- Complete metadata

### `installed_app_permissions`
Normalized permission data for fast filtering.

### `installed_app_categories`
Normalized category data for classification.

## Quick Start

### 1. Initialize Database

```bash
psql $DATABASE_URL -f realtime/utils/db/installed_apps_schema.sql
```

### 2. Test Extraction

```bash
python scripts/run_apps_extraction.py "path/to/file.ufdr" test-001
```

### 3. Verify Data

```sql
SELECT COUNT(*) FROM installed_apps WHERE upload_id = 'test-001';
-- Should return: 290 (for Google Pixel 3 sample file)
```

### 4. Start Worker for Automatic Extraction

```bash
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES rq worker ingest --url redis://localhost:6379/0
```

## Sample Queries

### Get all apps with install dates
```sql
SELECT app_name, app_version, install_timestamp_dt
FROM installed_apps
WHERE upload_id = 'your-upload-id'
ORDER BY install_timestamp_dt DESC;
```

### Get social media apps
```sql
SELECT DISTINCT a.app_name, a.install_timestamp_dt
FROM installed_apps a
JOIN installed_app_categories c ON a.id = c.app_id
WHERE a.upload_id = 'your-upload-id'
  AND c.category = 'SocialNetworking';
```

### Get apps with location permission
```sql
SELECT DISTINCT a.app_name
FROM installed_apps a
JOIN installed_app_permissions p ON a.id = p.app_id
WHERE a.upload_id = 'your-upload-id'
  AND p.permission_category = 'Location';
```

### Installation timeline
```sql
SELECT
    DATE(install_timestamp_dt) as date,
    COUNT(*) as apps_installed
FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND install_timestamp_dt IS NOT NULL
GROUP BY DATE(install_timestamp_dt)
ORDER BY date DESC;
```

## Environment Variables

Required in `realtime/.env`:

```env
DATABASE_URL=postgresql://user:password@host:port/database
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=ufdr-uploads
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
REDIS_URL=redis://localhost:6379/0
```

## Expected Output

From a Google Pixel 3 UFDR file:
- **290 unique apps** extracted
- **280+ apps** with install timestamps
- **Top categories**: SystemApplication, Utilities, SocialNetworking
- **Top permissions**: Network, Storage, Location
- **Sample apps**: Skype, WhatsApp, Chrome, Maps, Gmail

## Documentation

- **[INSTALLED_APPS_EXTRACTION.md](docs/INSTALLED_APPS_EXTRACTION.md)** - Complete user guide with all SQL queries
- **[APPS_IMPLEMENTATION_SUMMARY.md](docs/APPS_IMPLEMENTATION_SUMMARY.md)** - Technical implementation details
- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Step-by-step testing instructions

## Architecture

```
Upload UFDR file
    ↓
MinIO Storage
    ↓
Worker detects UFDR
    ↓
Download from MinIO
    ↓
Extract report.xml
    ↓
Parse InstalledApplication models
    ↓
Insert into PostgreSQL
    ↓
Query via SQL/Python API
```

## Development

### Run Tests
```bash
python scripts/run_apps_extraction.py "file.ufdr" test-id
```

### Check Logs
```bash
# Worker logs
rq worker ingest --url redis://localhost:6379/0

# Database status
psql $DATABASE_URL -c "SELECT * FROM app_extractions ORDER BY created_at DESC LIMIT 5;"
```

### Clean Test Data
```sql
DELETE FROM app_extractions WHERE upload_id = 'test-id';
-- Cascades to all related tables
```

## Troubleshooting

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for common issues and solutions.

## License

Part of the UFDR-Agent forensic analysis system.
