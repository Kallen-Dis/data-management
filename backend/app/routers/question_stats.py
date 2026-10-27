from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.deps import get_current_user
from app.services import question_service
from app.services.question_stats_service import version_stats

router = APIRouter(prefix="/api", tags=["cross-survey-statistics"])


@router.get("/question-versions/{version_id}/stats")
def get_version_stats(version_id: str, survey_ids: list[str] | None = Query(None), start: datetime | None = None,
                      end: datetime | None = None, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100), user=Depends(get_current_user)):
    return version_stats(version_id, user, survey_ids, start, end, offset, limit)


@router.get("/questions/{series_id}/stats")
def get_series_stats(series_id: str, user=Depends(get_current_user)):
    question = question_service.series_view(question_service.raw_series(series_id), user)
    return {"question": {"id": question["id"], "name": question["name"]}, "grouping": "按版本分别统计，不自动合并不同版本",
        "versions": [version_stats(version["id"], user) for version in question["versions"]]}
