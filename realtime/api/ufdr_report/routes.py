from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import logging
import sys
import os
import aiofiles
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from schemas.objects import UFDRUploadResponse
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter()

# Directory to store uploaded UFDR files
UPLOAD_DIR = Path(os.getenv("UFDR_UPLOAD_DIR", "./uploads/ufdr_files"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Maximum file size: 30 GB in bytes
MAX_FILE_SIZE = 30 * 1024 * 1024 * 1024  # 30 GB

@router.options("/upload-ufdr")
async def upload_ufdr_options():
    """Handle CORS preflight OPTIONS requests"""
    return {"status": "ok"}

@router.post("/upload-ufdr", response_model=UFDRUploadResponse)
async def upload_ufdr_file(
    file: UploadFile = File(..., description="UFDR file to upload (up to 30GB)"),
    file_id: Optional[str] = Form(None, description="Unique identifier for the file"),
    session_id: Optional[str] = Form(None, description="Session identifier"),
    email_id: Optional[str] = Form(None, description="User email identifier")
) -> UFDRUploadResponse:
    """
    Endpoint to receive large .ufdr files from the frontend.

    Args:
        file: UploadFile - The .ufdr file (can be up to 30GB)
        file_id: Optional unique identifier for the file
        session_id: Optional session identifier
        email_id: Optional user email identifier

    Returns:
        UFDRUploadResponse with status and file information
    """
    try:
        # Log incoming request
        logger.info(f"[REQUEST] Receiving UFDR file - Filename: {file.filename}, File ID: {file_id}, Session ID: {session_id}, Email ID: {email_id}")
        print(f"[REQUEST] Receiving UFDR file - Filename: {file.filename}, File ID: {file_id}, Session ID: {session_id}, Email ID: {email_id}")

        # Validate file extension (temporarily allowing .pdf for testing)
        allowed_extensions = ('.ufdr')
        # Validate filename (this also fixes type issues later)
        if not file.filename:
            logger.error("Uploaded file has no filename")
            return UFDRUploadResponse(
                status="error",
                file_info={"error": "Uploaded file has no filename"},
                file_id=file_id,
                status_code=400,
            )

        allowed_extensions = (".ufdr",)
        if not file.filename.lower().endswith(allowed_extensions):
            logger.error(f"Invalid file type: {file.filename}")
            return UFDRUploadResponse(
                status="error",
                file_info={"error": "Only .ufdr files are allowed"},
                file_id=file_id,
                status_code=400,
            )

        # At this point, mypy/pylance can safely treat filename as str
        original_filename: str = file.filename  # type: ignore[assignment]

        safe_filename = (
            f"{file_id}_{original_filename}" if file_id else original_filename
        )
        file_path = UPLOAD_DIR / safe_filename

        # Stream the file to disk in chunks to handle large files
        total_size = 0
        chunk_size = 1024 * 1024 * 10  # 10 MB chunks

        logger.info(f"Starting file upload to: {file_path}")

        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await file.read(chunk_size):
                total_size += len(chunk)

                # Check if file size exceeds maximum
                if total_size > MAX_FILE_SIZE:
                    # Delete the partially uploaded file
                    await f.close()
                    if file_path.exists():
                        file_path.unlink()

                    logger.error(f"File size exceeds maximum limit: {total_size} bytes")
                    return UFDRUploadResponse(
                        status="error",
                        file_info={"error": f"File size exceeds maximum limit of 30GB"},
                        file_id=file_id,
                        status_code=413
                    )

                await f.write(chunk)

        # Log successful upload
        file_size_mb = total_size / (1024 * 1024)
        file_size_gb = total_size / (1024 * 1024 * 1024)

        logger.info(f"[SUCCESS] File uploaded successfully - Size: {file_size_gb:.2f} GB ({file_size_mb:.2f} MB)")
        print(f"[SUCCESS] File uploaded successfully - Size: {file_size_gb:.2f} GB ({file_size_mb:.2f} MB)")

        response_data = UFDRUploadResponse(
            status="success",
            file_info={
                "filename": original_filename,
                "saved_as": safe_filename,
                "size_bytes": total_size,
                "size_mb": round(file_size_mb, 2),
                "size_gb": round(file_size_gb, 2),
                "file_path": str(file_path),
                "content_type": file.content_type
            },
            file_id=file_id,
            status_code=200
        )

        return response_data

    except Exception as e:
        logger.error(f"[ERROR] Exception occurred during file upload: {str(e)}", exc_info=True)
        print(f"[ERROR] Exception occurred: {str(e)}")

        # Clean up partial file if it exists
        if 'file_path' in locals() and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up partial file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up partial file: {cleanup_error}")

        return UFDRUploadResponse(
            status="error",
            file_info={"error": f"Failed to upload file: {str(e)}"},
            file_id=file_id,
            status_code=500
        )
