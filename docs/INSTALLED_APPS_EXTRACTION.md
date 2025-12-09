# Installed Applications Extraction from UFDR Files

## Overview

This document describes the installed applications extraction pipeline that processes Cellebrite UFDR files and extracts all installed Android app data into PostgreSQL for forensic analysis.

## Architecture

The extraction pipeline consists of the following components:

1. **Database Schema** ([realtime/utils/db/installed_apps_schema.sql](../realtime/utils/db/installed_apps_schema.sql))
   - PostgreSQL tables for installed apps with complete metadata
   - Optimized indexes for fast querying
   - Normalized tables for permissions and categories
   - View for easy data access

2. **Database Operations** ([realtime/utils/db/apps_operations.py](../realtime/utils/db/apps_operations.py))
   - Async database operations using asyncpg
   - Bulk insert capabilities for performance
   - Status tracking for extraction jobs
   - Search and statistics functions

3. **UFDR Apps Extractor** ([realtime/worker/ufdr_apps_extractor.py](../realtime/worker/ufdr_apps_extractor.py))
   - Extracts report.xml from UFDR files
   - Parses InstalledApplication XML models
   - Handles deduplication
   - Supports both local files and MinIO URLs

4. **Integration with Upload Workflow** ([realtime/worker/ingest_worker.py](../realtime/worker/ingest_worker.py))
   - Automatically detects UFDR files
   - Triggers app extraction after upload completes
   - Runs alongside WhatsApp extraction

## Database Schema

### Main Tables

#### `app_extractions`
Tracks extraction jobs:
- Upload ID
- Status (pending, processing, completed, failed)
- Progress counters
- Error messages

#### `installed_apps`
Stores all installed applications with complete metadata:
- **Identification**: Package name, display name, version, GUID
- **Timestamps**: Install timestamp (milliseconds + datetime), last launched
- **Metadata**: Decoding status, operation mode, deleted state
- **Arrays**: Permissions (JSONB), categories (JSONB), directory paths (JSONB)
- **Forensics**: Raw XML and complete JSON data

#### `installed_app_permissions`
Normalized permission data (for easier querying):
- App ID, upload ID, app identifier
- Permission category

#### `installed_app_categories`
Normalized category data:
- App ID, upload ID, app identifier
- Category name

### View

#### `installed_apps_view`
Convenient view joining apps with extraction status for easy querying.

## Data Extracted

### Application Information
- **Package Name**: Android package identifier (e.g., `com.whatsapp`)
- **Display Name**: User-visible app name (e.g., "WhatsApp Messenger")
- **Version**: Version string (e.g., "2.20.196.8")
- **App GUID**: Unique identifier if available

### Timestamps
- **Install Timestamp**: When the app was installed (milliseconds since epoch)
- **Install DateTime**: Converted timestamp for easy querying
- **Last Launched**: When the app was last opened (if available)

### Metadata
- **Decoding Status**: Whether Cellebrite successfully decoded the app data
- **Is Emulatable**: Whether the app can be emulated
- **Operation Mode**: Foreground or Background
- **Deleted State**: Intact or Deleted
- **Decoding Confidence**: High, Medium, or Low

### Permissions
Array of permission categories the app uses:
- Accounts
- AppInfo
- Audio
- Bluetooth
- Camera
- Contacts
- Location
- Network
- PersonalInfo
- SMS
- Storage
- And more...

### Categories
App categories for classification:
- SocialNetworking
- ChatApplications
- Productivity
- Entertainment
- Games
- Utilities
- And more...

### File System Paths
Complete list of directories associated with the app on the device.

## Usage

### Manual Extraction

To manually extract installed apps from a UFDR file:

```bash
python scripts/run_apps_extraction.py <ufdr_file_path_or_url> <upload_id>
```

Example with local file:
```bash
python scripts/run_apps_extraction.py \
    "Google G013A Pixel 3 Android11_2023-06-07_Report.ufdr" \
    investigation-2024-001
```

Example with MinIO URL:
```bash
python scripts/run_apps_extraction.py \
    "http://localhost:9000/ufdr-uploads/uploads/xxx/report.ufdr" \
    investigation-2024-001
```

### Automatic Extraction

When files are uploaded through the API:

1. Upload is initiated via `/api/uploads/init`
2. File is uploaded to MinIO/S3 in parts
3. Upload is completed via `/api/uploads/{upload_id}/complete`
4. Ingest worker processes the file
5. If UFDR format is detected:
   - WhatsApp extraction runs automatically
   - **Installed Apps extraction runs automatically**
6. The extractor downloads the file directly from MinIO using the URL
7. Data is inserted into PostgreSQL

Progress can be monitored via `/api/uploads/{upload_id}/ingest-progress`

## Querying the Data

### Get all installed apps

