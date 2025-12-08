"""
UFDR Browsing History Extractor

This module extracts browsing history, search queries, and bookmarks from UFDR files
and inserts them into PostgreSQL. It processes VisitedPage, SearchedItem, and WebBookmark models.

Usage:
    Can be called directly or as part of the unified UFDR extraction process.
"""

import os
import tempfile
import shutil
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
realtime_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(realtime_dir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[browsing_extractor] Loaded .env from: {env_path}")
else:
    print(f"[browsing_extractor] WARNING: .env file not found at: {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UFDRBrowsingExtractor:
    """
    Extracts browsing history, searches, and bookmarks from UFDR files and loads into PostgreSQL.
    Supports local file paths only (assumes file already downloaded).
    """

    def __init__(self, ufdr_path: str, upload_id: str):
        """
        Initialize the extractor.

        Args:
            ufdr_path: Path to the UFDR file (local path)
            upload_id: Unique identifier for this upload/extraction
        """
        self.ufdr_path = ufdr_path
        self.upload_id = upload_id
        self.temp_dir = None

    def extract_report_xml(self) -> str:
        """
        Extract report.xml from the UFDR file.

        Returns:
            Path to extracted report.xml file
        """
        logger.info(f"Extracting report.xml from {self.ufdr_path}")

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix=f"ufdr_browsing_{self.upload_id}_")
        logger.info(f"Created temp directory: {self.temp_dir}")

        try:
            with zipfile.ZipFile(self.ufdr_path, 'r') as zf:
                # Extract report.xml
                report_xml_path = zf.extract('report.xml', self.temp_dir)
                logger.info(f"Extracted report.xml to: {report_xml_path}")
                return report_xml_path

        except Exception as e:
            logger.error(f"Error extracting report.xml: {e}", exc_info=True)
            raise

    def parse_timestamp(self, timestamp_str: str) -> Optional[int]:
        """
        Parse ISO 8601 timestamp to milliseconds since epoch.

        Args:
            timestamp_str: ISO 8601 formatted timestamp

        Returns:
            Milliseconds since epoch or None
        """
        if not timestamp_str:
            return None

        try:
            # Parse ISO 8601 format: 2020-02-01T18:49:07.430+00:00
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except Exception as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None

    def parse_int(self, value_str: str) -> Optional[int]:
        """Parse integer value safely."""
        if not value_str:
            return None
        try:
            return int(value_str)
        except (ValueError, TypeError):
            return None

    def parse_browsing_history(self, report_xml_path: str) -> Dict[str, List[Dict]]:
        """
        Parse browsing history from report.xml.

        Args:
            report_xml_path: Path to report.xml file

        Returns:
            Dictionary with lists of visited_pages, searches, and bookmarks
        """
        logger.info(f"Parsing browsing history from: {report_xml_path}")

        visited_pages = []
        searches = []
        bookmarks = []

        try:
            # Use iterparse for memory-efficient parsing
            context = ET.iterparse(report_xml_path, events=('end',))

            entry_count = 0

            for event, elem in context:
                # Remove namespace from tag for comparison
                tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

                if tag_name == 'model':
                    model_type = elem.get('type')

                    if model_type == 'VisitedPage':
                        page_data = self._parse_visited_page(elem)
                        if page_data:
                            visited_pages.append(page_data)
                            entry_count += 1

                    elif model_type == 'SearchedItem':
                        search_data = self._parse_searched_item(elem)
                        if search_data:
                            searches.append(search_data)
                            entry_count += 1

                    elif model_type == 'WebBookmark':
                        bookmark_data = self._parse_web_bookmark(elem)
                        if bookmark_data:
                            bookmarks.append(bookmark_data)
                            entry_count += 1

                    # Log progress every 100 entries
                    if entry_count % 100 == 0:
                        logger.info(f"Parsed {entry_count} browsing entries...")

                # Clear element to free memory
                elem.clear()

            logger.info(f"Parsed {len(visited_pages)} visited pages, "
                       f"{len(searches)} searches, {len(bookmarks)} bookmarks")

            return {
                'visited_pages': visited_pages,
                'searches': searches,
                'bookmarks': bookmarks
            }

        except Exception as e:
            logger.error(f"Error parsing report.xml: {e}", exc_info=True)
            return {'visited_pages': [], 'searches': [], 'bookmarks': []}

    def _parse_visited_page(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a single VisitedPage model element."""
        try:
            page_data = {
                'entry_id': model_elem.get('id'),
                'entry_type': 'visited_page',
                'source_browser': None,
                'url': None,
                'title': None,
                'search_query': None,
                'bookmark_path': None,
                'last_visited': None,
                'last_visited_dt': None,
                'visit_count': None,
                'url_cache_file': None,
                'deleted_state': model_elem.get('deleted_state'),
                'decoding_confidence': model_elem.get('decoding_confidence'),
                'raw_xml': ET.tostring(model_elem, encoding='unicode'),
            }

            # Parse fields
            for child in model_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'field':
                    field_name = child.get('name')

                    # Get value element
                    value_elem = None
                    for sub_child in child:
                        sub_tag = sub_child.tag.split('}')[-1] if '}' in sub_child.tag else sub_child.tag
                        if sub_tag == 'value':
                            value_elem = sub_child
                            break

                    if value_elem is not None:
                        value = value_elem.text or ''

                        if field_name == 'Source':
                            page_data['source_browser'] = value
                        elif field_name == 'Url':
                            page_data['url'] = value
                        elif field_name == 'Title':
                            page_data['title'] = value
                        elif field_name == 'LastVisited':
                            timestamp_str = value_elem.text
                            if timestamp_str:
                                page_data['last_visited'] = self.parse_timestamp(timestamp_str)
                                if page_data['last_visited']:
                                    page_data['last_visited_dt'] = datetime.fromtimestamp(
                                        page_data['last_visited'] / 1000
                                    )
                        elif field_name == 'VisitCount':
                            page_data['visit_count'] = self.parse_int(value)
                        elif field_name == 'UrlCacheFile':
                            page_data['url_cache_file'] = value

            # Only return if we have essential data (at least URL or title)
            if page_data['url'] or page_data['title']:
                return page_data
            else:
                logger.debug("Skipping visited page without URL or title")
                return None

        except Exception as e:
            logger.error(f"Error parsing visited page: {e}", exc_info=True)
            return None

    def _parse_searched_item(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a single SearchedItem model element."""
        try:
            search_data = {
                'entry_id': model_elem.get('id'),
                'entry_type': 'search',
                'source_browser': None,
                'url': None,
                'title': None,
                'search_query': None,
                'bookmark_path': None,
                'last_visited': None,
                'last_visited_dt': None,
                'visit_count': None,
                'url_cache_file': None,
                'deleted_state': model_elem.get('deleted_state'),
                'decoding_confidence': model_elem.get('decoding_confidence'),
                'raw_xml': ET.tostring(model_elem, encoding='unicode'),
            }

            # Parse fields
            for child in model_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'field':
                    field_name = child.get('name')

                    # Get value element
                    value_elem = None
                    for sub_child in child:
                        sub_tag = sub_child.tag.split('}')[-1] if '}' in sub_child.tag else sub_child.tag
                        if sub_tag == 'value':
                            value_elem = sub_child
                            break

                    if value_elem is not None:
                        value = value_elem.text or ''

                        if field_name == 'Source':
                            search_data['source_browser'] = value
                        elif field_name == 'Value':
                            search_data['search_query'] = value
                        elif field_name == 'TimeStamp':
                            timestamp_str = value_elem.text
                            if timestamp_str:
                                search_data['last_visited'] = self.parse_timestamp(timestamp_str)
                                if search_data['last_visited']:
                                    search_data['last_visited_dt'] = datetime.fromtimestamp(
                                        search_data['last_visited'] / 1000
                                    )

            # Only return if we have essential data (search query)
            if search_data['search_query']:
                return search_data
            else:
                logger.debug("Skipping search without query")
                return None

        except Exception as e:
            logger.error(f"Error parsing searched item: {e}", exc_info=True)
            return None

    def _parse_web_bookmark(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a single WebBookmark model element."""
        try:
            bookmark_data = {
                'entry_id': model_elem.get('id'),
                'entry_type': 'bookmark',
                'source_browser': None,
                'url': None,
                'title': None,
                'search_query': None,
                'bookmark_path': None,
                'last_visited': None,
                'last_visited_dt': None,
                'visit_count': None,
                'url_cache_file': None,
                'deleted_state': model_elem.get('deleted_state'),
                'decoding_confidence': model_elem.get('decoding_confidence'),
                'raw_xml': ET.tostring(model_elem, encoding='unicode'),
            }

            # Parse fields
            for child in model_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'field':
                    field_name = child.get('name')

                    # Get value element
                    value_elem = None
                    for sub_child in child:
                        sub_tag = sub_child.tag.split('}')[-1] if '}' in sub_child.tag else sub_child.tag
                        if sub_tag == 'value':
                            value_elem = sub_child
                            break

                    if value_elem is not None:
                        value = value_elem.text or ''

                        if field_name == 'Source':
                            bookmark_data['source_browser'] = value
                        elif field_name == 'Url':
                            bookmark_data['url'] = value
                        elif field_name == 'Title':
                            bookmark_data['title'] = value
                        elif field_name == 'Path':
                            bookmark_data['bookmark_path'] = value
                        elif field_name == 'TimeStamp':
                            timestamp_str = value_elem.text
                            if timestamp_str:
                                bookmark_data['last_visited'] = self.parse_timestamp(timestamp_str)
                                if bookmark_data['last_visited']:
                                    bookmark_data['last_visited_dt'] = datetime.fromtimestamp(
                                        bookmark_data['last_visited'] / 1000
                                    )

            # Only return if we have essential data (URL or title)
            if bookmark_data['url'] or bookmark_data['title']:
                return bookmark_data
            else:
                logger.debug("Skipping bookmark without URL or title")
                return None

        except Exception as e:
            logger.error(f"Error parsing web bookmark: {e}", exc_info=True)
            return None

    def cleanup(self):
        """Clean up temporary files."""
        # Clean up temp directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")

    async def extract_and_load(self, db_operations_module):
        """
        Main extraction and loading pipeline.

        Args:
            db_operations_module: The browsing_operations module for DB operations
        """
        try:
            # Extract report.xml
            report_xml_path = self.extract_report_xml()

            # Create extraction job
            await db_operations_module.create_browsing_extraction_job(
                self.upload_id,
                os.path.basename(self.ufdr_path)
            )

            # Update status to processing
            await db_operations_module.update_browsing_extraction_status(
                self.upload_id,
                'processing'
            )

            # Parse browsing history
            browsing_data = self.parse_browsing_history(report_xml_path)

            visited_pages = browsing_data['visited_pages']
            searches = browsing_data['searches']
            bookmarks = browsing_data['bookmarks']

            total_entries = len(visited_pages) + len(searches) + len(bookmarks)

            if total_entries == 0:
                logger.warning("No browsing history found in UFDR file")
                await db_operations_module.update_browsing_extraction_status(
                    self.upload_id,
                    'completed',
                    total_entries=0,
                    processed_entries=0,
                    visited_pages_count=0,
                    searched_items_count=0,
                    bookmarks_count=0
                )
                return

            logger.info(f"Total browsing entries extracted: {total_entries}")

            # Update total count
            await db_operations_module.update_browsing_extraction_status(
                self.upload_id,
                'processing',
                total_entries=total_entries,
                visited_pages_count=len(visited_pages),
                searched_items_count=len(searches),
                bookmarks_count=len(bookmarks)
            )

            # Combine all entries for batch insertion
            all_entries = visited_pages + searches + bookmarks

            # Insert entries in batches
            batch_size = 100
            processed = 0

            for i in range(0, len(all_entries), batch_size):
                batch = all_entries[i:i + batch_size]
                await db_operations_module.bulk_insert_browsing_history(self.upload_id, batch)
                processed += len(batch)

                # Update progress
                await db_operations_module.update_browsing_extraction_status(
                    self.upload_id,
                    'processing',
                    processed_entries=processed
                )

                logger.info(f"Processed {processed}/{total_entries} browsing entries")

            # Mark as completed
            await db_operations_module.update_browsing_extraction_status(
                self.upload_id,
                'completed',
                total_entries=total_entries,
                processed_entries=processed
            )

            logger.info(f"Browsing extraction completed for upload_id: {self.upload_id}")

        except Exception as e:
            logger.error(f"Browsing extraction failed: {e}", exc_info=True)
            await db_operations_module.update_browsing_extraction_status(
                self.upload_id,
                'failed',
                error_message=str(e)
            )
            raise
        finally:
            self.cleanup()


# Main function for standalone execution
async def main():
    """Main function for testing the extractor standalone."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ufdr_browsing_extractor.py <ufdr_file_path> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Setup path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import browsing_operations

    # Initialize schema
    await browsing_operations.init_browsing_schema()

    # Run extraction
    extractor = UFDRBrowsingExtractor(ufdr_path, upload_id)
    await extractor.extract_and_load(browsing_operations)


if __name__ == '__main__':
    asyncio.run(main())
