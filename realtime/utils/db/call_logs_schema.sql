-- Schema for storing call logs from all apps extracted from UFDR files
-- Unified call logs from Phone, WhatsApp, Telegram, Skype, Viber, etc.
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- Drop existing tables if they exist
DROP TABLE IF EXISTS call_log_parties CASCADE;
DROP TABLE IF EXISTS call_logs CASCADE;
DROP TABLE IF EXISTS call_log_extractions CASCADE;

-- Table to track call log extraction jobs
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

-- Main table for all call logs (unified across all apps)
CREATE TABLE call_logs (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- Call identification
    call_id VARCHAR(500), -- Unique call ID if available
    source_app VARCHAR(200), -- App that made the call (WhatsApp, Telegram, Phone, etc.)

    -- Call details
    direction VARCHAR(50), -- Incoming, Outgoing
    call_type VARCHAR(50), -- Voice, Video, Incoming, Outgoing
    status VARCHAR(100), -- Established, Missed, Rejected, Cancelled, etc.

    -- Timestamps
    call_timestamp BIGINT, -- Milliseconds since epoch
    call_timestamp_dt TIMESTAMP, -- Converted datetime for easy querying

    -- Duration
    duration_seconds INTEGER, -- Duration in seconds
    duration_string VARCHAR(50), -- Original duration string (00:01:17)

    -- Network/Account info
    country_code VARCHAR(10),
    network_code VARCHAR(50),
    network_name VARCHAR(200),
    account VARCHAR(500), -- Account ID used for the call

    -- Call properties
    is_video_call BOOLEAN DEFAULT FALSE,

    -- Parties (simplified - main party info)
    from_party_identifier VARCHAR(500), -- Phone number or user ID
    from_party_name VARCHAR(500),
    from_party_is_owner BOOLEAN DEFAULT FALSE,

    to_party_identifier VARCHAR(500), -- Phone number or user ID
    to_party_name VARCHAR(500),
    to_party_is_owner BOOLEAN DEFAULT FALSE,

    -- Metadata
    deleted_state VARCHAR(50), -- Intact, Deleted
    decoding_confidence VARCHAR(50), -- High, Medium, Low

    -- Complete raw data for forensic purposes
    raw_xml TEXT, -- Original XML snippet
    raw_json JSONB, -- Parsed JSON representation

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    FOREIGN KEY (upload_id) REFERENCES call_log_extractions(upload_id) ON DELETE CASCADE
);

-- Separate table for all parties involved in calls (for group calls, conference calls)
CREATE TABLE call_log_parties (
    id SERIAL PRIMARY KEY,
    call_log_id INTEGER NOT NULL,
    upload_id VARCHAR(255) NOT NULL,

    -- Party details
    party_identifier VARCHAR(500), -- Phone number, user ID, email, etc.
    party_name VARCHAR(500),
    party_role VARCHAR(50), -- From, To
    is_phone_owner BOOLEAN DEFAULT FALSE,

    -- Metadata
    raw_json JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (call_log_id) REFERENCES call_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES call_log_extractions(upload_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_call_logs_upload_id ON call_logs(upload_id);
CREATE INDEX idx_call_logs_source_app ON call_logs(source_app);
CREATE INDEX idx_call_logs_direction ON call_logs(direction);
CREATE INDEX idx_call_logs_status ON call_logs(status);
CREATE INDEX idx_call_logs_timestamp ON call_logs(call_timestamp);
CREATE INDEX idx_call_logs_timestamp_dt ON call_logs(call_timestamp_dt);
CREATE INDEX idx_call_logs_from_party ON call_logs(from_party_identifier);
CREATE INDEX idx_call_logs_to_party ON call_logs(to_party_identifier);
CREATE INDEX idx_call_logs_is_video ON call_logs(is_video_call);

CREATE INDEX idx_call_log_parties_call_log_id ON call_log_parties(call_log_id);
CREATE INDEX idx_call_log_parties_upload_id ON call_log_parties(upload_id);
CREATE INDEX idx_call_log_parties_identifier ON call_log_parties(party_identifier);

-- View for easy querying
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

-- Comments for documentation
COMMENT ON TABLE call_log_extractions IS 'Tracks call log extraction jobs from UFDR files';
COMMENT ON TABLE call_logs IS 'Unified call logs from all apps (Phone, WhatsApp, Telegram, Skype, etc.)';
COMMENT ON TABLE call_log_parties IS 'All parties involved in each call (supports group/conference calls)';

COMMENT ON COLUMN call_logs.source_app IS 'App that made the call (WhatsApp, Telegram, Phone, Skype, Viber, etc.)';
COMMENT ON COLUMN call_logs.direction IS 'Incoming or Outgoing';
COMMENT ON COLUMN call_logs.call_type IS 'Voice, Video, or call direction type';
COMMENT ON COLUMN call_logs.status IS 'Established, Missed, Rejected, Cancelled, etc.';
COMMENT ON COLUMN call_logs.call_timestamp IS 'Call time in milliseconds since epoch';
COMMENT ON COLUMN call_logs.is_video_call IS 'TRUE if video call, FALSE if voice call';
COMMENT ON COLUMN call_logs.raw_xml IS 'Original XML from UFDR report.xml';
COMMENT ON COLUMN call_logs.raw_json IS 'Complete parsed data as JSON';
