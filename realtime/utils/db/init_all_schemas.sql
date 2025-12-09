-- Initialize all UFDR extraction schemas
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- This file combines all schema files for easy initialization
-- Run from the realtime/utils/db directory

\echo 'Initializing Apps Schema...'
\i apps_schema.sql

\echo 'Initializing Call Logs Schema...'
\i call_logs_schema.sql

\echo 'Initializing Messages Schema...'
\i messages_schema.sql

\echo 'Initializing Locations Schema...'
\i locations_schema.sql

\echo 'Initializing Browsing Schema...'
\i browsing_schema.sql

\echo 'Initializing Contacts Schema...'
\i contacts_schema.sql

\echo 'All schemas initialized successfully!'
