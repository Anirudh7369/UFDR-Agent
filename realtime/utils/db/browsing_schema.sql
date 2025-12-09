-- Schema for storing browsing history, searches, and bookmarks from all browsers
-- Unified data from Chrome, Firefox, Opera, Safari, and all other browsers
-- Author: UFDR-Agent Team
-- Date: 2025-12-09

-- Drop existing tables if they exist
DROP TABLE IF EXISTS browsing_history CASCADE;
DROP TABLE IF EXISTS browsing_extractions CASCADE;

-- Table to track browsing extraction jobs
CREATE TABLE browsing_extractions (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL UNIQUE,
    ufdr_filename VARCHAR(500),
    extraction_status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    total_entries INTEGER DEFAULT 0,
    processed_entries INTEGER DEFAULT 0,
    visited_pages_count INTEGER DEFAULT 0,
    searched_items_count INTEGER DEFAULT 0,
    bookmarks_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Main table for all browsing history (visited pages, searches, bookmarks)
CREATE TABLE browsing_history (
    id SERIAL PRIMARY KEY,
    upload_id VARCHAR(255) NOT NULL,

    -- Entry identification
    entry_id VARCHAR(500), -- Unique entry ID from UFDR
    entry_type VARCHAR(50), -- 'visited_page', 'search', 'bookmark'
    source_browser VARCHAR(200), -- Browser/App (Chrome, Firefox, Opera Mobile, Safari, etc.)

    -- URL and title information
    url TEXT, -- Full URL
    title TEXT, -- Page title or bookmark title

    -- Search specific
    search_query TEXT, -- Search query text (for SearchedItem)

    -- Bookmark specific
    bookmark_path TEXT, -- Folder path for bookmark

    -- Visit information
    last_visited BIGINT, -- Milliseconds since epoch
    last_visited_dt TIMESTAMP, -- Converted datetime for easy querying
    visit_count INTEGER, -- Number of visits (for VisitedPage)

    -- Cache information
    url_cache_file TEXT, -- Cache file path if available

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
    FOREIGN KEY (upload_id) REFERENCES browsing_extractions(upload_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_browsing_upload_id ON browsing_history(upload_id);
CREATE INDEX idx_browsing_entry_type ON browsing_history(entry_type);
CREATE INDEX idx_browsing_source_browser ON browsing_history(source_browser);
CREATE INDEX idx_browsing_last_visited ON browsing_history(last_visited);
CREATE INDEX idx_browsing_last_visited_dt ON browsing_history(last_visited_dt);
CREATE INDEX idx_browsing_url ON browsing_history USING hash(url);
CREATE INDEX idx_browsing_title_text ON browsing_history USING GIN (to_tsvector('english', title));
CREATE INDEX idx_browsing_search_query_text ON browsing_history USING GIN (to_tsvector('english', search_query));

-- View for easy querying of visited pages
CREATE OR REPLACE VIEW visited_pages_view AS
SELECT
    b.id,
    b.upload_id,
    b.source_browser,
    b.url,
    b.title,
    b.last_visited_dt,
    b.visit_count,
    e.ufdr_filename,
    e.extraction_status
FROM browsing_history b
LEFT JOIN browsing_extractions e ON b.upload_id = e.upload_id
WHERE b.entry_type = 'visited_page';

-- View for easy querying of search history
CREATE OR REPLACE VIEW search_history_view AS
SELECT
    b.id,
    b.upload_id,
    b.source_browser,
    b.search_query,
    b.last_visited_dt,
    e.ufdr_filename,
    e.extraction_status
FROM browsing_history b
LEFT JOIN browsing_extractions e ON b.upload_id = e.upload_id
WHERE b.entry_type = 'search';

-- View for easy querying of bookmarks
CREATE OR REPLACE VIEW bookmarks_view AS
SELECT
    b.id,
    b.upload_id,
    b.source_browser,
    b.title,
    b.url,
    b.bookmark_path,
    b.last_visited_dt,
    e.ufdr_filename,
    e.extraction_status
FROM browsing_history b
LEFT JOIN browsing_extractions e ON b.upload_id = e.upload_id
WHERE b.entry_type = 'bookmark';

-- Comments for documentation
COMMENT ON TABLE browsing_extractions IS 'Tracks browsing history extraction jobs from UFDR files';
COMMENT ON TABLE browsing_history IS 'Unified browsing history, searches, and bookmarks from all browsers';

COMMENT ON COLUMN browsing_history.entry_type IS 'Type of entry: visited_page, search, or bookmark';
COMMENT ON COLUMN browsing_history.source_browser IS 'Browser or app (Chrome, Firefox, Opera Mobile, Safari, Play Store, etc.)';
COMMENT ON COLUMN browsing_history.url IS 'Full URL of visited page or bookmark';
COMMENT ON COLUMN browsing_history.title IS 'Page title or bookmark title';
COMMENT ON COLUMN browsing_history.search_query IS 'Search query text (for search entries)';
COMMENT ON COLUMN browsing_history.bookmark_path IS 'Folder path for bookmarks (e.g., /custom_root/speedDial/)';
COMMENT ON COLUMN browsing_history.visit_count IS 'Number of times page was visited';
COMMENT ON COLUMN browsing_history.last_visited IS 'Last visit time in milliseconds since epoch';
COMMENT ON COLUMN browsing_history.raw_xml IS 'Original XML from UFDR report.xml';
COMMENT ON COLUMN browsing_history.raw_json IS 'Complete parsed data as JSON';