```sql
SELECT * FROM installed_apps_view
WHERE upload_id = 'your-upload-id'
ORDER BY install_timestamp_dt DESC
LIMIT 100;
```

### Get apps installed in a specific time range

```sql
SELECT app_name, app_identifier, install_timestamp_dt
FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND install_timestamp_dt BETWEEN '2020-01-01' AND '2020-12-31'
ORDER BY install_timestamp_dt DESC;
```

### Get apps by category

```sql
SELECT DISTINCT a.*
FROM installed_apps a
JOIN installed_app_categories c ON a.id = c.app_id
WHERE a.upload_id = 'your-upload-id'
  AND c.category = 'SocialNetworking'
ORDER BY a.install_timestamp_dt DESC;
```

### Get apps with specific permission

```sql
SELECT DISTINCT a.*
FROM installed_apps a
JOIN installed_app_permissions p ON a.id = p.app_id
WHERE a.upload_id = 'your-upload-id'
  AND p.permission_category = 'Location'
ORDER BY a.install_timestamp_dt DESC;
```

### Get app statistics by category

```sql
SELECT category, COUNT(*) as app_count
FROM installed_app_categories
WHERE upload_id = 'your-upload-id'
GROUP BY category
ORDER BY app_count DESC;
```

### Get most recently installed apps

```sql
SELECT app_name, app_identifier, app_version, install_timestamp_dt
FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND install_timestamp_dt IS NOT NULL
ORDER BY install_timestamp_dt DESC
LIMIT 20;
```

### Search for apps by name

```sql
SELECT * FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND app_name ILIKE '%whatsapp%'
ORDER BY install_timestamp_dt DESC;
```

### Get timeline of app installations

```sql
SELECT
    DATE(install_timestamp_dt) as install_date,
    COUNT(*) as apps_installed,
    STRING_AGG(app_name, ', ' ORDER BY install_timestamp_dt) as apps
FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND install_timestamp_dt IS NOT NULL
GROUP BY DATE(install_timestamp_dt)
ORDER BY install_date DESC;
```

### Get apps with multiple permissions

```sql
SELECT
    a.app_name,
    a.app_identifier,
    COUNT(DISTINCT p.permission_category) as permission_count,
    STRING_AGG(DISTINCT p.permission_category, ', ') as permissions
FROM installed_apps a
JOIN installed_app_permissions p ON a.id = p.app_id
WHERE a.upload_id = 'your-upload-id'
GROUP BY a.id, a.app_name, a.app_identifier
HAVING COUNT(DISTINCT p.permission_category) > 5
ORDER BY permission_count DESC;
```

## Python API

### Using Database Operations

```python
from realtime.utils.db import apps_operations

# Initialize schema
await apps_operations.init_apps_schema()

# Get extraction status
status = await apps_operations.get_app_extraction_status(upload_id)
print(f"Status: {status['extraction_status']}")
print(f"Apps: {status['processed_apps']}/{status['total_apps']}")

# Get installed apps
apps = await apps_operations.get_installed_apps(
    upload_id,
    category='SocialNetworking',
    limit=50
)

for app in apps:
    print(f"{app['app_name']} ({app['app_identifier']}) - v{app['app_version']}")
    print(f"  Installed: {app['install_timestamp_dt']}")

# Get statistics
stats = await apps_operations.get_app_statistics(upload_id)
print(f"Total apps: {stats['total_apps']}")
print(f"First install: {stats['first_install_date']}")
print(f"Last install: {stats['last_install_date']}")

for category in stats['categories'][:10]:
    print(f"  {category['category']}: {category['count']} apps")

# Search for apps
results = await apps_operations.search_apps(upload_id, 'facebook')
for app in results:
    print(f"Found: {app['app_name']}")
```

### Using the Extractor Directly

```python
from realtime.worker.ufdr_apps_extractor import UFDRAppsExtractor
from realtime.utils.db import apps_operations

# Create extractor (supports both local paths and MinIO URLs)
extractor = UFDRAppsExtractor(ufdr_path_or_url, upload_id)

# Run extraction
await extractor.extract_and_load(apps_operations)
```

## Performance Considerations

- **XML Parsing**: Uses `iterparse` for memory-efficient processing of large XML files
- **Batch Inserts**: Apps are inserted in batches of 50 for optimal performance
- **Database Indexes**: Indexes on frequently queried columns (identifier, name, timestamps)
- **Deduplication**: Apps are deduplicated by package name during extraction
- **JSONB**: Permissions and categories stored as JSONB for efficient querying
- **Normalized Tables**: Separate tables for permissions/categories enable fast filtering
- **Memory Management**: XML elements are cleared during parsing to minimize memory usage
- **Temp File Cleanup**: All temporary files are automatically cleaned up after extraction

## Error Handling

The extraction pipeline includes comprehensive error handling:

