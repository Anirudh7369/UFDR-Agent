"""
UFDR Installed Applications Extractor

This module extracts installed application data from UFDR files and inserts it into PostgreSQL.
It processes the report.xml file to extract all InstalledApplication model entries.

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

# Load environment variables from .env file
realtime_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(realtime_dir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[apps_extractor] Loaded .env from: {env_path}")
else:
    print(f"[apps_extractor] WARNING: .env file not found at: {env_path}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UFDRAppsExtractor:
    """
    Extracts installed application data from UFDR files and loads it into PostgreSQL.
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
        """
        Download UFDR file from MinIO URL to temporary file.

        Args:
            url: MinIO URL to download from

        Returns:
            str: Path to downloaded temporary file
        """
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
            temp_fd, temp_path = tempfile.mkstemp(suffix='.ufdr', prefix='ufdr_download_')
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
        """
        Extract report.xml from the UFDR file.

        Returns:
            Path to extracted report.xml file
        """
        # Download from URL if needed
        if self.is_url:
            self.ufdr_path = self._download_from_url(self.ufdr_source)
        else:
            self.ufdr_path = self.ufdr_source

        logger.info(f"Extracting report.xml from {self.ufdr_path}")

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix=f"ufdr_apps_{self.upload_id}_")
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
            # Parse ISO 8601 format: 2020-09-12T11:56:29.000+00:00
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except Exception as e:
            logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None

    def parse_installed_apps(self, report_xml_path: str) -> List[Dict]:
        """
        Parse installed applications from report.xml.

        Args:
            report_xml_path: Path to report.xml file

        Returns:
            List of installed app dictionaries
        """
        logger.info(f"Parsing installed applications from: {report_xml_path}")

        apps = []

        try:
            # Parse XML with iterparse to handle large files efficiently
            context = ET.iterparse(report_xml_path, events=('start', 'end'))
            context = iter(context)

            # Get the root element
            event, root = next(context)

            app_count = 0

            for event, elem in context:
                if event == 'end' and elem.tag == 'model' and elem.get('type') == 'InstalledApplication':
                    app_data = self._parse_app_model(elem)
                    if app_data:
                        apps.append(app_data)
                        app_count += 1

                        # Log progress every 50 apps
                        if app_count % 50 == 0:
                            logger.info(f"Parsed {app_count} apps...")

                    # Clear element to free memory
                    elem.clear()

            logger.info(f"Parsed {len(apps)} installed applications")
            return apps

        except Exception as e:
            logger.error(f"Error parsing report.xml: {e}", exc_info=True)
            return []

    def _parse_app_model(self, model_elem: ET.Element) -> Optional[Dict]:
        """
        Parse a single InstalledApplication model element.

        Args:
            model_elem: XML Element for the app model

        Returns:
            Dictionary with app data or None
        """
        try:
            app_data = {
                'app_identifier': None,
                'app_name': None,
                'app_version': None,
                'app_guid': None,
                'install_timestamp': None,
                'install_timestamp_dt': None,
                'last_launched_timestamp': None,
                'last_launched_dt': None,
                'decoding_status': None,
                'is_emulatable': False,
                'operation_mode': None,
                'deleted_state': model_elem.get('deleted_state'),
                'decoding_confidence': model_elem.get('decoding_confidence'),
                'permissions': [],
                'categories': [],
                'associated_directory_paths': [],
                'raw_xml': ET.tostring(model_elem, encoding='unicode'),
            }

            # Parse fields
            for field in model_elem.findall('field'):
                field_name = field.get('name')
                field_type = field.get('type')

                # Get value
                value_elem = field.find('value')
                if value_elem is not None:
                    value = value_elem.text or ''

                    if field_name == 'Name':
                        app_data['app_name'] = value
                    elif field_name == 'Version':
                        app_data['app_version'] = value
                    elif field_name == 'Identifier':
                        app_data['app_identifier'] = value
                    elif field_name == 'AppGUID':
                        app_data['app_guid'] = value if value else None
                    elif field_name == 'PurchaseDate':
                        timestamp_str = value_elem.text
                        if timestamp_str:
                            app_data['install_timestamp'] = self.parse_timestamp(timestamp_str)
                            if app_data['install_timestamp']:
                                app_data['install_timestamp_dt'] = datetime.fromtimestamp(
                                    app_data['install_timestamp'] / 1000
                                ).isoformat()
                    elif field_name == 'LastLaunched':
                        timestamp_str = value_elem.text
                        if timestamp_str:
                            app_data['last_launched_timestamp'] = self.parse_timestamp(timestamp_str)
                            if app_data['last_launched_timestamp']:
                                app_data['last_launched_dt'] = datetime.fromtimestamp(
                                    app_data['last_launched_timestamp'] / 1000
                                ).isoformat()
                    elif field_name == 'DecodingStatus':
                        app_data['decoding_status'] = value
                    elif field_name == 'IsEmulatable':
                        app_data['is_emulatable'] = value.lower() == 'true'
                    elif field_name == 'OperationMode':
                        app_data['operation_mode'] = value

            # Parse multiField elements
            for multi_field in model_elem.findall('multiField'):
                field_name = multi_field.get('name')
                values = [v.text for v in multi_field.findall('value') if v.text]

                if field_name == 'Permissions':
                    app_data['permissions'] = values
                elif field_name == 'Categories':
                    app_data['categories'] = values
                elif field_name == 'AssociatedDirectoryPaths':
                    app_data['associated_directory_paths'] = values

            # Only return if we have at least an identifier
            if app_data['app_identifier']:
                return app_data
            else:
                logger.debug("Skipping app without identifier")
                return None

        except Exception as e:
            logger.error(f"Error parsing app model: {e}", exc_info=True)
            return None

    def cleanup(self):
        """Clean up temporary files including downloaded UFDR file if from URL."""
        # Clean up temp directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp directory: {e}")

        # Clean up downloaded file if it was from URL
        if self.is_url and self.ufdr_path and os.path.exists(self.ufdr_path):
            try:
                os.remove(self.ufdr_path)
                logger.info(f"Cleaned up downloaded UFDR file: {self.ufdr_path}")
            except Exception as e:
                logger.error(f"Error cleaning up downloaded UFDR file: {e}")

    async def extract_and_load(self, db_operations_module):
        """
        Main extraction and loading pipeline.

        Args:
            db_operations_module: The apps_operations module for DB operations
        """
        try:
            # Extract report.xml
            report_xml_path = self.extract_report_xml()

            # Create extraction job
            await db_operations_module.create_app_extraction_job(
                self.upload_id,
                os.path.basename(self.ufdr_path)
            )

            # Update status to processing
            await db_operations_module.update_app_extraction_status(
                self.upload_id,
                'processing'
            )

            # Parse installed apps
            apps = self.parse_installed_apps(report_xml_path)

            if not apps:
                logger.warning("No installed applications found in UFDR file")
                await db_operations_module.update_app_extraction_status(
                    self.upload_id,
                    'completed',
                    total_apps=0,
                    processed_apps=0
                )
                return

            # Deduplicate by app_identifier
            unique_apps = self._deduplicate_apps(apps)

            logger.info(f"Total unique apps: {len(unique_apps)}")

            # Update total count
            await db_operations_module.update_app_extraction_status(
                self.upload_id,
                'processing',
                total_apps=len(unique_apps)
            )

            # Insert apps in batches
            batch_size = 50
            processed = 0

            for i in range(0, len(unique_apps), batch_size):
                batch = unique_apps[i:i + batch_size]
                await db_operations_module.bulk_insert_apps(self.upload_id, batch)
                processed += len(batch)

                # Update progress
                await db_operations_module.update_app_extraction_status(
                    self.upload_id,
                    'processing',
                    processed_apps=processed
                )

                logger.info(f"Processed {processed}/{len(unique_apps)} apps")

            # Mark as completed
            await db_operations_module.update_app_extraction_status(
                self.upload_id,
                'completed',
                total_apps=len(unique_apps),
                processed_apps=processed
            )

            logger.info(f"App extraction completed for upload_id: {self.upload_id}")

        except Exception as e:
            logger.error(f"App extraction failed: {e}", exc_info=True)
            await db_operations_module.update_app_extraction_status(
                self.upload_id,
                'failed',
                error_message=str(e)
            )
            raise
        finally:
            self.cleanup()

    def _deduplicate_apps(self, apps: List[Dict]) -> List[Dict]:
        """Deduplicate apps by app_identifier."""
        seen = set()
        unique = []

        for app in apps:
            identifier = app.get('app_identifier')
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique.append(app)

        return unique


