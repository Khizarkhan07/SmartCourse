import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

#nginix trafik

from config import ROUTE_TABLE, settings
from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing

configure_logging()
configure_tracing()

logger = get_logger(__name__)

app = FastAPI(title=settings.SERVICE_NAME)



# These prefixes all route to the same multi-resource service (course-service).
# We forward the FULL path so the service can discriminate by resource type
# (/courses/{id} vs /modules/{id} vs /lessons/{id}).
_FULL_PATH_PREFIXES = frozenset({"courses", "modules", "lessons", "enrollments"})


def _resolve(path: str) -> tuple[str, str] | None:
    """Return (backend_base_url, forwarded_path) for a given incoming path, or None if unroutable.

    Routes by the first path segment. If the segment matches a service in
    ROUTE_TABLE the prefix is stripped and the request goes to that service.
    Prefixes in _FULL_PATH_PREFIXES are forwarded with the full path intact
    so multi-resource services can route by resource type.
    Returns None for any path that doesn't match a known service.
    """
    parts = path.lstrip("/").split("/", 1)
    prefix = parts[0]
    rest = "/" + parts[1] if len(parts) > 1 else "/"

    if prefix in ROUTE_TABLE:
        if prefix in _FULL_PATH_PREFIXES:
            return ROUTE_TABLE[prefix], "/" + path.lstrip("/")
        return ROUTE_TABLE[prefix], rest

    return None


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": settings.SERVICE_NAME}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    resolved = _resolve(path)
    if resolved is None:
        raise HTTPException(status_code=404, detail="No service registered for this path")
    backend, forwarded_path = resolved
    url = f"{backend}{forwarded_path}"

    # Strip host header so the backend doesn't see the gateway's hostname
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    logger.info(
        "proxying request",
        method=request.method,
        original_path=path,
        backend=backend,
        forwarded_path=forwarded_path,
    )

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=await request.body(),
            params=request.query_params,
            follow_redirects=True,
            timeout=30.0,
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.headers.get("content-type"),
    )


FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
