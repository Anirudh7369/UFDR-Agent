"""
UFDR Contacts Extractor

This module extracts contacts from UFDR files and inserts them into PostgreSQL.
It processes Contact models with their associated entries (phone numbers, emails, user IDs, profile pictures, etc.).

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
    print(f"[contacts_extractor] Loaded .env from: {env_path}")
else:
    print(f"[contacts_extractor] WARNING: .env file not found at: {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UFDRContactsExtractor:
    """
    Extracts contacts from UFDR files and loads into PostgreSQL.
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
        self.temp_dir = tempfile.mkdtemp(prefix=f"ufdr_contacts_{self.upload_id}_")
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

    def parse_contacts(self, report_xml_path: str) -> List[Dict]:
        """
        Parse contacts from report.xml.

        Args:
            report_xml_path: Path to report.xml file

        Returns:
            List of contact dictionaries with their entries
        """
        logger.info(f"Parsing contacts from: {report_xml_path}")

        contacts = []

        try:
            # Use iterparse for memory-efficient parsing
            context = ET.iterparse(report_xml_path, events=('end',))

            contact_count = 0

            for event, elem in context:
                # Remove namespace from tag for comparison
                tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

                if tag_name == 'model' and elem.get('type') == 'Contact':
                    contact_data = self._parse_contact_model(elem)
                    if contact_data:
                        contacts.append(contact_data)
                        contact_count += 1

                        # Log progress every 20 contacts
                        if contact_count % 20 == 0:
                            logger.info(f"Parsed {contact_count} contacts...")

                    # Clear element to free memory
                    elem.clear()

            logger.info(f"Parsed {len(contacts)} contacts")
            return contacts

        except Exception as e:
            logger.error(f"Error parsing report.xml: {e}", exc_info=True)
            return []

    def _parse_contact_model(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a single Contact model element."""
        try:
            contact_data = {
                'contact_id': model_elem.get('id'),
                'source_app': None,
                'service_identifier': None,
                'name': None,
                'account': None,
                'contact_type': None,
                'contact_group': None,
                'time_created': None,
                'time_created_dt': None,
                'notes': [],
                'interaction_statuses': [],
                'user_tags': [],
                'entries': [],  # Will store phone numbers, emails, user IDs, etc.
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
                            contact_data['source_app'] = value
                        elif field_name == 'ServiceIdentifier':
                            contact_data['service_identifier'] = value
                        elif field_name == 'Name':
                            contact_data['name'] = value
                        elif field_name == 'Account':
                            contact_data['account'] = value
                        elif field_name == 'Type':
                            contact_data['contact_type'] = value
                        elif field_name == 'Group':
                            contact_data['contact_group'] = value
                        elif field_name == 'TimeCreated':
                            timestamp_str = value_elem.text
                            if timestamp_str:
                                contact_data['time_created'] = self.parse_timestamp(timestamp_str)
                                if contact_data['time_created']:
                                    contact_data['time_created_dt'] = datetime.fromtimestamp(
                                        contact_data['time_created'] / 1000
                                    )

                elif tag_name == 'multiField':
                    field_name = child.get('name')

                    if field_name == 'Notes':
                        # Parse notes
                        for value_elem in child:
                            value_tag = value_elem.tag.split('}')[-1] if '}' in value_elem.tag else value_elem.tag
                            if value_tag == 'value' and value_elem.text:
                                contact_data['notes'].append(value_elem.text)

                    elif field_name == 'InteractionStatuses':
                        # Parse interaction statuses
                        for value_elem in child:
                            value_tag = value_elem.tag.split('}')[-1] if '}' in value_elem.tag else value_elem.tag
                            if value_tag == 'value' and value_elem.text:
                                contact_data['interaction_statuses'].append(value_elem.text)

                    elif field_name == 'UserTags':
                        # Parse user tags
                        for value_elem in child:
                            value_tag = value_elem.tag.split('}')[-1] if '}' in value_elem.tag else value_elem.tag
                            if value_tag == 'value' and value_elem.text:
                                contact_data['user_tags'].append(value_elem.text)

                elif tag_name == 'multiModelField' and child.get('name') == 'Entries':
                    # Parse contact entries (phone numbers, emails, user IDs, profile pictures, etc.)
                    for entry_model in child:
                        entry_tag = entry_model.tag.split('}')[-1] if '}' in entry_model.tag else entry_model.tag
                        if entry_tag == 'model':
                            entry_data = self._parse_contact_entry(entry_model)
                            if entry_data:
                                contact_data['entries'].append(entry_data)

            # Only return if we have essential data (at least name or entries)
            if contact_data['name'] or contact_data['entries']:
                return contact_data
            else:
                logger.debug("Skipping contact without name or entries")
                return None

        except Exception as e:
            logger.error(f"Error parsing contact model: {e}", exc_info=True)
            return None

    def _parse_contact_entry(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a contact entry (PhoneNumber, EmailAddress, UserID, ProfilePicture, etc.)."""
        try:
            entry_data = {
                'entry_id': model_elem.get('id'),
                'entry_type': model_elem.get('type'),  # PhoneNumber, EmailAddress, UserID, ProfilePicture, etc.
                'category': None,
                'value': None,
                'domain': None,
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

                        if field_name == 'Category':
                            entry_data['category'] = value
                        elif field_name == 'Value':
                            entry_data['value'] = value
                        elif field_name == 'Domain':
                            entry_data['domain'] = value

            # Only return if we have essential data (at least value)
            if entry_data['value']:
                return entry_data
            else:
                return None

        except Exception as e:
            logger.error(f"Error parsing contact entry: {e}", exc_info=True)
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
            db_operations_module: The contacts_operations module for DB operations
        """
        try:
            # Extract report.xml
            report_xml_path = self.extract_report_xml()

            # Create extraction job
            await db_operations_module.create_contact_extraction_job(
                self.upload_id,
                os.path.basename(self.ufdr_path)
            )

            # Update status to processing
            await db_operations_module.update_contact_extraction_status(
                self.upload_id,
                'processing'
            )

            # Parse contacts
            contacts = self.parse_contacts(report_xml_path)

            if not contacts:
                logger.warning("No contacts found in UFDR file")
                await db_operations_module.update_contact_extraction_status(
                    self.upload_id,
                    'completed',
                    total_contacts=0,
                    processed_contacts=0,
                    total_entries=0
                )
                return

            # Count total entries
            total_entries = sum(len(contact.get('entries', [])) for contact in contacts)

            logger.info(f"Total contacts extracted: {len(contacts)}")
            logger.info(f"Total contact entries: {total_entries}")

            # Update total count
            await db_operations_module.update_contact_extraction_status(
                self.upload_id,
                'processing',
                total_contacts=len(contacts),
                total_entries=total_entries
            )

            # Insert contacts in batches
            batch_size = 20
            processed = 0

            for i in range(0, len(contacts), batch_size):
                batch = contacts[i:i + batch_size]
                await db_operations_module.bulk_insert_contacts(self.upload_id, batch)
                processed += len(batch)

                # Update progress
                await db_operations_module.update_contact_extraction_status(
                    self.upload_id,
                    'processing',
                    processed_contacts=processed
                )

                logger.info(f"Processed {processed}/{len(contacts)} contacts")

            # Mark as completed
            await db_operations_module.update_contact_extraction_status(
                self.upload_id,
                'completed',
                total_contacts=len(contacts),
                processed_contacts=processed,
                total_entries=total_entries
            )

            logger.info(f"Contact extraction completed for upload_id: {self.upload_id}")

        except Exception as e:
            logger.error(f"Contact extraction failed: {e}", exc_info=True)
            await db_operations_module.update_contact_extraction_status(
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
        print("Usage: python ufdr_contacts_extractor.py <ufdr_file_path> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Setup path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import contacts_operations

    # Initialize schema
    await contacts_operations.init_contacts_schema()

    # Run extraction
    extractor = UFDRContactsExtractor(ufdr_path, upload_id)
    await extractor.extract_and_load(contacts_operations)


if __name__ == '__main__':
    asyncio.run(main())