1. **Schema Initialization**: Verifies database connectivity
2. **File Download**: Validates MinIO/S3 URLs and credentials
3. **XML Parsing**: Handles malformed XML gracefully
4. **Data Insertion**: Uses PostgreSQL transactions
5. **Cleanup**: Always removes temporary files, even on failure

Extraction status is tracked in the `app_extractions` table with detailed error messages.

## Sample Data from Google Pixel 3

From the test UFDR file, we extracted **290 unique applications** with:

- Install timestamps for most apps
- Permission data (e.g., Location, Camera, Contacts)
- Categories (SocialNetworking, ChatApplications, Productivity)
- Complete metadata for forensic analysis

**Example Apps Extracted:**
- Skype - free IM & video calls (com.skype.raider) v8.61.0.96
- WhatsApp Messenger (com.whatsapp) v2.20.196.8
- Chrome Browser (com.android.chrome)
- Google Maps (com.google.android.apps.maps)
- And 286 more...

## Troubleshooting

### Extraction Failed

Check the `app_extractions` table for error messages:

```sql
SELECT * FROM app_extractions
WHERE upload_id = 'your-upload-id';
```

### No Apps Extracted

Some UFDR files may not contain InstalledApplication models:
- Check logs for "Parsed 0 installed applications"
- Verify the UFDR file contains report.xml
- Ensure the device was properly extracted by Cellebrite

### Performance Issues

For very large UFDR files (>1GB):
- Extraction may take several minutes
- Monitor Redis progress via `/api/uploads/{upload_id}/ingest-progress`
- Check RQ worker logs for detailed progress

### Database Connection Issues

Ensure environment variables are set correctly:
- `DATABASE_URL=postgresql://user:password@host:port/database`
- Check `.env` file in `realtime/` directory

## Schema Initialization

Before first use, initialize the database schema:

```bash
# Option 1: Using psql
psql $DATABASE_URL -f realtime/utils/db/installed_apps_schema.sql

# Option 2: Using Python
python -c "import asyncio; from realtime.utils.db import apps_operations; asyncio.run(apps_operations.init_apps_schema())"
```

## Future Enhancements

Potential improvements to the extraction pipeline:

1. **App Icons**: Extract and store app icon images
2. **App Usage Stats**: Parse app usage time and frequency data
3. **App Permissions History**: Track permission changes over time
4. **App Data Size**: Include storage usage per app
5. **Uninstalled Apps**: Detect and track previously uninstalled apps
6. **App Updates**: Track app update history
7. **Export Formats**: Export to CSV, JSON, or forensic report formats
8. **Visualization**: Timeline visualization of app installations
9. **Risk Assessment**: Flag suspicious apps or permission combinations
10. **Cross-Device Analysis**: Compare installed apps across multiple devices

## Related Documentation

- [WhatsApp Extraction](WHATSAPP_EXTRACTION.md) - WhatsApp data extraction from UFDR
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - Complete implementation overview
- [ufdr2dir.py](../ufdr2dir.py) - Original UFDR extraction script
- [UFDR-TO-DIR.md](../UFDR-TO-DIR.md) - Documentation for UFDR file format

## Example Queries for Forensic Analysis

### Identify social media apps

```sql
SELECT app_name, app_identifier, install_timestamp_dt
FROM installed_apps a
JOIN installed_app_categories c ON a.id = c.app_id
WHERE a.upload_id = 'your-upload-id'
  AND c.category IN ('SocialNetworking', 'ChatApplications')
ORDER BY install_timestamp_dt DESC;
```

### Find apps with location access

```sql
SELECT DISTINCT a.app_name, a.app_identifier, a.install_timestamp_dt
FROM installed_apps a
JOIN installed_app_permissions p ON a.id = p.app_id
WHERE a.upload_id = 'your-upload-id'
  AND p.permission_category = 'Location'
ORDER BY a.install_timestamp_dt DESC;
```

### Identify recently installed apps (last 30 days before extraction)

```sql
SELECT app_name, app_identifier, install_timestamp_dt
FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND install_timestamp_dt > (
    SELECT MAX(install_timestamp_dt) - INTERVAL '30 days'
    FROM installed_apps
    WHERE upload_id = 'your-upload-id'
  )
ORDER BY install_timestamp_dt DESC;
```

### Find deleted apps

```sql
SELECT app_name, app_identifier, install_timestamp_dt
FROM installed_apps
WHERE upload_id = 'your-upload-id'
  AND deleted_state = 'Deleted'
ORDER BY install_timestamp_dt DESC;
```

## See Also

- Database operations: [realtime/utils/db/apps_operations.py](../realtime/utils/db/apps_operations.py)
- Extractor implementation: [realtime/worker/ufdr_apps_extractor.py](../realtime/worker/ufdr_apps_extractor.py)
- Database schema: [realtime/utils/db/installed_apps_schema.sql](../realtime/utils/db/installed_apps_schema.sql)
