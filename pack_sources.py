#!/usr/bin/env python3
"""
Pack all source files + documentation into a ZIP and upload to GigaFile.nu
Run: python3 pack_sources.py
"""
import asyncio
import os
import zipfile
import tempfile
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))
from gigafile_client import gigafile_client


INCLUDE_FILES = [
    ('backend/server.py',          'backend/server.py'),
    ('backend/gigafile_client.py', 'backend/gigafile_client.py'),
    ('backend/bot.py',             'backend/bot.py'),
    ('backend/requirements.txt',   'backend/requirements.txt'),
    ('pack_sources.py',            'pack_sources.py'),
]

DOCS_URL = (
    'https://customer-assets.emergentagent.com/job_680a770b-012c-4b55-819e-fe8ffb4515ad'
    '/artifacts/2ymmn5tz_GIGAFILE_NU_FULL_DOCUMENTATION.md'
)


async def main():
    root = Path(__file__).parent
    tmp = tempfile.mktemp(suffix='.zip')

    print("📦 Packing source files...")
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zf:
        for src, arc in INCLUDE_FILES:
            full = root / src
            if full.exists():
                zf.write(full, arc)
                print(f"  + {arc}")
            else:
                print(f"  ! missing: {arc}")

        # Download and include documentation
        print("  + fetching documentation...")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(DOCS_URL) as r:
                    doc_bytes = await r.read()
            zf.writestr('GIGAFILE_NU_FULL_DOCUMENTATION.md', doc_bytes)
            print("  + GIGAFILE_NU_FULL_DOCUMENTATION.md")
        except Exception as e:
            print(f"  ! docs fetch failed: {e}")

    size_kb = os.path.getsize(tmp) / 1024
    print(f"\nZIP size: {size_kb:.1f} KB")
    print("\n⬆️  Uploading to GigaFile.nu (lifetime=100 days)...")

    result = await gigafile_client.upload_file_path(tmp, lifetime=100)
    os.unlink(tmp)

    if result.get('success'):
        backend_url = os.environ.get('BACKEND_URL', 'http://localhost:8001')
        proxy_url = f"{backend_url}/api/proxy?url={result['page_url']}"
        print("\n✅ Done!\n")
        print(f"📄 Page URL:     {result['page_url']}")
        print(f"⬇️  Direct URL:   {result['direct_url']}")
        print(f"🚀 Proxy URL:    {proxy_url}")
    else:
        print(f"\n❌ Upload failed: {result.get('error')}")


if __name__ == '__main__':
    asyncio.run(main())
