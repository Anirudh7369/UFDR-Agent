-- WhatsApp Data Extraction Schema
-- This schema stores WhatsApp messages and related data extracted from UFDR files

-- Table to track UFDR extraction jobs
CREATE TABLE IF NOT EXISTS ufdr_extractions (
    id SERIAL PRIMARY KEY,
    upload_id TEXT UNIQUE NOT NULL,
    ufdr_filename TEXT NOT NULL,
    extraction_status TEXT NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    total_messages INTEGER DEFAULT 0,
    processed_messages INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB
);

-- WhatsApp JID (Jabber ID) lookup table
CREATE TABLE IF NOT EXISTS whatsapp_jids (
    id SERIAL PRIMARY KEY,
    upload_id TEXT NOT NULL,
    raw_string TEXT NOT NULL,
    user_part TEXT,
    server_part TEXT,
    jid_type INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(upload_id, raw_string)
);

-- WhatsApp Chats table
CREATE TABLE IF NOT EXISTS whatsapp_chats (
    id SERIAL PRIMARY KEY,
    upload_id TEXT NOT NULL,
    chat_jid_id INTEGER REFERENCES whatsapp_jids(id),
    chat_jid TEXT NOT NULL,
    subject TEXT,
    created_timestamp BIGINT,
    archived INTEGER DEFAULT 0,
    hidden INTEGER DEFAULT 0,
    last_message_timestamp BIGINT,
    unseen_message_count INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(upload_id, chat_jid)
);

-- Main WhatsApp messages table
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id SERIAL PRIMARY KEY,
    upload_id TEXT NOT NULL,
    msg_id TEXT NOT NULL,
    chat_jid TEXT NOT NULL,
    chat_id INTEGER REFERENCES whatsapp_chats(id),

    -- Sender information
    sender_jid TEXT,
    sender_jid_id INTEGER REFERENCES whatsapp_jids(id),
    from_me INTEGER DEFAULT 0,

    -- Message content
    message_text TEXT,
    message_type INTEGER,

    -- Timestamps (WhatsApp uses milliseconds since epoch)
    timestamp BIGINT,
    timestamp_dt TIMESTAMP WITH TIME ZONE,
    received_timestamp BIGINT,
    send_timestamp BIGINT,

    -- Message status
    status INTEGER,
    starred INTEGER DEFAULT 0,

    -- Media information
    media_url TEXT,
    media_path TEXT,
    media_mimetype TEXT,
    media_size BIGINT,
    media_name TEXT,
    media_caption TEXT,
    media_hash TEXT,
    media_duration BIGINT,
    media_wa_type TEXT,

    -- Location data
    latitude REAL,
    longitude REAL,

    -- Message metadata
    quoted_row_id INTEGER,
    forwarded INTEGER DEFAULT 0,
    mentioned_jids TEXT,

    -- Raw data for complete forensic analysis
    raw_json JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(upload_id, msg_id, chat_jid)
);

-- WhatsApp contacts/participants
CREATE TABLE IF NOT EXISTS whatsapp_contacts (
    id SERIAL PRIMARY KEY,
    upload_id TEXT NOT NULL,
    jid TEXT NOT NULL,
    jid_id INTEGER REFERENCES whatsapp_jids(id),
    display_name TEXT,
    phone_number TEXT,
    is_business INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(upload_id, jid)
);

-- WhatsApp call logs
CREATE TABLE IF NOT EXISTS whatsapp_call_logs (
    id SERIAL PRIMARY KEY,
    upload_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    from_jid TEXT,
    to_jid TEXT,
    from_me INTEGER DEFAULT 0,
    call_type TEXT, -- voice, video
    timestamp BIGINT,
    timestamp_dt TIMESTAMP WITH TIME ZONE,
    duration BIGINT,
    status TEXT,
    call_result INTEGER,
    bytes_transferred BIGINT,
    is_group_call INTEGER DEFAULT 0,
    raw_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(upload_id, call_id)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_upload_id ON whatsapp_messages(upload_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_chat_jid ON whatsapp_messages(chat_jid);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_timestamp ON whatsapp_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_from_me ON whatsapp_messages(from_me);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_sender_jid ON whatsapp_messages(sender_jid);
CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_message_type ON whatsapp_messages(message_type);

CREATE INDEX IF NOT EXISTS idx_whatsapp_chats_upload_id ON whatsapp_chats(upload_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_chats_chat_jid ON whatsapp_chats(chat_jid);

CREATE INDEX IF NOT EXISTS idx_whatsapp_jids_upload_id ON whatsapp_jids(upload_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_jids_raw_string ON whatsapp_jids(raw_string);

CREATE INDEX IF NOT EXISTS idx_whatsapp_contacts_upload_id ON whatsapp_contacts(upload_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_contacts_jid ON whatsapp_contacts(jid);

CREATE INDEX IF NOT EXISTS idx_ufdr_extractions_upload_id ON ufdr_extractions(upload_id);
CREATE INDEX IF NOT EXISTS idx_ufdr_extractions_status ON ufdr_extractions(extraction_status);

CREATE INDEX IF NOT EXISTS idx_whatsapp_call_logs_upload_id ON whatsapp_call_logs(upload_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_call_logs_timestamp ON whatsapp_call_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_whatsapp_call_logs_call_type ON whatsapp_call_logs(call_type);
CREATE INDEX IF NOT EXISTS idx_whatsapp_call_logs_status ON whatsapp_call_logs(status);

-- Create a view for easy querying of messages with sender names
CREATE OR REPLACE VIEW whatsapp_messages_view AS
SELECT
    m.id,
    m.upload_id,
    m.msg_id,
    m.chat_jid,
    m.sender_jid,
    m.from_me,
    m.message_text,
    m.message_type,
    m.timestamp,
    m.timestamp_dt,
    m.media_path,
    m.media_mimetype,
    m.media_caption,
    m.latitude,
    m.longitude,
    m.starred,
    c.subject as chat_subject,
    sender_contact.display_name as sender_name,
    sender_contact.phone_number as sender_number,
    m.raw_json,
    m.created_at
FROM whatsapp_messages m
LEFT JOIN whatsapp_chats c ON m.chat_id = c.id
LEFT JOIN whatsapp_contacts sender_contact ON m.sender_jid = sender_contact.jid AND m.upload_id = sender_contact.upload_id;