# Async wrapper for RQ worker
def extract_apps_from_ufdr(upload_id: str, ufdr_path: str):
    """
    RQ worker job to extract installed apps from UFDR file.

    Args:
        upload_id: Unique upload identifier
        ufdr_path: Path to the UFDR file or MinIO URL
    """
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import apps_operations

    logger.info(f"Starting app extraction for upload_id: {upload_id}")

    extractor = UFDRAppsExtractor(ufdr_path, upload_id)

    # Run async extraction
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(extractor.extract_and_load(apps_operations))
        logger.info("App extraction completed successfully")
    except Exception as e:
        logger.error(f"App extraction failed: {e}", exc_info=True)
        raise
    finally:
        loop.close()


# Main function for standalone execution
async def main():
    """Main function for testing the extractor standalone."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python ufdr_apps_extractor.py <ufdr_file_path_or_url> <upload_id>")
        sys.exit(1)

    ufdr_path = sys.argv[1]
    upload_id = sys.argv[2]

    # Setup path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    from realtime.utils.db import apps_operations

    # Initialize schema
    await apps_operations.init_apps_schema()

    # Run extraction
    extractor = UFDRAppsExtractor(ufdr_path, upload_id)
    await extractor.extract_and_load(apps_operations)


if __name__ == '__main__':
    asyncio.run(main())
