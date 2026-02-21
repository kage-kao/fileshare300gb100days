"""
GigaFile.nu async client - MEMORY-SAFE
- Streaming chunk uploads (reads from disk, never loads all chunks into RAM)
- Parallel chunk uploads with bounded concurrency (up to 4 concurrent)
- Larger chunk size (50MB) for speed
- Robust timeouts (sock_read, sock_connect) to prevent hangs
- Retry logic for failed chunks and downloads
- Streaming download with stall detection
"""
import aiohttp
import asyncio
import uuid
import re
import math
import os
import tempfile
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50 * 1024 * 1024  # 50 MB per chunk
UPLOAD_CONCURRENCY = 4  # parallel chunk uploads
VALID_LIFETIMES = {3, 5, 7, 14, 30, 60, 100}
MAX_RETRIES = 3
DOWNLOAD_READ_CHUNK = 2 * 1024 * 1024  # 2MB read buffer for downloads
STALL_TIMEOUT = 120  # seconds


def _extract_filename_from_cd(cd: str) -> Optional[str]:
    if not cd:
        return None
    m = re.search(r"filename\*=UTF-8''(.+?)(?:;|$)", cd, re.IGNORECASE)
    if m:
        return unquote(m.group(1)).strip()
    m = re.search(r'filename="?([^";\n]+)"?', cd, re.IGNORECASE)
    if m:
        return m.group(1).strip().strip('"')
    return None


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = path.rstrip('/').split('/')[-1]
    return unquote(name) if name else 'file'


def _read_chunk_from_file(filepath: str, chunk_no: int) -> bytes:
    """Read a single chunk from file on disk. Memory-safe: only 1 chunk in RAM."""
    with open(filepath, 'rb') as f:
        f.seek(chunk_no * CHUNK_SIZE)
        return f.read(CHUNK_SIZE)


