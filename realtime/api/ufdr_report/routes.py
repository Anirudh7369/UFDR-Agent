from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import logging
import sys
import os
from pathlib import Path

import aiofiles
from dotenv import load_dotenv
from pydantic import BaseModel

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------
# Logging & router
# ---------------------------------------------------------------------
logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------
# Make schema imports work (team folder structure)
# ---------------------------------------------------------------------
# Adjusted sys.path only if needed to find `schemas.objects`
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from schemas.objects import UFDRUploadResponse  # noqa: E402

# ---------------------------------------------------------------------
# S3 / MinIO configuration
# ---------------------------------------------------------------------
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_BUCKET_DEFAULT = os.getenv("S3_BUCKET", "ufdr-uploads")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)

# ---------------------------------------------------------------------
# Local-disk upload configuration (legacy teammate flow)
# ---------------------------------------------------------------------
UPLOAD_DIR = Path(os.getenv("UFDR_UPLOAD_DIR", "./uploads/ufdr_files"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 30 * 1024 * 1024 * 1024  # 30 GB

# ---------------------------------------------------------------------
# Request Model for Bucket-Based Registration
# ---------------------------------------------------------------------
class UFDRFromBucketRequest(BaseModel):
    bucket: Optional[str] = None
    key: str  # S3 key, e.g., "uploads/<uuid>/report.ufdr"
    filename: Optional[str] = None
    file_id: Optional[str] = None
    session_id: Optional[str] = None
    email_id: Optional[str] = None


# ---------------------------------------------------------------------
# OPTIONS (CORS preflight)
# ---------------------------------------------------------------------
@router.options("/upload-ufdr")
async def upload_ufdr_options():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# DIRECT FILE UPLOAD (legacy disk-based workflow)
# ---------------------------------------------------------------------
@router.post("/upload-ufdr", response_model=UFDRUploadResponse)
async def upload_ufdr_file(
    file: UploadFile = File(...),
    file_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    email_id: Optional[str] = Form(None),
) -> UFDRUploadResponse:
    """
    Legacy endpoint – streams UFDR file to local disk.

    NOTE:
    - Your new MinIO multipart flow uses /api/uploads/* routes.
    - This endpoint can coexist; it's just a separate path.
    """
    try:
        logger.info(
            f"[REQUEST] Receiving UFDR file -> {file.filename}, "
            f"file_id={file_id}, session_id={session_id}, email={email_id}"
        )

        # Validate filename
        if not file.filename:
            logger.error("Uploaded file has no filename")
            return UFDRUploadResponse(
                status="error",
                file_info={"error": "Uploaded file has no filename"},
                file_id=file_id,
                status_code=400,
            )

        # Validate extension
        if not file.filename.lower().endswith(".ufdr"):
            logger.error(f"Invalid file type: {file.filename}")
            return UFDRUploadResponse(
                status="error",
                file_info={"error": "Only .ufdr files are allowed"},
                file_id=file_id,
                status_code=400,
            )

        # Build save path
        original_filename = file.filename
        safe_filename = (
            f"{file_id}_{original_filename}" if file_id else original_filename
        )
        file_path = UPLOAD_DIR / safe_filename

        # Stream to disk
        logger.info(f"Streaming upload to: {file_path}")
        total_size = 0
        chunk_size = 10 * 1024 * 1024  # 10 MB

        async with aiofiles.open(file_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    await f.close()
                    if file_path.exists():
                        file_path.unlink()

                    logger.error(f"Upload exceeded max size: {total_size}")
                    return UFDRUploadResponse(
                        status="error",
                        file_info={"error": "File exceeds 30GB limit"},
                        file_id=file_id,
                        status_code=413,
                    )

                await f.write(chunk)

        # Log final size
        mb = total_size / (1024 * 1024)
        gb = total_size / (1024 * 1024 * 1024)

        logger.info(f"[SUCCESS] Uploaded {gb:.2f} GB ({mb:.2f} MB)")

        # Return structured response
        return UFDRUploadResponse(
            status="success",
            file_info={
                "filename": original_filename,
                "saved_as": safe_filename,
                "size_bytes": total_size,
                "size_mb": round(mb, 2),
                "size_gb": round(gb, 2),
                "file_path": str(file_path),
                "content_type": file.content_type,
            },
            file_id=file_id,
            status_code=200,
        )

    except Exception as e:
        logger.error(f"[ERROR] {e}", exc_info=True)

        if "file_path" in locals() and file_path.exists():
            file_path.unlink()

        return UFDRUploadResponse(
            status="error",
            file_info={"error": str(e)},
            file_id=file_id,
            status_code=500,
        )


# ---------------------------------------------------------------------
# REGISTER FROM BUCKET (MinIO flow)
# ---------------------------------------------------------------------
@router.post("/upload-ufdr/from-bucket", response_model=UFDRUploadResponse)
async def register_ufdr_from_bucket(
    body: UFDRFromBucketRequest,
) -> UFDRUploadResponse:
    """
    This is the MinIO-based endpoint:

    - Expects object already uploaded to MinIO (via multipart flow).
    - Verifies it exists (HEAD).
    - Returns UFDRUploadResponse with bucket+key so the rest of the pipeline
      can ingest from MinIO.
    """
    bucket = body.bucket or S3_BUCKET_DEFAULT
    key = body.key

    logger.info(
        f"[REGISTER] Verify UFDR in bucket={bucket}, key={key}, "
        f"file_id={body.file_id}, session={body.session_id}"
    )

    # HEAD request to MinIO
    try:
        head = s3_client.head_object(Bucket=bucket, Key=key)
        size_bytes = head.get("ContentLength", 0)
        content_type = head.get("ContentType", "application/octet-stream")
    except ClientError:
        raise HTTPException(
            status_code=404,
            detail=f"Object not found in bucket: {bucket}/{key}",
        )

    filename = body.filename or os.path.basename(key)
    mb = size_bytes / (1024 * 1024)
    gb = size_bytes / (1024 * 1024 * 1024)

    logger.info(f"[SUCCESS] Verified object -> {filename}, {gb:.2f}GB")

    return UFDRUploadResponse(
        status="success",
        file_info={
            "filename": filename,
            "saved_as": key,
            "size_bytes": size_bytes,
            "size_mb": round(mb, 2),
            "size_gb": round(gb, 2),
            "file_path": f"s3://{bucket}/{key}",
            "content_type": content_type,
            "bucket": bucket,
            "key": key,
            "session_id": body.session_id,
            "email_id": body.email_id,
        },
        file_id=body.file_id,
        status_code=200,
    )
