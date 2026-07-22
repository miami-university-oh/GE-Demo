import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

# HLS players reload playlists several times a second; one log line each buries everything.
logging.getLogger("httpx").setLevel(logging.WARNING)

# mediamtx serves HLS on this container-internal port (see mediamtx.yml).
# Only the backend talks to it, so the dashboard needs just port 8000 exposed.
MEDIAMTX_HLS_URL = "http://127.0.0.1:8888"

cam02_router = APIRouter()

hls_client = httpx.AsyncClient(base_url=MEDIAMTX_HLS_URL, timeout=10.0)


@cam02_router.get("/cam02/{file_path:path}")
async def cam02_hls(file_path: str, request: Request):
    # Low-latency HLS uses query params for blocking playlist reloads; forward them.
    url = f"/cam02/{file_path}"
    if request.url.query:
        url += f"?{request.url.query}"
    try:
        upstream = await hls_client.get(url)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="cam02 stream proxy unavailable")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
