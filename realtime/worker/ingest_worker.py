# realtime/worker/ingest_worker.py
"""
Simple ingest worker for demo / dev.

- process_upload(upload_id, bucket, key): streams object from S3/MinIO to a temp file,
  attempts to list/extract files if it's a zip, and writes lightweight metadata to
  data/uploads.json under the upload record.
"""

import os
import tempfile
import shutil
import json
import zipfile
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from datetime import datetime
import redis
import asyncio
import inspect

# Load envs
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "ufdr-uploads")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# boto3 client
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT if S3_ENDPOINT else None,
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
)

# simple JSON persistence (same as uploads router)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
UPLOADS_JSON = os.path.join(DATA_DIR, "uploads.json")
os.makedirs(DATA_DIR, exist_ok=True)

# Redis client (guarded)
try:
    rcli = redis.from_url(REDIS_URL)
except Exception as e:
    print("[worker] Warning: could not connect to Redis:", e)
    rcli = None


def _load_uploads_data():
    try:
        with open(UPLOADS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_uploads_data(d):
    with open(UPLOADS_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, default=str)


def _update_record(upload_id: str, patch: dict):
    data = _load_uploads_data()
    rec = data.get(upload_id, {})
    rec.update(patch)
    data[upload_id] = rec
    _save_uploads_data(data)


def _hset_progress(key: str, mapping: dict):
    """Helper to set Redis hash fields safely (no-op if redis unavailable)."""
    if not rcli:
        return
    # convert bytes/ints to strings where needed
    mapping_safe = {k: (str(v) if not isinstance(v, (str, bytes)) else v) for k, v in mapping.items()}
    try:
        rcli.hset(key, mapping=mapping_safe)
    except Exception as e:
        print("[worker] Warning: redis hset failed:", e)


def _hincrby(key: str, field: str, amount: int = 1):
    if not rcli:
        return
    try:
        rcli.hincrby(key, field, amount)
    except Exception as e:
        print("[worker] Warning: redis hincrby failed:", e)


def _hgetint(key: str, field: str) -> int:
    """
    Return integer value from redis hash field (0 if missing / error).

    This handles the case where rcli.hget might return an awaitable (in some
    redis client variants). If it's awaitable we run it to completion
    synchronously (safe inside an RQ worker).
    """
    if not rcli:
        return 0
    try:
        v = rcli.hget(key, field)

        # If we accidentally got an awaitable, run it to completion
        if inspect.isawaitable(v):
            try:
                loop = asyncio.get_event_loop()
                # If the loop is running, create a new one (rare in RQ worker)
                if loop.is_running():
                    v = asyncio.new_event_loop().run_until_complete(v)
                else:
                    v = loop.run_until_complete(v)
            except RuntimeError:
                # fallback: create a fresh loop
                v = asyncio.new_event_loop().run_until_complete(v)

        if v is None:
            return 0
        # decode bytes to string if needed
        if isinstance(v, bytes):
            v = v.decode()
        # Final guard: convert to int via str() to handle odd types
        return int(str(v))
    except Exception:
        return 0


def process_upload(upload_id: str, bucket: str, key: str):
    """
    RQ will call this. Streams the object to a temp file and does a simple unzip
    (if zip-like) and extracts filenames and tiny metadata.

    If the file is a UFDR file (Cellebrite), it will also extract WhatsApp data
    and load it into PostgreSQL.
    """
    print(f"[worker] Starting processing: upload_id={upload_id} bucket={bucket} key={key}")
    job_progress_key = f"ingest_progress:{upload_id}"

    # mark started in redis
    _hset_progress(job_progress_key, {"status": "running", "processed": 0, "total": 0})
    if rcli:
        try:
            rcli.expire(job_progress_key, 60 * 60 * 6)  # keep 6 hours
        except Exception:
            pass

    # temp workspace
    tmpdir = tempfile.mkdtemp(prefix=f"ufdr_{upload_id}_")
    tmpfile = os.path.join(tmpdir, "object.bin")
    is_ufdr_file = False

    try:
        # stream object to temp file
        print("[worker] Streaming object from S3...")
        obj = s3.get_object(Bucket=bucket, Key=key)
        streaming_body = obj["Body"]
        with open(tmpfile, "wb") as fh:
            # stream in chunks
            chunk_size = 1024 * 1024
            total = 0
            while True:
                chunk = streaming_body.read(chunk_size)
                if not chunk:
                    break
                fh.write(chunk)
                total += len(chunk)
                # update progress every ~10MB
                if total % (10 * 1024 * 1024) < chunk_size:
                    _hset_progress(job_progress_key, {"processed": total})
        print(f"[worker] Downloaded {total} bytes to {tmpfile}")

        # If file is a zip, try to inspect/extract a few entries
        extracted = []
        try:
            if zipfile.is_zipfile(tmpfile):
                print("[worker] File is zip — inspecting contents")
                with zipfile.ZipFile(tmpfile, "r") as zf:
                    namelist = zf.namelist()
                    _hset_progress(job_progress_key, {"total": len(namelist)})

                    # Check if this is a UFDR file (Cellebrite format)
                    # UFDR files contain report.xml and files/Database/ structure
                    is_ufdr_file = any('report.xml' in name for name in namelist) and \
                                   any('files/Database/' in name for name in namelist)

                    if is_ufdr_file:
                        print("[worker] Detected UFDR file (Cellebrite format)")
                        _hset_progress(job_progress_key, {"status": "processing_ufdr", "message": "Extracting WhatsApp data"})

                    # extract up to first 10 small entries and create metadata
                    for i, name in enumerate(namelist[:10], start=1):
                        info = zf.getinfo(name)
                        # read small files only
                        sample_text = ""
                        try:
                            with zf.open(name) as f:
                                sample = f.read(2048)  # sample up to 2KB
                                # decode safely
                                sample_text = sample.decode(errors="replace")
                        except Exception:
                            sample_text = ""
                        extracted.append({
                            "name": name,
                            "compressed_size": info.compress_size,
                            "file_size": info.file_size,
                            "sample": sample_text[:512],
                        })
                        _hincrby(job_progress_key, "processed", 1)
            else:
                # not a zip: create a small sample
                with open(tmpfile, "rb") as fh:
                    sample = fh.read(2048)
                    sample_text = sample.decode(errors="replace")
                extracted.append({
                    "name": os.path.basename(key),
                    "file_size": os.path.getsize(tmpfile),
                    "sample": sample_text[:512],
                })
                _hset_progress(job_progress_key, {"total": 1, "processed": 1})
        except Exception as e:
            print("[worker] Extraction error:", e)

        # persist extracted metadata into uploads.json under record.upload_id.ingest
        now = datetime.utcnow().isoformat() + "Z"
        ingest_summary = {
            "ingested_at": now,
            "extracted_count": len(extracted),
            "extracted_samples": extracted,
            "is_ufdr": is_ufdr_file
        }
        _update_record(upload_id, {"ingest": ingest_summary, "ingest_status": "done", "ingest_completed_at": now})

        # If this is a UFDR file, trigger WhatsApp extraction
        if is_ufdr_file:
            print("[worker] Starting WhatsApp data extraction from UFDR...")
            try:
                from realtime.worker.ufdr_whatsapp_extractor import extract_whatsapp_from_ufdr

                # Run WhatsApp extraction
                extract_whatsapp_from_ufdr(upload_id, tmpfile)
                print("[worker] WhatsApp extraction completed successfully")

                _hset_progress(job_progress_key, {"status": "done", "whatsapp_extracted": "true"})
            except Exception as e:
                print(f"[worker] WhatsApp extraction failed: {e}")
                _hset_progress(job_progress_key, {"status": "done", "whatsapp_error": str(e)})
                # Don't fail the entire job if WhatsApp extraction fails
        else:
            # mark complete in redis (processed should be int)
            processed_val = _hgetint(job_progress_key, "processed")
            _hset_progress(job_progress_key, {"status": "done", "processed": processed_val})

        print(f"[worker] Finished processing upload {upload_id}")

    except ClientError as e:
        print("[worker] S3 client error:", e)
        _update_record(upload_id, {"ingest_status": "failed", "ingest_error": str(e)})
        _hset_progress(job_progress_key, {"status": "failed", "error": str(e)})
    except Exception as e:
        print("[worker] Unexpected error:", e)
        _update_record(upload_id, {"ingest_status": "failed", "ingest_error": str(e)})
        _hset_progress(job_progress_key, {"status": "failed", "error": str(e)})
    finally:
        # cleanup tempdir
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
