-- Schema for storing installed applications extracted from UFDR files
-- Based on Cellebrite InstalledApplication model type
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS installed_app_permissions CASCADE;
DROP TABLE IF EXISTS installed_app_categories CASCADE;
DROP TABLE IF EXISTS installed_apps CASCADE;
DROP TABLE IF EXISTS app_extractions CASCADE;

-- Table to track app extraction jobs
CREATE TABLE app_extractions (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL UNIQUE,
    ufdr_filename VARCHAR(500),
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    total_apps INTEGER DEFAULT 0,
    processed_apps INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main table for installed applications
CREATE TABLE installed_apps (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- Core app identification
    app_identifier VARCHAR(500) NOT NULL, -- Package name (e.g., com.skype.raider)
    app_name VARCHAR(1000), -- Display name (e.g., "Skype - free IM & video calls")
    app_version VARCHAR(200), -- Version string (e.g., "8.61.0.96")
    app_guid VARCHAR(500), -- App GUID if available

    -- Timestamps (BIGINT to store milliseconds since epoch)
    install_timestamp BIGINT, -- PurchaseDate from UFDR
    install_timestamp_dt TIMESTAMP, -- Converted datetime for easy querying
    last_launched_timestamp BIGINT, -- LastLaunched timestamp
    last_launched_dt TIMESTAMP, -- Converted datetime

    -- App metadata
    decoding_status VARCHAR(50), -- Decoded, NotDecoded, etc.
    is_emulatable BOOLEAN DEFAULT FALSE,
    operation_mode VARCHAR(50), -- Foreground, Background
    deleted_state VARCHAR(50), -- Intact, Deleted
    decoding_confidence VARCHAR(50), -- High, Medium, Low

    -- Array fields stored as JSON arrays
    permissions JSONB, -- Array of permission categories
    categories JSONB, -- Array of app categories
    associated_directory_paths JSONB, -- Array of file system paths

    -- Complete raw data for forensic purposes
    raw_xml TEXT, -- Original XML snippet
    raw_json JSONB, -- Parsed JSON representation

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(upload_id, app_identifier),
    FOREIGN KEY (upload_id) REFERENCES app_extractions(upload_id) ON DELETE CASCADE
);

-- Separate table for permissions (normalized for easier querying)
CREATE TABLE installed_app_permissions (
    id SERIAL PRIMARY KEY,
    app_id INTEGER NOT NULL,
    upload_id VARCHAR(255) NOT NULL,
    app_identifier VARCHAR(500) NOT NULL,
    permission_category VARCHAR(100) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (app_id) REFERENCES installed_apps(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES app_extractions(upload_id) ON DELETE CASCADE
);

-- Separate table for categories (normalized for easier querying)
CREATE TABLE installed_app_categories (
    id SERIAL PRIMARY KEY,
    app_id INTEGER NOT NULL,
    upload_id VARCHAR(255) NOT NULL,
    app_identifier VARCHAR(500) NOT NULL,
    category VARCHAR(100) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (app_id) REFERENCES installed_apps(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES app_extractions(upload_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_installed_apps_upload_id ON installed_apps(upload_id);
CREATE INDEX idx_installed_apps_identifier ON installed_apps(app_identifier);
CREATE INDEX idx_installed_apps_name ON installed_apps(app_name);
CREATE INDEX idx_installed_apps_install_timestamp ON installed_apps(install_timestamp);
CREATE INDEX idx_installed_apps_install_timestamp_dt ON installed_apps(install_timestamp_dt);
CREATE INDEX idx_installed_apps_last_launched ON installed_apps(last_launched_timestamp);
CREATE INDEX idx_installed_apps_categories ON installed_apps USING GIN(categories);
CREATE INDEX idx_installed_apps_permissions ON installed_apps USING GIN(permissions);

CREATE INDEX idx_app_permissions_upload_id ON installed_app_permissions(upload_id);
CREATE INDEX idx_app_permissions_app_id ON installed_app_permissions(app_id);
CREATE INDEX idx_app_permissions_category ON installed_app_permissions(permission_category);

CREATE INDEX idx_app_categories_upload_id ON installed_app_categories(upload_id);
CREATE INDEX idx_app_categories_app_id ON installed_app_categories(app_id);
CREATE INDEX idx_app_categories_category ON installed_app_categories(category);

-- View for easy querying
CREATE OR REPLACE VIEW installed_apps_view AS
SELECT
    a.id,
    a.upload_id,
    a.app_identifier,
    a.app_name,
    a.app_version,
    a.install_timestamp,
    a.install_timestamp_dt,
    a.last_launched_timestamp,
    a.last_launched_dt,
    a.decoding_status,
    a.operation_mode,
    a.deleted_state,
    a.permissions,
    a.categories,
    a.associated_directory_paths,
    e.ufdr_filename,
    e.extraction_status
FROM installed_apps a
LEFT JOIN app_extractions e ON a.upload_id = e.upload_id;

-- Comments for documentation
COMMENT ON TABLE app_extractions IS 'Tracks app extraction jobs from UFDR files';
COMMENT ON TABLE installed_apps IS 'Stores installed applications extracted from Android UFDR files';
COMMENT ON TABLE installed_app_permissions IS 'Normalized permission data for apps';
COMMENT ON TABLE installed_app_categories IS 'Normalized category data for apps';

COMMENT ON COLUMN installed_apps.app_identifier IS 'Android package name (e.g., com.whatsapp)';
COMMENT ON COLUMN installed_apps.app_name IS 'User-visible app name';
COMMENT ON COLUMN installed_apps.install_timestamp IS 'Install time in milliseconds since epoch';
COMMENT ON COLUMN installed_apps.install_timestamp_dt IS 'Install time as PostgreSQL timestamp';
COMMENT ON COLUMN installed_apps.permissions IS 'JSON array of permission categories';
COMMENT ON COLUMN installed_apps.categories IS 'JSON array of app categories';
COMMENT ON COLUMN installed_apps.associated_directory_paths IS 'JSON array of file system paths';
COMMENT ON COLUMN installed_apps.raw_xml IS 'Original XML from UFDR report.xml';
COMMENT ON COLUMN installed_apps.raw_json IS 'Complete parsed data as JSON';
