-- Schema for storing contacts from all sources
-- Unified data from WhatsApp, Facebook Messenger, Kik, Skype, Viber, Phone Book, etc.
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- Drop existing tables if they exist
DROP TABLE IF EXISTS contact_entries CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;
DROP TABLE IF EXISTS contact_extractions CASCADE;

-- Table to track contact extraction jobs
CREATE TABLE contact_extractions (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL UNIQUE,
    ufdr_filename VARCHAR(500),
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    total_contacts INTEGER DEFAULT 0,
    processed_contacts INTEGER DEFAULT 0,
    total_entries INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main table for contacts
CREATE TABLE contacts (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- Contact identification
    contact_id VARCHAR(500), -- Unique contact ID from UFDR
    source_app VARCHAR(200), -- WhatsApp, Facebook Messenger, Kik, Skype, Viber, Phone Book, etc.
    service_identifier VARCHAR(500), -- Service-specific identifier

    -- Basic information
    name TEXT, -- Contact name
    account VARCHAR(500), -- Account associated with this contact

    -- Contact type and group
    contact_type VARCHAR(100), -- PhoneBook, ChatParticipant, etc.
    contact_group VARCHAR(200), -- Contact group if any

    -- Timestamps
    time_created BIGINT, -- Milliseconds since epoch
    time_created_dt TIMESTAMP, -- Converted datetime

    -- Additional metadata
    notes TEXT, -- Notes about the contact
    interaction_statuses TEXT[], -- Array of interaction status types
    user_tags TEXT[], -- Array of user tags

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
    FOREIGN KEY (upload_id) REFERENCES contact_extractions(upload_id) ON DELETE CASCADE
);

-- Table for contact entries (phone numbers, emails, user IDs, etc.)
CREATE TABLE contact_entries (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL, -- References contacts(id)
    upload_id VARCHAR(255) NOT NULL,

    -- Entry identification
    entry_id VARCHAR(500), -- Unique entry ID from UFDR
    entry_type VARCHAR(50), -- PhoneNumber, EmailAddress, UserID, ProfilePicture, InstantMessaging, etc.

    -- Entry details
    category VARCHAR(200), -- Mobile, Email, Facebook Id, Username, etc.
    value TEXT, -- The actual phone number, email, user ID, URL, etc.
    domain VARCHAR(100), -- Phone, Email, User ID, Profile Picture, etc.

    -- Metadata
    deleted_state VARCHAR(50),
    decoding_confidence VARCHAR(50),

    -- Raw data
    raw_xml TEXT,
    raw_json JSONB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES contact_extractions(upload_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_contacts_upload_id ON contacts(upload_id);
CREATE INDEX idx_contacts_source_app ON contacts(source_app);
CREATE INDEX idx_contacts_name ON contacts USING GIN (to_tsvector('english', name));
CREATE INDEX idx_contacts_contact_type ON contacts(contact_type);
CREATE INDEX idx_contacts_account ON contacts(account);

CREATE INDEX idx_contact_entries_contact_id ON contact_entries(contact_id);
CREATE INDEX idx_contact_entries_upload_id ON contact_entries(upload_id);
CREATE INDEX idx_contact_entries_entry_type ON contact_entries(entry_type);
CREATE INDEX idx_contact_entries_category ON contact_entries(category);
CREATE INDEX idx_contact_entries_value ON contact_entries USING GIN (to_tsvector('english', value));

-- View for phone contacts with phone numbers
CREATE OR REPLACE VIEW phone_contacts_view AS
SELECT
    c.id,
    c.upload_id,
    c.name,
    c.source_app,
    c.contact_type,
    c.account,
    ce.value as phone_number,
    ce.category as phone_type,
    c.time_created_dt,
    e.ufdr_filename,
    e.extraction_status
FROM contacts c
INNER JOIN contact_entries ce ON c.id = ce.contact_id
LEFT JOIN contact_extractions e ON c.upload_id = e.upload_id
WHERE ce.entry_type = 'PhoneNumber';

-- View for email contacts
CREATE OR REPLACE VIEW email_contacts_view AS
SELECT
    c.id,
    c.upload_id,
    c.name,
    c.source_app,
    c.contact_type,
    c.account,
    ce.value as email_address,
    ce.category as email_type,
    c.time_created_dt,
    e.ufdr_filename,
    e.extraction_status
FROM contacts c
INNER JOIN contact_entries ce ON c.id = ce.contact_id
LEFT JOIN contact_extractions e ON c.upload_id = e.upload_id
WHERE ce.entry_type = 'EmailAddress';

-- View for social media contacts
CREATE OR REPLACE VIEW social_contacts_view AS
SELECT
    c.id,
    c.upload_id,
    c.name,
    c.source_app,
    c.contact_type,
    c.account,
    ce.value as user_id,
    ce.category as id_type,
    c.time_created_dt,
    e.ufdr_filename,
    e.extraction_status
FROM contacts c
INNER JOIN contact_entries ce ON c.id = ce.contact_id
LEFT JOIN contact_extractions e ON c.upload_id = e.upload_id
WHERE ce.entry_type = 'UserID';

-- Comments for documentation
COMMENT ON TABLE contact_extractions IS 'Tracks contact extraction jobs from UFDR files';
COMMENT ON TABLE contacts IS 'Unified contacts from all messaging apps and phone book';
COMMENT ON TABLE contact_entries IS 'Contact entries: phone numbers, emails, user IDs, profile pictures, etc.';

COMMENT ON COLUMN contacts.source_app IS 'Source app: WhatsApp, Facebook Messenger, Kik, Skype, Viber, Phone Book, etc.';
COMMENT ON COLUMN contacts.contact_type IS 'Type: PhoneBook, ChatParticipant, etc.';
COMMENT ON COLUMN contact_entries.entry_type IS 'Type: PhoneNumber, EmailAddress, UserID, ProfilePicture, InstantMessaging, etc.';
COMMENT ON COLUMN contact_entries.category IS 'Category: Mobile, Email, Facebook Id, Username, Profile Picture size, etc.';
COMMENT ON COLUMN contact_entries.value IS 'The actual value: phone number, email address, user ID, profile picture URL, etc.';
COMMENT ON COLUMN contact_entries.domain IS 'Domain: Phone, Email, User ID, Profile Picture, etc.';
