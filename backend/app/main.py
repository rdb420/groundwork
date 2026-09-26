import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import SessionLocal, init_db
from .routers import admin, artifacts, auth, boards, live, ontology, processes
from .seed import seed_processes

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_processes(db)
    yield


app = FastAPI(title="Groundwork", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
for r in (auth.router, artifacts.router, processes.router, boards.router, live.router, admin.router, ontology.router):
    app.include_router(r)

# Sent by the app itself so every deployment option has them, with or without Caddy. Everything,
# fonts included, comes from this origin.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "font-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
       "connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
                    "Permissions-Policy": "camera=(), geolocation=(), microphone=(self)"}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if not request.url.path.startswith("/api/docs"):  # the API explorer loads its own scripts
        response.headers.setdefault("Content-Security-Policy", CSP)
    return response


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built frontend when it sits next to the backend (single-container deploy).
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
