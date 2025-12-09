"""
UFDR Instant Messages Extractor

This module extracts instant message data from UFDR files and inserts it into PostgreSQL.
It processes the report.xml file to extract all InstantMessage model entries from all apps.

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
    print(f"[messages_extractor] Loaded .env from: {env_path}")
else:
    print(f"[messages_extractor] WARNING: .env file not found at: {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UFDRMessagesExtractor:
    """
    Extracts instant message data from UFDR files and loads it into PostgreSQL.
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
        self.temp_dir = tempfile.mkdtemp(prefix=f"ufdr_messages_{self.upload_id}_")
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

    def parse_instant_messages(self, report_xml_path: str) -> List[Dict]:
        """
        Parse instant messages from report.xml.

        Args:
            report_xml_path: Path to report.xml file

        Returns:
            List of message dictionaries
        """
        logger.info(f"Parsing instant messages from: {report_xml_path}")

        messages = []

        try:
            # Use iterparse for memory-efficient parsing
            context = ET.iterparse(report_xml_path, events=('start', 'end'))
            context = iter(context)

            # Get the root element
            event, root = next(context)

            message_count = 0

            for event, elem in context:
                if event == 'end':
                    # Remove namespace from tag for comparison
                    tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

                    if tag_name == 'model' and elem.get('type') == 'InstantMessage':
                        message_data = self._parse_message_model(elem)
                        if message_data:
                            messages.append(message_data)
                            message_count += 1

                            # Log progress every 50 messages
                            if message_count % 50 == 0:
                                logger.info(f"Parsed {message_count} messages...")

                        # Clear element to free memory
                        elem.clear()

            logger.info(f"Parsed {len(messages)} instant messages")
            return messages

        except Exception as e:
            logger.error(f"Error parsing report.xml: {e}", exc_info=True)
            return []

    def _parse_message_model(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a single InstantMessage model element."""
        try:
            message_data = {
                'message_id': model_elem.get('id'),
                'source_app': None,
                'body': None,
                'message_type': None,
                'platform': None,
                'message_timestamp': None,
                'message_timestamp_dt': None,
                'deleted_state': model_elem.get('deleted_state'),
                'decoding_confidence': model_elem.get('decoding_confidence'),
                'parties': [],
                'attachments': [],
                'from_party_identifier': None,
                'from_party_name': None,
                'from_party_is_owner': False,
                'to_party_identifier': None,
                'to_party_name': None,
                'to_party_is_owner': False,
                'has_attachments': False,
                'attachment_count': 0,
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

                        if field_name == 'Source' or field_name == 'SourceApplication':
                            message_data['source_app'] = value
                        elif field_name == 'Body':
                            message_data['body'] = value
                        elif field_name == 'Type':
                            message_data['message_type'] = value
                        elif field_name == 'Platform':
                            message_data['platform'] = value
                        elif field_name == 'TimeStamp':
                            timestamp_str = value_elem.text
                            if timestamp_str:
                                message_data['message_timestamp'] = self.parse_timestamp(timestamp_str)
                                if message_data['message_timestamp']:
                                    message_data['message_timestamp_dt'] = datetime.fromtimestamp(
                                        message_data['message_timestamp'] / 1000
                                    )

                elif tag_name == 'modelField':
                    field_name = child.get('name')

                    if field_name == 'From':
                        # Parse From party
                        for party_model in child:
                            party_tag = party_model.tag.split('}')[-1] if '}' in party_model.tag else party_model.tag
                            if party_tag == 'model' and party_model.get('type') == 'Party':
                                party = self._parse_party(party_model)
                                if party:
                                    message_data['parties'].append(party)
                                    message_data['from_party_identifier'] = party.get('identifier')
                                    message_data['from_party_name'] = party.get('name')
                                    message_data['from_party_is_owner'] = party.get('is_phone_owner', False)

                    elif field_name == 'Attachment':
                        # Single attachment
                        for attach_model in child:
                            attach_tag = attach_model.tag.split('}')[-1] if '}' in attach_model.tag else attach_model.tag
                            if attach_tag == 'model' and attach_model.get('type') == 'Attachment':
                                attachment = self._parse_attachment(attach_model)
                                if attachment:
                                    message_data['attachments'].append(attachment)
                                    message_data['has_attachments'] = True

                elif tag_name == 'multiModelField':
                    field_name = child.get('name')

                    if field_name == 'To':
                        # Parse To parties (can be multiple for group chats)
                        for party_model in child:
                            party_tag = party_model.tag.split('}')[-1] if '}' in party_model.tag else party_model.tag
                            if party_tag == 'model' and party_model.get('type') == 'Party':
                                party = self._parse_party(party_model)
                                if party:
                                    message_data['parties'].append(party)
                                    # Set first To party as primary recipient
                                    if not message_data['to_party_identifier']:
                                        message_data['to_party_identifier'] = party.get('identifier')
                                        message_data['to_party_name'] = party.get('name')
                                        message_data['to_party_is_owner'] = party.get('is_phone_owner', False)

                    elif field_name == 'Attachments':
                        # Multiple attachments
                        for attach_model in child:
                            attach_tag = attach_model.tag.split('}')[-1] if '}' in attach_model.tag else attach_model.tag
                            if attach_tag == 'model' and attach_model.get('type') == 'Attachment':
                                attachment = self._parse_attachment(attach_model)
                                if attachment:
                                    message_data['attachments'].append(attachment)
                                    message_data['has_attachments'] = True

            # Set attachment count
            message_data['attachment_count'] = len(message_data['attachments'])

            # Only return if we have essential data
            if message_data['source_app']:
                return message_data
            else:
                logger.debug("Skipping message without source app")
                return None

        except Exception as e:
            logger.error(f"Error parsing message model: {e}", exc_info=True)
            return None

    def _parse_party(self, party_model: ET.Element) -> Optional[Dict]:
        """Parse a Party model element."""
        try:
            party = {
                'identifier': None,
                'name': None,
                'role': None,
                'is_phone_owner': False,
            }

            for field in party_model:
                tag_name = field.tag.split('}')[-1] if '}' in field.tag else field.tag

                if tag_name == 'field':
                    field_name = field.get('name')

                    # Get value
                    value_elem = None
                    for sub_child in field:
                        sub_tag = sub_child.tag.split('}')[-1] if '}' in sub_child.tag else sub_child.tag
                        if sub_tag == 'value':
                            value_elem = sub_child
                            break

                    if value_elem is not None:
                        value = value_elem.text or ''

                        if field_name == 'Identifier':
                            party['identifier'] = value
                        elif field_name == 'Name':
                            party['name'] = value
                        elif field_name == 'Role':
                            party['role'] = value
                        elif field_name == 'IsPhoneOwner':
                            party['is_phone_owner'] = value.lower() == 'true'

            return party if party['identifier'] else None

        except Exception as e:
            logger.debug(f"Error parsing party: {e}")
            return None

    def _parse_attachment(self, attach_model: ET.Element) -> Optional[Dict]:
        """Parse an Attachment model element."""
        try:
            attachment = {
                'attachment_type': None,
                'filename': None,
                'file_path': None,
                'file_size': None,
                'mime_type': None,
            }

            for field in attach_model:
                tag_name = field.tag.split('}')[-1] if '}' in field.tag else field.tag

                if tag_name == 'field':
                    field_name = field.get('name')

                    # Get value
                    value_elem = None
                    for sub_child in field:
                        sub_tag = sub_child.tag.split('}')[-1] if '}' in sub_child.tag else sub_child.tag
                        if sub_tag == 'value':
                            value_elem = sub_child
                            break

                    if value_elem is not None:
                        value = value_elem.text or ''

                        if field_name == 'Type':
                            attachment['attachment_type'] = value
                        elif field_name == 'Filename':
                            attachment['filename'] = value
                        elif field_name == 'LocalPath':
                            attachment['file_path'] = value
                        elif field_name == 'Size':
                            try:
                                attachment['file_size'] = int(value) if value else None
                            except ValueError:
                                pass
                        elif field_name == 'ContentType':
                            attachment['mime_type'] = value

            return attachment

        except Exception as e:
            logger.debug(f"Error parsing attachment: {e}")
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
            db_operations_module: The messages_operations module for DB operations
        """
        try:
            # Extract report.xml
            report_xml_path = self.extract_report_xml()

            # Create extraction job
            await db_operations_module.create_message_extraction_job(
                self.upload_id,
                os.path.basename(self.ufdr_path)
            )

            # Update status to processing
            await db_operations_module.update_message_extraction_status(
                self.upload_id,
                'processing'
            )

            # Parse instant messages
            messages = self.parse_instant_messages(report_xml_path)

            if not messages:
                logger.warning("No instant messages found in UFDR file")
                await db_operations_module.update_message_extraction_status(
                    self.upload_id,
                    'completed',
                    total_messages=0,
                    processed_messages=0
                )
                return

            logger.info(f"Total messages extracted: {len(messages)}")

            # Update total count
            await db_operations_module.update_message_extraction_status(
                self.upload_id,
                'processing',
                total_messages=len(messages)
            )

            # Insert messages in batches
            batch_size = 50
            processed = 0

            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                await db_operations_module.bulk_insert_messages(self.upload_id, batch)
                processed += len(batch)

                # Update progress
                await db_operations_module.update_message_extraction_status(
                    self.upload_id,
                    'processing',
                    processed_messages=processed
                )

                logger.info(f"Processed {processed}/{len(messages)} messages")

            # Mark as completed
            await db_operations_module.update_message_extraction_status(
                self.upload_id,
                'completed',
                total_messages=len(messages),
                processed_messages=processed
            )

            logger.info(f"Message extraction completed for upload_id: {self.upload_id}")

        except Exception as e:
            logger.error(f"Message extraction failed: {e}", exc_info=True)
            await db_operations_module.update_message_extraction_status(
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
        print("Usage: python ufdr_messages_extractor.py <ufdr_file_path> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Setup path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import messages_operations

    # Initialize schema
    await messages_operations.init_messages_schema()

    # Run extraction
    extractor = UFDRMessagesExtractor(ufdr_path, upload_id)
    await extractor.extract_and_load(messages_operations)


if __name__ == '__main__':
    asyncio.run(main())
