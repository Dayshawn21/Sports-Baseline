from starlette.applications import Starlette
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.main import app


def _app_gzip_options() -> dict[str, int]:
    [middleware] = [m for m in app.user_middleware if m.cls is GZipMiddleware]
    return dict(middleware.kwargs)


def test_large_json_is_gzipped_when_the_client_accepts_it() -> None:
    client = TestClient(app)
    plain = client.get("/openapi.json", headers={"Accept-Encoding": "identity"})
    zipped = client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})

    assert "content-encoding" not in plain.headers
    assert zipped.headers["content-encoding"] == "gzip"
    assert "Accept-Encoding" in zipped.headers["vary"]
    assert zipped.content == plain.content
    assert zipped.num_bytes_downloaded < len(plain.content) / 3


def test_the_compression_level_stays_below_the_cpu_heavy_default() -> None:
    assert _app_gzip_options() == {"compresslevel": 4}


def test_event_streams_are_never_compressed() -> None:
    async def frames():
        yield b"data: " + b"x" * 5000 + b"\n\n"

    async def stream(_request):
        return StreamingResponse(frames(), media_type="text/event-stream")

    sse_app = Starlette(routes=[Route("/stream", stream)])
    sse_app.add_middleware(GZipMiddleware, **_app_gzip_options())

    res = TestClient(sse_app).get("/stream", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in res.headers
    assert res.text.startswith("data: x")
