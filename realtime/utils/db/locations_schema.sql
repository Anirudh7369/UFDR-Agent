-- Schema for storing location data from all apps extracted from UFDR files
-- Unified locations from Google Fit, Maps, and multiple applications
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- Drop existing tables if they exist
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS location_extractions CASCADE;

-- Table to track location extraction jobs
CREATE TABLE location_extractions (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL UNIQUE,
    ufdr_filename VARCHAR(500),
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    total_locations INTEGER DEFAULT 0,
    processed_locations INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main table for all location data (unified across all apps)
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- Location identification
    location_id VARCHAR(500), -- Unique location ID if available
    source_app VARCHAR(200), -- App that recorded the location (Google Maps, Google Fit, Uber, etc.)

    -- Geographic coordinates
    latitude DOUBLE PRECISION, -- Latitude in decimal degrees
    longitude DOUBLE PRECISION, -- Longitude in decimal degrees
    altitude DOUBLE PRECISION, -- Altitude in meters

    -- Location accuracy and metadata
    accuracy DOUBLE PRECISION, -- Horizontal accuracy in meters
    vertical_accuracy DOUBLE PRECISION, -- Vertical accuracy in meters
    bearing DOUBLE PRECISION, -- Direction of travel in degrees (0-360)
    speed DOUBLE PRECISION, -- Speed in meters per second

    -- Location type and category
    location_type VARCHAR(100), -- GPS, Network, Cell Tower, WiFi
    category VARCHAR(100), -- Home, Work, Transit, etc.

    -- Address information
    address TEXT, -- Full formatted address
    city VARCHAR(200),
    state VARCHAR(200),
    country VARCHAR(200),
    postal_code VARCHAR(50),

    -- Timestamps
    location_timestamp BIGINT, -- Milliseconds since epoch
    location_timestamp_dt TIMESTAMP, -- Converted datetime for easy querying

    -- Additional metadata
    device_name VARCHAR(200), -- Device that recorded the location
    platform VARCHAR(50), -- Android, iOS
    confidence VARCHAR(50), -- High, Medium, Low

    -- Activity recognition (if available)
    activity_type VARCHAR(100), -- Still, Walking, Running, Driving, Biking, etc.
    activity_confidence INTEGER, -- 0-100

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
    FOREIGN KEY (upload_id) REFERENCES location_extractions(upload_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_locations_upload_id ON locations(upload_id);
CREATE INDEX idx_locations_source_app ON locations(source_app);
CREATE INDEX idx_locations_timestamp ON locations(location_timestamp);
CREATE INDEX idx_locations_timestamp_dt ON locations(location_timestamp_dt);
CREATE INDEX idx_locations_lat_lng ON locations(latitude, longitude);
CREATE INDEX idx_locations_location_type ON locations(location_type);
CREATE INDEX idx_locations_category ON locations(category);
CREATE INDEX idx_locations_activity_type ON locations(activity_type);

-- Spatial index for geographic queries (requires PostGIS extension)
-- Uncomment if PostGIS is available:
-- CREATE INDEX idx_locations_geom ON locations USING GIST (ST_MakePoint(longitude, latitude));

-- View for easy querying
CREATE OR REPLACE VIEW locations_view AS
SELECT
    l.id,
    l.upload_id,
    l.source_app,
    l.latitude,
    l.longitude,
    l.altitude,
    l.accuracy,
    l.location_timestamp_dt,
    l.address,
    l.city,
    l.state,
    l.country,
    l.category,
    l.activity_type,
    e.ufdr_filename,
    e.extraction_status
FROM locations l
LEFT JOIN location_extractions e ON l.upload_id = e.upload_id;

-- Comments for documentation
COMMENT ON TABLE location_extractions IS 'Tracks location extraction jobs from UFDR files';
COMMENT ON TABLE locations IS 'Unified location data from all apps (Google Maps, Google Fit, Uber, etc.)';

COMMENT ON COLUMN locations.source_app IS 'App that recorded the location (Google Maps, Google Fit, Uber, Lyft, etc.)';
COMMENT ON COLUMN locations.latitude IS 'Latitude in decimal degrees (-90 to 90)';
COMMENT ON COLUMN locations.longitude IS 'Longitude in decimal degrees (-180 to 180)';
COMMENT ON COLUMN locations.altitude IS 'Altitude in meters above sea level';
COMMENT ON COLUMN locations.accuracy IS 'Horizontal accuracy radius in meters';
COMMENT ON COLUMN locations.location_timestamp IS 'Location time in milliseconds since epoch';
COMMENT ON COLUMN locations.activity_type IS 'Detected activity: Still, Walking, Running, Driving, Biking, etc.';
COMMENT ON COLUMN locations.raw_xml IS 'Original XML from UFDR report.xml';
COMMENT ON COLUMN locations.raw_json IS 'Complete parsed data as JSON';
