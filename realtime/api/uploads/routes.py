# realtime/api/uploads/routes.py
"""
Uploads router for direct-to-MinIO (S3-compatible) multipart uploads.

Endpoints:
- POST /api/uploads/init
    -> request: { filename, size, session_id?, metadata?, part_size? }
    -> response: { upload_id, key, bucket, part_size, parts: [{part_number, url}], total_parts }

- PUT /api/uploads/{upload_id}/complete
    -> request: { parts: [{ part_number, etag }, ...] }
    -> completes multipart upload and enqueues ingest job

- GET /api/uploads/{upload_id}/status
    -> returns basic upload status and parts count

- GET /api/uploads/{upload_id}/ingest-progress
    -> returns ingest progress (Redis first, then realtime/data/uploads.json fallback)

Notes:
- This implementation persists upload metadata to realtime/data/uploads.json as a
  development fallback. Replace with a proper DB in production.
- Uses boto3 to talk to MinIO/S3.
"""

import os
import uuid
import math
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import redis
from rq import Queue
import inspect
import asyncio

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# --------------------
# Configuration (env)
# --------------------
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "ufdr-uploads")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
PRESIGN_EXPIRES = int(os.getenv("PRESIGN_EXPIRES", 60 * 60))  # 1 hour default
MAX_PARTS = int(os.getenv("MAX_PARTS", 10000))
DEFAULT_PART_SIZE = int(os.getenv("DEFAULT_PART_SIZE", 64 * 1024 * 1024))  # 64 MB
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --------------------
# Persistence (dev)
# --------------------
# keep uploads.json inside realtime/data so router + worker share the same file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
UPLOADS_JSON = os.path.join(DATA_DIR, "uploads.json")


# --------------------
# S3 client (boto3)
# --------------------
s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT if S3_ENDPOINT else None,
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)


# --------------------
# Pydantic models
# --------------------
class InitUploadRequest(BaseModel):
    filename: str
    size: int
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    part_size: Optional[int] = None  # client can request an override


class PartPresign(BaseModel):
    part_number: int
    url: str


class InitUploadResponse(BaseModel):
    upload_id: str
    key: str
    bucket: str
    part_size: int
    total_parts: int
    parts: List[PartPresign]


class CompletePart(BaseModel):
    part_number: int
    etag: str


class CompleteUploadRequest(BaseModel):
    parts: List[CompletePart]
    checksum: Optional[str] = None


class CompleteUploadResponse(BaseModel):
    upload_id: str
    key: str
    bucket: str
    status: str
    location: Optional[str] = None


class UploadStatusResponse(BaseModel):
    upload_id: str
    key: Optional[str]
    bucket: Optional[str]
    parts_uploaded: int
    total_parts: Optional[int]
    status: str


