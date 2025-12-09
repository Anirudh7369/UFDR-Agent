-- Schema for storing instant messages from all apps extracted from UFDR files
-- Unified messages from WhatsApp, Telegram, Facebook Messenger, Instagram, Twitter, SMS, etc.
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- Drop existing tables if they exist
DROP TABLE IF EXISTS message_attachments CASCADE;
DROP TABLE IF EXISTS message_parties CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS message_extractions CASCADE;

-- Table to track message extraction jobs
CREATE TABLE message_extractions (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL UNIQUE,
    ufdr_filename VARCHAR(500),
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    total_messages INTEGER DEFAULT 0,
    processed_messages INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main table for all instant messages (unified across all apps)
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- Message identification
    message_id VARCHAR(500), -- Unique message ID if available
    source_app VARCHAR(200), -- App that sent the message (WhatsApp, Telegram, Facebook Messenger, SMS, etc.)

    -- Message content
    body TEXT, -- Message text content
    message_type VARCHAR(100), -- AppMessage, SMS, etc.
    platform VARCHAR(50), -- Mobile, Desktop

    -- Timestamps
    message_timestamp BIGINT, -- Milliseconds since epoch
    message_timestamp_dt TIMESTAMP, -- Converted datetime for easy querying

    -- Sender (From party)
    from_party_identifier VARCHAR(500), -- User ID, phone number
    from_party_name VARCHAR(500),
    from_party_is_owner BOOLEAN DEFAULT FALSE,

    -- Recipient (primary To party for 1-on-1 chats)
    to_party_identifier VARCHAR(500), -- User ID, phone number
    to_party_name VARCHAR(500),
    to_party_is_owner BOOLEAN DEFAULT FALSE,

    -- Message properties
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,

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
    FOREIGN KEY (upload_id) REFERENCES message_extractions(upload_id) ON DELETE CASCADE
);

-- Table for all parties involved in messages (supports group chats)
CREATE TABLE message_parties (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    upload_id VARCHAR(255) NOT NULL,

    -- Party details
    party_identifier VARCHAR(500), -- User ID, phone number, email
    party_name VARCHAR(500),
    party_role VARCHAR(50), -- From, To
    is_phone_owner BOOLEAN DEFAULT FALSE,

    -- Metadata
    raw_json JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES message_extractions(upload_id) ON DELETE CASCADE
);

-- Table for message attachments
CREATE TABLE message_attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    upload_id VARCHAR(255) NOT NULL,

    -- Attachment details
    attachment_type VARCHAR(100), -- Image, Video, Audio, Document, etc.
    filename VARCHAR(1000),
    file_path VARCHAR(2000),
    file_size BIGINT,
    mime_type VARCHAR(200),

    -- Metadata
    raw_json JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES message_extractions(upload_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_messages_upload_id ON messages(upload_id);
CREATE INDEX idx_messages_source_app ON messages(source_app);
CREATE INDEX idx_messages_message_type ON messages(message_type);
CREATE INDEX idx_messages_timestamp ON messages(message_timestamp);
CREATE INDEX idx_messages_timestamp_dt ON messages(message_timestamp_dt);
CREATE INDEX idx_messages_from_party ON messages(from_party_identifier);
CREATE INDEX idx_messages_to_party ON messages(to_party_identifier);
CREATE INDEX idx_messages_has_attachments ON messages(has_attachments);
CREATE INDEX idx_messages_body_text ON messages USING GIN (to_tsvector('english', body));

CREATE INDEX idx_message_parties_message_id ON message_parties(message_id);
CREATE INDEX idx_message_parties_upload_id ON message_parties(upload_id);
CREATE INDEX idx_message_parties_identifier ON message_parties(party_identifier);

CREATE INDEX idx_message_attachments_message_id ON message_attachments(message_id);
CREATE INDEX idx_message_attachments_upload_id ON message_attachments(upload_id);
CREATE INDEX idx_message_attachments_type ON message_attachments(attachment_type);

-- View for easy querying
CREATE OR REPLACE VIEW messages_view AS
SELECT
    m.id,
    m.upload_id,
    m.source_app,
    m.message_type,
    m.platform,
    m.message_timestamp_dt,
    m.body,
    m.from_party_name,
    m.from_party_identifier,
    m.to_party_name,
    m.to_party_identifier,
    m.has_attachments,
    m.attachment_count,
    e.ufdr_filename,
    e.extraction_status
FROM messages m
LEFT JOIN message_extractions e ON m.upload_id = e.upload_id;

-- Comments for documentation
COMMENT ON TABLE message_extractions IS 'Tracks message extraction jobs from UFDR files';
COMMENT ON TABLE messages IS 'Unified instant messages from all apps (WhatsApp, Telegram, Facebook Messenger, SMS, etc.)';
COMMENT ON TABLE message_parties IS 'All parties involved in each message (supports group chats)';
COMMENT ON TABLE message_attachments IS 'File attachments for messages (images, videos, documents, etc.)';

COMMENT ON COLUMN messages.source_app IS 'App that sent the message (WhatsApp, Telegram, Facebook Messenger, Instagram, Twitter, SMS, etc.)';
COMMENT ON COLUMN messages.body IS 'Message text content';
COMMENT ON COLUMN messages.message_type IS 'AppMessage, SMS, MMS, etc.';
COMMENT ON COLUMN messages.message_timestamp IS 'Message time in milliseconds since epoch';
COMMENT ON COLUMN messages.has_attachments IS 'TRUE if message has file attachments';
COMMENT ON COLUMN messages.raw_xml IS 'Original XML from UFDR report.xml';
COMMENT ON COLUMN messages.raw_json IS 'Complete parsed data as JSON';
