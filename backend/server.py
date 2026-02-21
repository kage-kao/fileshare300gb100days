from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import aiohttp
import re
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta

from aiogram.types import Update
from gigafile_client import gigafile_client

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
BACKEND_URL = os.environ.get('BACKEND_URL', '')

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if BOT_TOKEN:
        from bot import setup_webhook
        webhook_url = f"{BACKEND_URL}/api/webhook"
        await setup_webhook(BOT_TOKEN, webhook_url, BACKEND_URL)
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set - bot disabled")
    yield
    if BOT_TOKEN:
        from bot import teardown_webhook
        await teardown_webhook()
    mongo_client.close()


app = FastAPI(lifespan=lifespan, title="GigaFile Proxy API")
api_router = APIRouter(prefix="/api")


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


class UploadResponse(BaseModel):
    success: bool
    url: Optional[str] = None
    raw_url: Optional[str] = None
    proxy_url: Optional[str] = None
    expires: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None


@api_router.get("/")
async def root():
    return {"message": "GigaFile Proxy API", "endpoints": ["/api/upload", "/api/proxy"]}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    items = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for item in items:
        if isinstance(item['timestamp'], str):
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
    return items


# Telegram Webhook
_seen_updates: set = set()

@api_router.post("/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    from bot import bot, dp
    if not bot:
        return Response(status_code=200)
    try:
        data = await request.json()
        update_id = data.get("update_id")
        if update_id in _seen_updates:
            return Response(status_code=200)
        _seen_updates.add(update_id)
        if len(_seen_updates) > 5000:
            _seen_updates.clear()

        update = Update.model_validate(data)
        asyncio.create_task(dp.feed_update(bot, update))
    except Exception as e:
        logger.exception("Webhook processing error: %s", e)
    return Response(status_code=200)


# GigaFile Upload API
UPLOAD_READ_CHUNK = 1 * 1024 * 1024  # 1MB streaming read for file uploads

@api_router.post("/upload", response_model=UploadResponse, summary="Upload file to GigaFile.nu")
async def upload_to_gigafile(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    duration: int = Form(100),
):
    if duration not in {3, 5, 7, 14, 30, 60, 100}:
        duration = 100

    tmp_path = None
    try:
        if url:
            result = await gigafile_client.upload_from_url(url, lifetime=duration)
        elif file:
            # Stream uploaded file to disk before processing (memory-safe for large files)
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'_{file.filename or "upload"}') as tmp:
                tmp_path = tmp.name
                while True:
                    chunk = await file.read(UPLOAD_READ_CHUNK)
                    if not chunk:
                        break
                    tmp.write(chunk)
            result = await gigafile_client.upload_file_path(
                tmp_path, lifetime=duration
            )
            # Override filename with original
            if result.get('success') and file.filename:
                result['filename'] = file.filename
        else:
            raise HTTPException(status_code=400, detail="Provide 'file' or 'url'")

        if not result.get('success'):
            return UploadResponse(success=False, error=result.get('error'))

        proxy_url = f"{BACKEND_URL}/api/proxy?url={result['page_url']}"
        expires = (datetime.now(timezone.utc) + timedelta(days=duration)).isoformat()

        return UploadResponse(
            success=True,
            url=result['page_url'],
            raw_url=result['direct_url'],
            proxy_url=proxy_url,
            expires=expires,
            filename=result.get('filename'),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload error")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


# GigaFile Proxy Download
@api_router.get("/proxy", summary="Proxy-download from GigaFile")
async def proxy_gigafile(url: str):
    if 'gigafile.nu' not in url:
        raise HTTPException(status_code=400, detail="Only GigaFile.nu URLs are accepted")

    if '/download.php' in url:
        m = re.search(r'file=([^&]+)', url)
        if not m:
            raise HTTPException(status_code=400, detail="Cannot parse file ID from URL")
        file_id = m.group(1)
        server = url.split('/')[2]
        page_url = f"https://{server}/{file_id}"
    else:
        page_url = url.split('?')[0]

    file_id = page_url.rstrip('/').split('/')[-1]
    server_host = page_url.split('/')[2]
    download_url = f"https://{server_host}/download.php?file={file_id}"

    connector = aiohttp.TCPConnector(limit=0, force_close=False)
    session = aiohttp.ClientSession(connector=connector)
    try:
        async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=15)) as _:
            pass

        resp = await session.get(download_url, timeout=aiohttp.ClientTimeout(total=7200))

        if resp.status != 200 or (resp.content_type or '').startswith('text/html'):
            await resp.read()
            await session.close()
            raise HTTPException(status_code=404, detail="File not found or expired")

        cd = resp.headers.get('Content-Disposition', f'attachment; filename="{file_id}"')
        content_type = resp.headers.get('Content-Type', 'application/octet-stream')
        headers = {"Content-Disposition": cd}
        if 'Content-Length' in resp.headers:
            headers['Content-Length'] = resp.headers['Content-Length']

        async def _stream():
            try:
                async for chunk in resp.content.iter_chunked(2 * 1024 * 1024):
                    yield chunk
            finally:
                await resp.release()
                await session.close()

        return StreamingResponse(_stream(), media_type=content_type, headers=headers)

    except HTTPException:
        await session.close()
        raise
    except Exception as e:
        await session.close()
        logger.exception("Proxy error for %s", url)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/uploads")
async def get_uploads():
    items = await db.uploads.find({}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    return items


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