# --------------------
# Persistence helpers
# --------------------
def _load_uploads_data() -> Dict[str, Any]:
    try:
        with open(UPLOADS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        # if file corrupt or other issue, return empty dict to avoid crashing
        return {}


def _save_uploads_data(d: Dict[str, Any]):
    with open(UPLOADS_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, default=str)


def persist_upload_record(upload_id: str, record: Dict[str, Any]):
    data = _load_uploads_data()
    data[upload_id] = record
    _save_uploads_data(data)


def get_upload_record(upload_id: str) -> Optional[Dict[str, Any]]:
    data = _load_uploads_data()
    return data.get(upload_id)


# --------------------
# Utility functions
# --------------------
def choose_part_size(file_size: int, requested_part_size: Optional[int]) -> int:
    """
    Pick a part size (bytes) that results in <= MAX_PARTS parts.
    """
    if requested_part_size and requested_part_size > 0:
        part_size = int(requested_part_size)
    else:
        part_size = DEFAULT_PART_SIZE

    num_parts = math.ceil(file_size / part_size)
    if num_parts > MAX_PARTS:
        part_size = math.ceil(file_size / MAX_PARTS)
    return part_size


# --------------------
# Routes
# --------------------
@router.post("/init", response_model=InitUploadResponse)
def uploads_init(body: InitUploadRequest):
    """
    Initialize a multipart upload in S3/MinIO and return presigned URLs for parts.
    """
    filename = body.filename
    size = int(body.size)
    session_id = body.session_id or ""
    metadata = body.metadata or {}
    requested_part_size = body.part_size

    part_size = choose_part_size(size, requested_part_size)
    total_parts = math.ceil(size / part_size)
    if total_parts <= 0:
        total_parts = 1
    if total_parts > MAX_PARTS:
        raise HTTPException(status_code=400, detail=f"File too large; requires {total_parts} parts (limit {MAX_PARTS}).")

    upload_uuid = str(uuid.uuid4())
    key = f"uploads/{upload_uuid}/{filename}"

    # create multipart upload
    try:
        create_resp = s3_client.create_multipart_upload(
            Bucket=S3_BUCKET,
            Key=key,
            Metadata={"session_id": session_id, **{k: str(v) for k, v in metadata.items()}} if metadata else {"session_id": session_id},
        )
        s3_upload_id = create_resp["UploadId"]
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Could not create multipart upload: {e}")

    # generate presigned URLs for each part
    parts: List[Dict[str, Any]] = []
    try:
        for part_num in range(1, total_parts + 1):
            presigned = s3_client.generate_presigned_url(
                "upload_part",
                Params={"Bucket": S3_BUCKET, "Key": key, "UploadId": s3_upload_id, "PartNumber": part_num},
                ExpiresIn=PRESIGN_EXPIRES,
            )
            parts.append({"part_number": part_num, "url": presigned})
    except ClientError as e:
        # abort multipart upload if presign generation fails
        try:
            s3_client.abort_multipart_upload(Bucket=S3_BUCKET, Key=key, UploadId=s3_upload_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URLs: {e}")

    # Persist mapping
    record = {
        "upload_id": upload_uuid,
        "s3_upload_id": s3_upload_id,
        "key": key,
        "bucket": S3_BUCKET,
        "filename": filename,
        "size": size,
        "session_id": session_id,
        "metadata": metadata,
        "part_size": part_size,
        "total_parts": total_parts,
        "parts_generated": len(parts),
        "status": "initiated",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        persist_upload_record(upload_uuid, record)
    except Exception:
        # warn but continue
        print("Warning: failed to persist upload record to local JSON file.")

    return InitUploadResponse(
        upload_id=upload_uuid,
        key=key,
        bucket=S3_BUCKET,
        part_size=part_size,
        total_parts=total_parts,
        parts=[PartPresign(part_number=p["part_number"], url=p["url"]) for p in parts],
    )


@router.put("/{upload_id}/complete", response_model=CompleteUploadResponse)
def uploads_complete(upload_id: str, body: CompleteUploadRequest = Body(...)):
    """
    Complete a multipart upload, persist record and enqueue an ingest job (RQ).
    Expects JSON:
    { "parts": [{"part_number":1,"etag":"\"etagval\""}, ...] }
    """
    record = get_upload_record(upload_id)
    if not record:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    s3_upload_id = record.get("s3_upload_id")
    key = record.get("key")
    bucket = record.get("bucket", S3_BUCKET)

    if not s3_upload_id or not key:
        raise HTTPException(status_code=500, detail="Incomplete upload record (missing s3_upload_id or key).")

    # Build parts list sorted by part number
    parts_sorted = sorted(body.parts, key=lambda p: p.part_number)
    multipart = {"Parts": [{"ETag": p.etag, "PartNumber": int(p.part_number)} for p in parts_sorted]}

    try:
        resp = s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=s3_upload_id,
            MultipartUpload=multipart,
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete multipart upload: {e}")

    # Update persisted record to uploaded
    record["status"] = "uploaded"
    record["completed_at"] = datetime.utcnow().isoformat() + "Z"
    record["location"] = resp.get("Location") or f"{bucket}/{key}"
    try:
        persist_upload_record(upload_id, record)
    except Exception:
        print("Warning: failed to persist upload record after completion.")

    # Enqueue ingest job (Redis + RQ)
    try:
        redis_conn = redis.from_url(REDIS_URL)
        q = Queue("ingest", connection=redis_conn)
        job = q.enqueue("realtime.worker.ingest_worker.process_upload", upload_id, bucket, key)
        record["ingest_job_id"] = job.id
        record["status"] = "queued_for_ingest"
        record["enqueue_at"] = datetime.utcnow().isoformat() + "Z"
        try:
            persist_upload_record(upload_id, record)
        except Exception:
            print("Warning: failed to persist upload record after enqueue.")
        print(f"Enqueued ingest job {job.id} for upload {upload_id}")
    except Exception as e:
        # not fatal; return success but warn
        print("Warning: failed to enqueue ingest job:", e)

    return CompleteUploadResponse(
        upload_id=upload_id,
        key=key,
        bucket=bucket,
        status=record.get("status", "uploaded"),
        location=record.get("location"),
    )


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
def uploads_status(upload_id: str):
    """
    Return upload status. If upload is still in progress, list parts and count them.
    """
    record = get_upload_record(upload_id)
    if not record:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    status = record.get("status", "initiated")
    key = record.get("key")
    bucket = record.get("bucket", S3_BUCKET)
    total_parts = record.get("total_parts")

    parts_count = 0
    if status in ("initiated", "uploading"):
        s3_upload_id = record.get("s3_upload_id")
        if s3_upload_id and key:
            try:
                resp = s3_client.list_parts(Bucket=bucket, Key=key, UploadId=s3_upload_id)
                parts_count = len(resp.get("Parts", []))
            except ClientError:
                parts_count = 0

    if status == "uploaded":
        parts_count = total_parts or parts_count

    return UploadStatusResponse(
        upload_id=upload_id,
        key=key,
        bucket=bucket,
        parts_uploaded=parts_count,
        total_parts=total_parts,
        status=status,
    )


@router.get("/{upload_id}/ingest-progress")
def ingest_progress(upload_id: str):
    """
    Returns a small JSON summary for frontend polling:
    { status: "running"|"done"|"failed"|..., processed: int, total: int, ingest?: {...} }
    """
    # Try Redis first
    try:
        r = redis.from_url(REDIS_URL)
        key = f"ingest_progress:{upload_id}"
        if r.exists(key):
            raw = r.hgetall(key)
        # If the redis client returned an awaitable (some async clients), run it.
        if inspect.isawaitable(raw):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're likely in an async environment; create a temporary loop to run the coroutine
                    raw = asyncio.new_event_loop().run_until_complete(raw)
                else:
                    raw = loop.run_until_complete(raw)
            except RuntimeError:
                # Fallback: create a fresh loop
                raw = asyncio.new_event_loop().run_until_complete(raw)

        # now raw should be a mapping (dict-like)
        out: Dict[str, Any] = {}
        for k, v in raw.items():
            if isinstance(k, bytes):
                k = k.decode()
            if isinstance(v, bytes):
                v = v.decode()
            if k in ("processed", "total"):
                try:
                    v = int(v)
                except Exception:
                    pass
            out[k] = v

            # Normalize fields
            return {
                "status": out.get("status", "running"),
                "processed": out.get("processed", 0),
                "total": out.get("total", 0),
                **({"ingest": out.get("ingest")} if out.get("ingest") else {}),
            }
    except Exception:
        # Redis might be down — fall back to file
        pass

    # Fallback to realtime/data/uploads.json
    try:
        if os.path.exists(UPLOADS_JSON):
            with open(UPLOADS_JSON, "r", encoding="utf-8") as f:
                allr = json.load(f)
            rec = allr.get(upload_id)
            if rec:
                ingest = rec.get("ingest")
                status = rec.get("ingest_status") or ("done" if ingest else rec.get("status"))
                return {
                    "status": status,
                    "processed": ingest.get("extracted_count") if ingest else 0,
                    "total": len(ingest.get("extracted_samples", [])) if ingest else 0,
                    "ingest": ingest,
                }
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Upload not found or no progress available")


@router.get("/{upload_id}/extraction-status")
def extraction_status(upload_id: str):
    """
    Returns extraction status for all UFDR data types.
    Frontend can poll this endpoint to know when all extractions are complete.

    Response:
    {
        "status": "completed"|"processing"|"failed"|"not_started",
        "upload_id": "...",
        "extractions": {
            "apps": {"status": "completed", "extracted": true},
            "call_logs": {"status": "completed", "extracted": true},
            "messages": {"status": "completed", "extracted": true},
            "locations": {"status": "completed", "extracted": true},
            "browsing": {"status": "completed", "extracted": true},
            "contacts": {"status": "completed", "extracted": true}
        },
        "overall_status": "completed",
        "message": "All extractions completed successfully"
    }
    """
    # Try Redis first for real-time status
    try:
        r = redis.from_url(REDIS_URL)
        key = f"ingest_progress:{upload_id}"

        if r.exists(key):
            raw = r.hgetall(key)

            # Handle async Redis clients
            if inspect.isawaitable(raw):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        raw = asyncio.new_event_loop().run_until_complete(raw)
                    else:
                        raw = loop.run_until_complete(raw)
                except RuntimeError:
                    raw = asyncio.new_event_loop().run_until_complete(raw)

            # Decode Redis bytes to strings
            progress: Dict[str, Any] = {}
            for k, v in raw.items():
                if isinstance(k, bytes):
                    k = k.decode()
                if isinstance(v, bytes):
                    v = v.decode()
                progress[k] = v

            # Build extraction status response
            status = progress.get("status", "processing")

            # Check individual extraction flags
            extractions = {
                "apps": {
                    "status": "completed" if progress.get("apps_extracted") == "true" else "processing",
                    "extracted": progress.get("apps_extracted") == "true"
                },
                "call_logs": {
                    "status": "completed" if progress.get("call_logs_extracted") == "true" else "processing",
                    "extracted": progress.get("call_logs_extracted") == "true"
                },
                "messages": {
                    "status": "completed" if progress.get("messages_extracted") == "true" else "processing",
                    "extracted": progress.get("messages_extracted") == "true"
                },
                "locations": {
                    "status": "completed" if progress.get("locations_extracted") == "true" else "processing",
                    "extracted": progress.get("locations_extracted") == "true"
                },
                "browsing": {
                    "status": "completed" if progress.get("browsing_extracted") == "true" else "processing",
                    "extracted": progress.get("browsing_extracted") == "true"
                },
                "contacts": {
                    "status": "completed" if progress.get("contacts_extracted") == "true" else "processing",
                    "extracted": progress.get("contacts_extracted") == "true"
                }
            }

            # Determine overall status
            all_completed = all(ext.get("extracted") for ext in extractions.values())
            overall_status = "completed" if (status == "done" and all_completed) else status

            # Add error information if any
            errors = {}
            for ext_type in ["apps", "call_logs", "messages", "locations", "browsing", "contacts"]:
                error_key = f"{ext_type}_error"
                if error_key in progress:
                    errors[ext_type] = progress[error_key]

            response = {
                "status": overall_status,
                "upload_id": upload_id,
                "extractions": extractions,
                "overall_status": overall_status,
                "message": "All extractions completed successfully" if overall_status == "completed" else "Extraction in progress"
            }

            if errors:
                response["errors"] = errors
                response["message"] = "Some extractions failed"
                response["overall_status"] = "failed"

            return response

    except Exception as e:
        print(f"Error checking Redis extraction status: {e}")
        # Fall through to file-based check

    # Fallback to file-based status check
    try:
        if os.path.exists(UPLOADS_JSON):
            with open(UPLOADS_JSON, "r", encoding="utf-8") as f:
                allr = json.load(f)
            rec = allr.get(upload_id)
            if rec:
                status = rec.get("status", "not_started")
                return {
                    "status": status,
                    "upload_id": upload_id,
                    "overall_status": status,
                    "message": f"Extraction status: {status}"
                }
    except Exception as e:
        print(f"Error checking file-based extraction status: {e}")

    raise HTTPException(status_code=404, detail="Upload not found or extraction status unavailable")
