

from __future__ import annotations

import asyncio
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
from model.captioner import VideoCaptioner
from model.pipeline import VideoPipeline
from model.scene_detector import SceneDetector


class CaptionRequest(BaseModel):
    url: str = Field(..., description="Video URL, file URL, or local path")


class CaptionEntry(BaseModel):
    start: float
    end: float
    text: str


class CaptionResponse(BaseModel):
    success: bool
    video_id: str
    video_serve_url: str
    duration: float
    captions: list[CaptionEntry]
    processing_time: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


class SiteResponse(BaseModel):
    name: str
    public_url: str
    api_health_url: str
    api_caption_url: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load heavy model objects once at startup."""
    print("[server] Initialising components...")
    app.state.captioner = None
    app.state.pipeline = None
    app.state.model_loaded = False
    app.state.startup_error = None

    try:
        captioner = VideoCaptioner()
        scene_detector = SceneDetector()
        pipeline = VideoPipeline(captioner, scene_detector)

        app.state.captioner = captioner
        app.state.pipeline = pipeline
        app.state.model_loaded = True
        print("[server] All components ready")
    except Exception as exc:
        app.state.startup_error = str(exc)
        print(f"[server] Startup error: {exc}")

    yield

    print("[server] Shutting down...")


app = FastAPI(
    title="Veauido",
    description="Video captioning powered by ViT + GPT-2",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.captioner = None
app.state.pipeline = None
app.state.model_loaded = False
app.state.startup_error = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )


@app.post(
    "/api/caption",
    response_model=CaptionResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def caption_video(body: CaptionRequest):
    """Accept a video source, run the full pipeline, and return captions."""
    if not getattr(app.state, "model_loaded", False) or app.state.pipeline is None:
        detail = getattr(app.state, "startup_error", None) or "Model is not loaded."
        raise HTTPException(status_code=503, detail=detail)

    source = body.url.strip()
    if not source:
        raise HTTPException(status_code=400, detail="URL must not be empty.")

    try:
        return await asyncio.to_thread(app.state.pipeline.process_video, source)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal processing error: {exc}")


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Readiness probe."""
    model_loaded = bool(getattr(app.state, "model_loaded", False))
    return {
        "status": "ready" if model_loaded else "not_ready",
        "model_loaded": model_loaded,
    }


@app.get("/api/site", response_model=SiteResponse)
async def site_info():
    """Deployment URL and API endpoints for the running instance."""
    base = config.PUBLIC_URL
    return {
        "name": "Veauido",
        "public_url": base,
        "api_health_url": f"{base}/api/health",
        "api_caption_url": f"{base}/api/caption",
    }


app.mount("/videos", StaticFiles(directory=str(config.VIDEOS_DIR)), name="videos")

frontend_dir = config.BASE_DIR / "frontend"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    