class GigaFileClient:
    def __init__(self):
        self._server_cache: str | None = None
        self._server_cache_ts: float = 0

    async def get_server(self) -> str:
        import time
        now = time.monotonic()
        if self._server_cache and (now - self._server_cache_ts) < 300:
            return self._server_cache

        timeout = aiohttp.ClientTimeout(total=15, sock_connect=10, sock_read=10)
        async with aiohttp.ClientSession() as s:
            async with s.get('https://gigafile.nu/', timeout=timeout) as resp:
                text = await resp.text()
        m = re.search(r'var server\s*=\s*"(.+?)"', text)
        if not m:
            raise RuntimeError("Failed to find GigaFile server")
        self._server_cache = m.group(1)
        self._server_cache_ts = now
        return self._server_cache

    async def _upload_chunk(
        self,
        session: aiohttp.ClientSession,
        server: str,
        token: str,
        filename: str,
        chunk_data: bytes,
        chunk_no: int,
        total_chunks: int,
        lifetime: int,
    ) -> dict:
        for attempt in range(MAX_RETRIES):
            try:
                form = aiohttp.FormData()
                form.add_field('id', token)
                form.add_field('name', filename)
                form.add_field('chunk', str(chunk_no))
                form.add_field('chunks', str(total_chunks))
                form.add_field('lifetime', str(lifetime))
                form.add_field('file', chunk_data, filename='blob', content_type='application/octet-stream')

                timeout = aiohttp.ClientTimeout(total=600, sock_connect=30, sock_read=300)
                async with session.post(
                    f'https://{server}/upload_chunk.php',
                    data=form,
                    timeout=timeout,
                ) as resp:
                    result = await resp.json()
                    return result
            except Exception as e:
                logger.warning("Chunk %d/%d upload attempt %d failed: %s", chunk_no + 1, total_chunks, attempt + 1, e)
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        return {}

    async def _upload_chunks_streaming(
        self,
        session: aiohttp.ClientSession,
        server: str,
        token: str,
        filename: str,
        filepath: str,
        total_chunks: int,
        lifetime: int,
        progress_cb: Optional[Callable[[str, int], Awaitable[None]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Optional[str]:
        """Upload chunks from disk with controlled parallelism.
        MEMORY-SAFE: reads one chunk at a time from disk, never loads all into RAM.
        """
        result_url = None
        sem = asyncio.Semaphore(UPLOAD_CONCURRENCY)
        completed = 0
        lock = asyncio.Lock()

        # First chunk must go first to establish session on GigaFile
        first_data = _read_chunk_from_file(filepath, 0)
        r = await self._upload_chunk(session, server, token, filename, first_data, 0, total_chunks, lifetime)
        del first_data  # free memory immediately
        if 'url' in r:
            result_url = r['url']
        completed = 1
        if progress_cb:
            pct = min(99, int(completed * 100 / total_chunks))
            await progress_cb('upload', pct)

        if total_chunks <= 1:
            return result_url

        # Upload remaining chunks in parallel, reading from disk on-demand
        async def upload_one(chunk_no: int):
            nonlocal result_url, completed
            if cancel_event and cancel_event.is_set():
                return
            async with sem:
                if cancel_event and cancel_event.is_set():
                    return
                # Read chunk from disk right before uploading (memory-safe)
                chunk_data = await asyncio.get_event_loop().run_in_executor(
                    None, _read_chunk_from_file, filepath, chunk_no
                )
                try:
                    r = await self._upload_chunk(
                        session, server, token, filename, chunk_data,
                        chunk_no, total_chunks, lifetime
                    )
                finally:
                    del chunk_data  # free memory immediately after upload
                if 'url' in r:
                    async with lock:
                        result_url = r['url']
                async with lock:
                    completed += 1
                    if progress_cb:
                        pct = min(99, int(completed * 100 / total_chunks))
                        await progress_cb('upload', pct)

        tasks = [upload_one(i) for i in range(1, total_chunks)]
        await asyncio.gather(*tasks)

        return result_url

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        lifetime: int = 100,
        progress_cb: Optional[Callable[[str, int], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """Upload bytes - saves to temp file first to use streaming upload."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(data)
            del data  # free the bytes from memory

            return await self.upload_file_path(
                tmp_path, lifetime=lifetime, progress_cb=progress_cb,
                original_filename=filename,
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    async def _download_with_retry(
        self,
        url: str,
        tmp_path: str,
        progress_cb: Optional[Callable[[str, int], Awaitable[None]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> tuple[str, int]:
        """Download file with retry logic and stall detection. Returns (filename, file_size)."""
        filename = _filename_from_url(url) or 'file'

        for attempt in range(MAX_RETRIES):
            try:
                timeout = aiohttp.ClientTimeout(
                    total=7200,
                    sock_connect=30,
                    sock_read=STALL_TIMEOUT,
                )

                own_session = False
                if session is None:
                    connector = aiohttp.TCPConnector(ssl=False, limit=0, force_close=False)
                    session = aiohttp.ClientSession(connector=connector)
                    own_session = True

                try:
                    async with session.get(url, allow_redirects=True, timeout=timeout) as resp:
                        if resp.status != 200:
                            if attempt < MAX_RETRIES - 1:
                                logger.warning("Download attempt %d: HTTP %d, retrying...", attempt + 1, resp.status)
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return filename, 0

                        cd = resp.headers.get('Content-Disposition', '')
                        fn = _extract_filename_from_cd(cd)
                        if fn:
                            filename = fn

                        total_size = int(resp.headers.get('Content-Length', 0))
                        downloaded = 0

                        with open(tmp_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(DOWNLOAD_READ_CHUNK):
                                if cancel_event and cancel_event.is_set():
                                    return filename, downloaded
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_cb and total_size > 0:
                                    pct = min(99, int(downloaded * 100 / total_size))
                                    await progress_cb('download', pct)
                                elif progress_cb and downloaded > 0:
                                    mb = downloaded / (1024 * 1024)
                                    pct = min(95, int(mb) % 96)
                                    await progress_cb('download', pct)

                        if progress_cb:
                            await progress_cb('download', 100)

                        return filename, downloaded
                finally:
                    if own_session:
                        await session.close()
                        session = None

            except asyncio.TimeoutError:
                logger.warning("Download attempt %d timed out (stall detection)", attempt + 1)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
            except aiohttp.ClientError as e:
                logger.warning("Download attempt %d failed: %s", attempt + 1, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

        return filename, 0

    async def upload_from_url(
        self,
        url: str,
        lifetime: int = 100,
        progress_cb: Optional[Callable[[str, int], Awaitable[None]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        if lifetime not in VALID_LIFETIMES:
            lifetime = 100

        server = await self.get_server()
        token = uuid.uuid1().hex
        tmp_path = None

        try:
            actual_download_url = url
            gigafile_match = re.search(r'https?://(\d+)\.gigafile\.nu/', url)

            connector = aiohttp.TCPConnector(ssl=False, limit=0, force_close=False)
            session = aiohttp.ClientSession(connector=connector)

            try:
                if gigafile_match:
                    if '/download.php' in url:
                        m = re.search(r'file=([^&]+)', url)
                        file_id = m.group(1) if m else None
                        server_host = url.split('/')[2]
                        page_url = f"https://{server_host}/{file_id}"
                    else:
                        page_url = url.split('?')[0]
                        file_id = page_url.rstrip('/').split('/')[-1]
                        server_host = page_url.split('/')[2]
                        actual_download_url = f"https://{server_host}/download.php?file={file_id}"
                    async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=15)) as _:
                        pass

                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp_path = tmp.name

                # Download with retry and stall detection
                filename, downloaded = await self._download_with_retry(
                    actual_download_url, tmp_path, progress_cb, cancel_event, session
                )
            finally:
                await session.close()

            if cancel_event and cancel_event.is_set():
                return {'success': False, 'error': 'cancelled'}

            if downloaded == 0 and os.path.getsize(tmp_path) == 0:
                return {'success': False, 'error': 'Download failed - empty file'}

            # Upload phase - STREAMING from disk (memory-safe)
            file_size = os.path.getsize(tmp_path)
            total_chunks = max(1, math.ceil(file_size / CHUNK_SIZE))

            upload_connector = aiohttp.TCPConnector(limit=UPLOAD_CONCURRENCY + 2, force_close=False)
            async with aiohttp.ClientSession(connector=upload_connector) as up_session:
                result_url = await self._upload_chunks_streaming(
                    up_session, server, token, filename, tmp_path,
                    total_chunks, lifetime, progress_cb, cancel_event
                )

            if progress_cb:
                await progress_cb('upload', 100)

            return self._build_result(result_url, server, filename)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    async def upload_file_path(
        self,
        filepath: str,
        lifetime: int = 100,
        progress_cb: Optional[Callable[[str, int], Awaitable[None]]] = None,
        original_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        server = await self.get_server()
        token = uuid.uuid1().hex
        filename = original_filename or os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        total_chunks = max(1, math.ceil(file_size / CHUNK_SIZE))

        # STREAMING upload - reads from disk on-demand (memory-safe)
        upload_connector = aiohttp.TCPConnector(limit=UPLOAD_CONCURRENCY + 2, force_close=False)
        async with aiohttp.ClientSession(connector=upload_connector) as session:
            result_url = await self._upload_chunks_streaming(
                session, server, token, filename, filepath,
                total_chunks, lifetime, progress_cb
            )

        if progress_cb:
            await progress_cb('upload', 100)

        return self._build_result(result_url, server, filename)

    def _build_result(
        self,
        page_url: Optional[str],
        server: str,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not page_url:
            return {'success': False, 'error': 'Upload failed - no URL returned'}

        file_id = page_url.rsplit('/', 1)[-1]
        base = page_url.rsplit('/', 1)[0]
        direct_url = f"{base}/download.php?file={file_id}"

        return {
            'success': True,
            'page_url': page_url,
            'direct_url': direct_url,
            'file_id': file_id,
            'server': server,
            'filename': filename,
        }


gigafile_client = GigaFileClient()
