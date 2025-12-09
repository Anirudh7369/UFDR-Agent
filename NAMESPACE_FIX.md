# XML Namespace Fix for UFDR Apps Extraction

## Problem

The initial upload showed:
```
[INFO] Parsed 0 installed applications
[WARNING] No installed applications found in UFDR file
```

Despite the UFDR file containing 580+ InstalledApplication entries.

## Root Cause

The Cellebrite UFDR `report.xml` file uses an XML namespace:
```xml
<project xmlns="http://pa.cellebrite.com/report/2.0">
```

This means all XML elements have a namespace prefix internally:
- `<model>` becomes `{http://pa.cellebrite.com/report/2.0}model`
- `<field>` becomes `{http://pa.cellebrite.com/report/2.0}field`
- etc.

The original code was looking for elements without accounting for the namespace, so it couldn't find any matches.

## Solution

Modified `realtime/worker/ufdr_apps_extractor.py` to:

1. **Strip namespace from tag names** when checking element types:
   ```python
   tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
   ```

2. **Iterate through children directly** instead of using `findall()`:
   ```python
   for child in model_elem:
       tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
       if tag_name == 'field':
           # Process field
   ```

3. **Handle nested elements** by iterating through sub-children:
   ```python
   for sub_child in child:
       sub_tag = sub_child.tag.split('}')[-1] if '}' in sub_child.tag else sub_child.tag
       if sub_tag == 'value':
           value_elem = sub_child
   ```

## Results After Fix

✅ **340 unique apps extracted** (from 580 XML entries after deduplication)
✅ **95 apps with install timestamps**
✅ **Categories extracted**: SocialNetworking, DeveloperTools, ChatApplications, etc.
✅ **Permissions extracted**: Network, AppInfo, Accounts, Bluetooth, etc.

### Sample Data
```
Google Play services         | 20.36.15           | 2020-10-03 22:03:55
Health Sync                  | 6.7.7              | 2020-10-02 07:30:11
Garmin Connect™              | 4.35.1             | 2020-10-02 07:18:35
Feature for Instagram        | 158.0.0.30.123     | 2020-09-23 20:00:51
Sleep as Android            | 20200828           | 2020-09-17 00:25:35
ZOOM Cloud Meetings         | 5.2.45120.0906     | 2020-09-14 21:29:11
```

## Testing

```bash
# Test extraction
python3 scripts/run_apps_extraction.py "path/to/file.ufdr" test-id

# Verify in database
psql $DATABASE_URL -c "SELECT COUNT(*) FROM installed_apps WHERE upload_id = 'test-id';"
# Should show: 340

# Clean up test data
psql $DATABASE_URL -c "DELETE FROM app_extractions WHERE upload_id = 'test-id';"
```

## Next Upload

The system is now ready! When you upload the UFDR file again:

1. Worker will download from MinIO
2. Extract report.xml
3. Parse all 340 apps correctly
4. Store in database with install timestamps

The previous upload with ID `a97b3667-6e45-4706-9aee-39c478d898a4` failed because of this namespace issue. Just upload again and it will work now! 🚀
