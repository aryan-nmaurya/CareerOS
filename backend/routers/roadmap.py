import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ai.client import AIClient, get_ai_client
from db.session import get_db
from schemas.roadmap import ModuleToggle, ModuleToggleOut, ProgressOut, RoadmapOut
from services import roadmap_service
from services.progress_service import build_progress
from services.roadmap_service import ModuleNotFoundError, RoadmapNotFoundError

router = APIRouter(tags=["roadmap"])

_ROADMAP_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "roadmap_not_found", "message": "No roadmap exists for that track yet."},
)
_MODULE_MISSING = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "module_not_found", "message": "That module does not exist."},
)


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/api/tracks/{track_id}/roadmap/stream")
def generate_roadmap(
    track_id: int,
    db: Session = Depends(get_db),
    ai_client: AIClient = Depends(get_ai_client),
):
    def event_stream():
        # A client can reconnect after the model has finished but before the
        # final SSE frame reaches it. Do not spend another model call or
        # overwrite a completed roadmap in that case.
        try:
            existing = roadmap_service.get_roadmap_by_track(db, track_id)
        except RoadmapNotFoundError:
            existing = None
        if existing is not None:
            yield _format_sse("done", {"roadmap_id": existing.id})
            return
        for event, data in roadmap_service.stream_roadmap(db, ai_client, track_id):
            yield _format_sse(event, data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/api/tracks/{track_id}/roadmap", response_model=RoadmapOut)
def get_roadmap(track_id: int, db: Session = Depends(get_db)):
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, track_id)
    except RoadmapNotFoundError:
        raise _ROADMAP_MISSING
    return roadmap_service.to_roadmap_out(roadmap)


@router.patch("/api/modules/{module_id}", response_model=ModuleToggleOut)
def patch_module(module_id: int, payload: ModuleToggle, db: Session = Depends(get_db)):
    try:
        module = roadmap_service.toggle_module(db, module_id, payload.completed)
    except ModuleNotFoundError:
        raise _MODULE_MISSING
    return roadmap_service.to_module_toggle_out(module)


@router.get("/api/tracks/{track_id}/progress", response_model=ProgressOut)
def get_progress(track_id: int, db: Session = Depends(get_db)):
    try:
        roadmap = roadmap_service.get_roadmap_by_track(db, track_id)
    except RoadmapNotFoundError:
        raise _ROADMAP_MISSING
    return ProgressOut(**build_progress(roadmap.phases))
