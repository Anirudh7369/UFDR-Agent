# UFDR Extraction Status API

## Endpoint

`GET /api/uploads/{upload_id}/extraction-status`

## Description

This endpoint returns the extraction status for all UFDR data types (apps, call logs, messages, locations, browsing history). The frontend can poll this endpoint to know when all extractions are complete.

## Usage

### Request

```bash
GET /api/uploads/{upload_id}/extraction-status
```

**Parameters:**
- `upload_id` (path parameter): The unique identifier for the upload

### Response

**When extraction is in progress:**
```json
{
  "status": "processing",
  "upload_id": "abc123-def456-ghi789",
  "extractions": {
    "apps": {
      "status": "completed",
      "extracted": true
    },
    "call_logs": {
      "status": "completed",
      "extracted": true
    },
    "messages": {
      "status": "processing",
      "extracted": false
    },
    "locations": {
      "status": "processing",
      "extracted": false
    },
    "browsing": {
      "status": "processing",
      "extracted": false
    }
  },
  "overall_status": "processing",
  "message": "Extraction in progress"
}
```

**When all extractions are complete:**
```json
{
  "status": "completed",
  "upload_id": "abc123-def456-ghi789",
  "extractions": {
    "apps": {
      "status": "completed",
      "extracted": true
    },
    "call_logs": {
      "status": "completed",
      "extracted": true
    },
    "messages": {
      "status": "completed",
      "extracted": true
    },
    "locations": {
      "status": "completed",
      "extracted": true
    },
    "browsing": {
      "status": "completed",
      "extracted": true
    }
  },
  "overall_status": "completed",
  "message": "All extractions completed successfully"
}
```

**When extraction fails:**
```json
{
  "status": "failed",
  "upload_id": "abc123-def456-ghi789",
  "extractions": {
    "apps": {
      "status": "completed",
      "extracted": true
    },
    "call_logs": {
      "status": "completed",
      "extracted": true
    },
    "messages": {
      "status": "processing",
      "extracted": false
    },
    "locations": {
      "status": "processing",
      "extracted": false
    },
    "browsing": {
      "status": "processing",
      "extracted": false
    }
  },
  "overall_status": "failed",
  "message": "Some extractions failed",
  "errors": {
    "messages": "Database connection error",
    "locations": "Parsing error in report.xml"
  }
}
```

## Frontend Polling Example

```javascript
// Poll extraction status every 2 seconds
async function pollExtractionStatus(uploadId) {
  const checkStatus = async () => {
    try {
      const response = await fetch(`/api/uploads/${uploadId}/extraction-status`);
      const data = await response.json();

      console.log('Extraction status:', data);

      if (data.overall_status === 'completed') {
        console.log('All extractions completed!');
        // Stop polling and notify user
        return true;
      } else if (data.overall_status === 'failed') {
        console.error('Extraction failed:', data.errors);
        // Stop polling and show error to user
        return true;
      }

      // Continue polling
      return false;
    } catch (error) {
      console.error('Error checking extraction status:', error);
      return false;
    }
  };

  // Poll every 2 seconds
  const intervalId = setInterval(async () => {
    const done = await checkStatus();
    if (done) {
      clearInterval(intervalId);
    }
  }, 2000);

  // Check immediately on first call
  await checkStatus();
}

// Usage
pollExtractionStatus('abc123-def456-ghi789');
```

## Status Values

### Overall Status
- `completed`: All extractions finished successfully
- `processing`: One or more extractions still in progress
- `failed`: One or more extractions failed
- `not_started`: Upload found but extraction hasn't started yet

### Individual Extraction Status
- `completed`: This specific extraction finished successfully
- `processing`: This specific extraction is still in progress

## Redis Keys

The endpoint reads from Redis key: `ingest_progress:{upload_id}`

The worker sets these flags in Redis:
- `apps_extracted=true` - Apps extraction complete
- `call_logs_extracted=true` - Call logs extraction complete
- `messages_extracted=true` - Messages extraction complete
- `locations_extracted=true` - Locations extraction complete
- `browsing_extracted=true` - Browsing history extraction complete
- `status=done` - Overall extraction process complete

## Error Handling

If the upload is not found or extraction status is unavailable, the endpoint returns:

```json
HTTP 404 Not Found
{
  "detail": "Upload not found or extraction status unavailable"
}
```

## Architecture

1. **Primary source**: Redis (`ingest_progress:{upload_id}`)
   - Real-time status updated by worker during extraction
   - Fast access for polling

2. **Fallback source**: `realtime/data/uploads.json`
   - Used if Redis is unavailable
   - Basic status information only

## Data Extraction Summary

Based on current implementation, the following data types are extracted:

1. **Apps**: Installed applications (340 apps extracted in test run)
2. **Call Logs**: Phone call history (56 calls from 9 apps in test run)
3. **Messages**: SMS, WhatsApp, and other instant messages (340 messages from 14 apps in test run)
4. **Locations**: GPS coordinates from Google Fit, Maps, Photos, etc. (70 locations in test run)
5. **Browsing History**: Visited pages, searches, and bookmarks from all browsers (1636 entries in test run)

All data is stored in PostgreSQL with unified schemas for easy querying.
