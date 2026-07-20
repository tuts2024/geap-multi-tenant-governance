"""
App entrypoint. Run locally with:
    uvicorn app.main:app --reload --port 8080
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import admin_router, auth_router, chat_router, oauth_router

import httpx
from fastapi import Request, Response

app = FastAPI(title="Contract Analyst Agent - Frontend")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router.router)
app.include_router(oauth_router.router)


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def proxy_orchestrator(request: Request, path: str):
    async with httpx.AsyncClient(timeout=120.0) as client:
        url = f"http://127.0.0.1:8082/api/v1/{path}"
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
        body = await request.body()
        try:
            resp = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type", "application/json"))
        except Exception as e:
            return Response(content=f'{{"status": "ERROR", "message": "{str(e)}"}}', status_code=502, media_type="application/json")
