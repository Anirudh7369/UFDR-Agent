# UFDR Database Schema Setup Guide

This guide will help you set up all the UFDR extraction database schemas on any laptop.

## Prerequisites

1. PostgreSQL installed and running
2. Database credentials:
   - Database: `ufdr_agent`
   - User: `ufdr_team`
   - Password: `strongSIHpassword`
   - Host: `localhost`
   - Port: `5432`

## Schema Files

The following schema files are available in `realtime/utils/db/`:

1. `apps_schema.sql` - Installed applications
2. `call_logs_schema.sql` - Call history from all apps
3. `messages_schema.sql` - SMS, WhatsApp, and instant messages
4. `locations_schema.sql` - GPS location data
5. `browsing_schema.sql` - Browser history, searches, and bookmarks

## Setup Methods

### Method 1: Single Combined Command (Recommended)

Navigate to the `realtime/utils/db` directory and run:

```bash
cd realtime/utils/db
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f init_all_schemas.sql
```

### Method 2: Individual Schema Files

If you want to initialize schemas one by one:

```bash
cd realtime/utils/db

# Initialize Apps schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f apps_schema.sql

# Initialize Call Logs schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f call_logs_schema.sql

# Initialize Messages schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f messages_schema.sql

# Initialize Locations schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f locations_schema.sql

# Initialize Browsing schema
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f browsing_schema.sql
```

### Method 3: From Project Root (Any Directory)

If you want to run from the project root directory:

```bash
# Get the absolute path to your project
PROJECT_PATH=$(pwd)

# Run all schemas
cd ${PROJECT_PATH}/realtime/utils/db && \
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent -f init_all_schemas.sql
```

## What Gets Created

After running the schemas, you will have the following tables:

### Apps Extraction
- `app_extractions` - Tracking table for app extraction jobs
- `installed_apps` - All installed applications data

### Call Logs
- `call_log_extractions` - Tracking table for call log extraction jobs
- `call_logs` - Unified call history from all apps

### Messages
- `message_extractions` - Tracking table for message extraction jobs
- `instant_messages` - Unified messages from all messaging apps

### Locations
- `location_extractions` - Tracking table for location extraction jobs
- `locations` - GPS coordinates and location data

### Browsing History
- `browsing_extractions` - Tracking table for browsing extraction jobs
- `browsing_history` - Unified browser history, searches, and bookmarks
- Views: `visited_pages_view`, `search_history_view`, `bookmarks_view`

## Verification

To verify all tables were created successfully:

```sql
-- Connect to database
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent

-- List all tables
\dt

-- Check specific schema tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Exit
\q
```

## Troubleshooting

### Error: Database does not exist

Create the database first:
```bash
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/postgres -c "CREATE DATABASE ufdr_agent;"
```

### Error: Role does not exist

Create the user first:
```bash
psql postgresql://postgres@localhost:5432/postgres -c "CREATE USER ufdr_team WITH PASSWORD 'strongSIHpassword';"
psql postgresql://postgres@localhost:5432/postgres -c "GRANT ALL PRIVILEGES ON DATABASE ufdr_agent TO ufdr_team;"
```

### Error: Permission denied

Grant necessary privileges:
```bash
psql postgresql://postgres@localhost:5432/ufdr_agent -c "GRANT ALL ON SCHEMA public TO ufdr_team;"
psql postgresql://postgres@localhost:5432/ufdr_agent -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ufdr_team;"
```

## Drop All Tables (Clean Slate)

If you need to drop all tables and start fresh:

```sql
-- Connect to database
psql postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent

-- Drop all UFDR tables (keeps feedback table)
DROP TABLE IF EXISTS browsing_history CASCADE;
DROP TABLE IF EXISTS browsing_extractions CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS location_extractions CASCADE;
DROP TABLE IF EXISTS instant_messages CASCADE;
DROP TABLE IF EXISTS message_extractions CASCADE;
DROP TABLE IF EXISTS call_logs CASCADE;
DROP TABLE IF EXISTS call_log_extractions CASCADE;
DROP TABLE IF EXISTS installed_apps CASCADE;
DROP TABLE IF EXISTS app_extractions CASCADE;

-- Drop views
DROP VIEW IF EXISTS visited_pages_view CASCADE;
DROP VIEW IF EXISTS search_history_view CASCADE;
DROP VIEW IF EXISTS bookmarks_view CASCADE;

\q
```

Then re-run the schema initialization.

## Quick Setup Script

Save this as `setup_db.sh` for quick setup:

```bash
#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}UFDR Database Schema Setup${NC}"
echo "======================================"

# Database connection string
DB_URL="postgresql://ufdr_team:strongSIHpassword@localhost:5432/ufdr_agent"

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo -e "${RED}Error: PostgreSQL is not running${NC}"
    exit 1
fi

# Navigate to schema directory
cd realtime/utils/db || exit 1

# Initialize all schemas
echo -e "${YELLOW}Initializing schemas...${NC}"
if psql "$DB_URL" -f init_all_schemas.sql; then
    echo -e "${GREEN}✓ All schemas initialized successfully!${NC}"
else
    echo -e "${RED}✗ Schema initialization failed${NC}"
    exit 1
fi

# Verify tables
echo -e "${YELLOW}Verifying tables...${NC}"
TABLE_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")

echo -e "${GREEN}✓ Created $TABLE_COUNT tables${NC}"
echo "======================================"
echo -e "${GREEN}Setup complete!${NC}"
