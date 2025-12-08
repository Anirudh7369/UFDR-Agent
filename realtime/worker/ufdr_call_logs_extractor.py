"""
UFDR Call Logs Extractor

This module extracts call logs from all apps (WhatsApp, Telegram, Phone, Skype, etc.)
from UFDR files and inserts them into PostgreSQL.

Usage:
    Can be called directly or as an RQ worker job.
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
import urllib.parse
from dotenv import load_dotenv
import re

# Load environment variables
realtime_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(realtime_dir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[call_logs_extractor] Loaded .env from: {env_path}")
else:
    print(f"[call_logs_extractor] WARNING: .env file not found at: {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UFDRCallLogsExtractor:
    """
    Extracts call logs from all apps in UFDR files and loads into PostgreSQL.
    Supports both local file paths and MinIO/S3 URLs.
    """

    def __init__(self, ufdr_path_or_url: str, upload_id: str):
        """
        Initialize the extractor.

        Args:
            ufdr_path_or_url: Path to the UFDR file or MinIO URL
            upload_id: Unique identifier for this upload/extraction
        """
        self.ufdr_source = ufdr_path_or_url
        self.upload_id = upload_id
        self.temp_dir = None
        self.ufdr_path = None
        self.is_url = self._is_url(ufdr_path_or_url)

    def _is_url(self, path: str) -> bool:
        """Check if the path is a URL."""
        return path.startswith('http://') or path.startswith('https://')

    def _download_from_url(self, url: str) -> str:
        """Download UFDR file from MinIO URL to temporary file."""
        try:
            logger.info(f"Downloading UFDR file from: {url}")

            from urllib.parse import urlparse, unquote
            import boto3
            from botocore.client import Config

            parsed = urlparse(url)
            path_parts = parsed.path.lstrip('/').split('/', 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid MinIO URL format: {url}")

            bucket = path_parts[0]
            key = unquote(path_parts[1])

            logger.info(f"Parsed MinIO URL - Bucket: {bucket}, Key: {key}")

            # Create boto3 client
            s3_endpoint = os.getenv("S3_ENDPOINT", "http://localhost:9000")
            s3_region = os.getenv("S3_REGION", "us-east-1")
            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

            s3 = boto3.client(
                "s3",
                endpoint_url=s3_endpoint,
                region_name=s3_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                config=Config(signature_version="s3v4"),
            )

            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.ufdr', prefix='ufdr_download_calls_')
            os.close(temp_fd)

            # Download file
            logger.info(f"Downloading from S3: bucket={bucket}, key={key}")
            s3.download_file(bucket, key, temp_path)

            file_size = os.path.getsize(temp_path)
            logger.info(f"Downloaded UFDR file: {file_size} bytes to {temp_path}")

            return temp_path

        except Exception as e:
            logger.error(f"Failed to download UFDR file from URL: {e}", exc_info=True)
            raise

    def extract_report_xml(self) -> str:
        """Extract report.xml from the UFDR file."""
        if self.is_url:
            self.ufdr_path = self._download_from_url(self.ufdr_source)
        else:
            self.ufdr_path = self.ufdr_source

        logger.info(f"Extracting report.xml from {self.ufdr_path}")

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix=f"ufdr_calls_{self.upload_id}_")
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
        """Parse ISO 8601 timestamp to milliseconds since epoch."""
        if not timestamp_str:
            return None

        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except Exception as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None

    def parse_duration(self, duration_str: str) -> Optional[int]:
        """Parse duration string (HH:MM:SS) to seconds."""
        if not duration_str:
            return None

        try:
            # Format: 00:01:17 or 01:17 or 77
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            else:
                return int(duration_str)
        except Exception as e:
            logger.debug(f"Failed to parse duration '{duration_str}': {e}")
            return None

    def parse_call_logs(self, report_xml_path: str) -> List[Dict]:
        """Parse all call logs from report.xml."""
        logger.info(f"Parsing call logs from: {report_xml_path}")

        calls = []

        try:
            # Parse XML with iterparse
            context = ET.iterparse(report_xml_path, events=('start', 'end'))
            context = iter(context)

            # Get the root element
            event, root = next(context)

            call_count = 0

            for event, elem in context:
                if event == 'end':
                    # Remove namespace from tag
                    tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

                    if tag_name == 'model' and elem.get('type') == 'Call':
                        call_data = self._parse_call_model(elem)
                        if call_data:
                            calls.append(call_data)
                            call_count += 1

                            # Log progress every 10 calls
                            if call_count % 10 == 0:
                                logger.info(f"Parsed {call_count} calls...")

                        # Clear element to free memory
                        elem.clear()

            logger.info(f"Parsed {len(calls)} call logs")
            return calls

        except Exception as e:
            logger.error(f"Error parsing report.xml: {e}", exc_info=True)
            return []

    def _parse_call_model(self, model_elem: ET.Element) -> Optional[Dict]:
        """Parse a single Call model element."""
        try:
            call_data = {
                'call_id': model_elem.get('id'),
                'source_app': None,
                'direction': None,
                'call_type': None,
                'status': None,
                'call_timestamp': None,
                'call_timestamp_dt': None,
                'duration_seconds': None,
                'duration_string': None,
                'country_code': None,
                'network_code': None,
                'network_name': None,
                'account': None,
                'is_video_call': False,
                'deleted_state': model_elem.get('deleted_state'),
                'decoding_confidence': model_elem.get('decoding_confidence'),
                'parties': [],
                'from_party_identifier': None,
                'from_party_name': None,
                'from_party_is_owner': False,
                'to_party_identifier': None,
                'to_party_name': None,
                'to_party_is_owner': False,
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
                            call_data['source_app'] = value
                        elif field_name == 'Direction':
                            call_data['direction'] = value
                        elif field_name == 'Type':
                            call_data['call_type'] = value
                        elif field_name == 'Status':
                            call_data['status'] = value
                        elif field_name == 'TimeStamp':
                            timestamp_str = value_elem.text
                            if timestamp_str:
                                call_data['call_timestamp'] = self.parse_timestamp(timestamp_str)
                                if call_data['call_timestamp']:
                                    call_data['call_timestamp_dt'] = datetime.fromtimestamp(
                                        call_data['call_timestamp'] / 1000
                                    ).isoformat()
                        elif field_name == 'Duration':
                            call_data['duration_string'] = value
                            call_data['duration_seconds'] = self.parse_duration(value)
                        elif field_name == 'CountryCode':
                            call_data['country_code'] = value if value else None
                        elif field_name == 'NetworkCode':
                            call_data['network_code'] = value if value else None
                        elif field_name == 'NetworkName':
                            call_data['network_name'] = value if value else None
                        elif field_name == 'Account':
                            call_data['account'] = value
                        elif field_name == 'VideoCall':
                            call_data['is_video_call'] = value.lower() == 'true'

                elif tag_name == 'multiModelField' and child.get('name') == 'Parties':
                    # Parse parties
                    for party_model in child:
                        party_tag = party_model.tag.split('}')[-1] if '}' in party_model.tag else party_model.tag
                        if party_tag == 'model' and party_model.get('type') == 'Party':
                            party = self._parse_party(party_model)
                            if party:
                                call_data['parties'].append(party)

                                # Set main party fields for easy querying
                                if party['role'] == 'From':
                                    call_data['from_party_identifier'] = party['identifier']
                                    call_data['from_party_name'] = party['name']
                                    call_data['from_party_is_owner'] = party['is_phone_owner']
                                elif party['role'] == 'To':
                                    call_data['to_party_identifier'] = party['identifier']
                                    call_data['to_party_name'] = party['name']
                                    call_data['to_party_is_owner'] = party['is_phone_owner']

            return call_data

        except Exception as e:
            logger.error(f"Error parsing call model: {e}", exc_info=True)
            return None

    def _parse_party(self, party_elem: ET.Element) -> Optional[Dict]:
        """Parse a Party model element."""
        try:
            party = {
                'identifier': None,
                'name': None,
                'role': None,
                'is_phone_owner': False,
            }

            for child in party_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'field':
                    field_name = child.get('name')

                    # Get value
                    value_elem = None
                    for sub_child in child:
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

            return party

        except Exception as e:
            logger.debug(f"Error parsing party: {e}")
            return None

    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")

        if self.is_url and self.ufdr_path and os.path.exists(self.ufdr_path):
            try:
                os.remove(self.ufdr_path)
                logger.info(f"Cleaned up downloaded UFDR file: {self.ufdr_path}")
            except Exception as e:
                logger.error(f"Error cleaning up downloaded UFDR file: {e}")

    async def extract_and_load(self, db_operations_module):
        """Main extraction and loading pipeline."""
        try:
            # Extract report.xml
            report_xml_path = self.extract_report_xml()

            # Create extraction job
            await db_operations_module.create_call_log_extraction_job(
                self.upload_id,
                os.path.basename(self.ufdr_path)
            )

            # Update status
            await db_operations_module.update_call_log_extraction_status(
                self.upload_id,
                'processing'
            )

            # Parse call logs
            calls = self.parse_call_logs(report_xml_path)

            if not calls:
                logger.warning("No call logs found in UFDR file")
                await db_operations_module.update_call_log_extraction_status(
                    self.upload_id,
                    'completed',
                    total_calls=0,
                    processed_calls=0
                )
                return

            logger.info(f"Total calls extracted: {len(calls)}")

            # Update total count
            await db_operations_module.update_call_log_extraction_status(
                self.upload_id,
                'processing',
                total_calls=len(calls)
            )

            # Insert calls in batches
            batch_size = 20
            processed = 0

            for i in range(0, len(calls), batch_size):
                batch = calls[i:i + batch_size]
                await db_operations_module.bulk_insert_call_logs(self.upload_id, batch)
                processed += len(batch)

                # Update progress
                await db_operations_module.update_call_log_extraction_status(
                    self.upload_id,
                    'processing',
                    processed_calls=processed
                )

                logger.info(f"Processed {processed}/{len(calls)} calls")

            # Mark as completed
            await db_operations_module.update_call_log_extraction_status(
                self.upload_id,
                'completed',
                total_calls=len(calls),
                processed_calls=processed
            )

            logger.info(f"Call log extraction completed for upload_id: {self.upload_id}")

        except Exception as e:
            logger.error(f"Call log extraction failed: {e}", exc_info=True)
            await db_operations_module.update_call_log_extraction_status(
                self.upload_id,
                'failed',
                error_message=str(e)
            )
            raise
        finally:
            self.cleanup()


# Async wrapper for RQ worker
def extract_call_logs_from_ufdr(upload_id: str, ufdr_path: str):
    """RQ worker job to extract call logs from UFDR file."""
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import call_logs_operations

    logger.info(f"Starting call log extraction for upload_id: {upload_id}")

    extractor = UFDRCallLogsExtractor(ufdr_path, upload_id)

    # Run async extraction
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(extractor.extract_and_load(call_logs_operations))
        logger.info("Call log extraction completed successfully")
    except Exception as e:
        logger.error(f"Call log extraction failed: {e}", exc_info=True)
        raise
    finally:
        loop.close()


# Main function for standalone execution
async def main():
    """Main function for testing the extractor standalone."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ufdr_call_logs_extractor.py <ufdr_file_path_or_url> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Setup path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import call_logs_operations

    # Initialize schema
    await call_logs_operations.init_call_logs_schema()

    # Run extraction
    extractor = UFDRCallLogsExtractor(ufdr_path, upload_id)
    await extractor.extract_and_load(call_logs_operations)


if __name__ == '__main__':
    asyncio.run(main())
