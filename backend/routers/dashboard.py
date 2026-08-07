from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.dashboard import DashboardOut
from services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard_service.get_dashboard(db)
