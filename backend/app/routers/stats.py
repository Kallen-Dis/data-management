"""统计接口：整卷统计 / 单题统计 / 填写明细 / 快照重建统计。"""
from fastapi import APIRouter, Depends, HTTPException

from app.db import responses as responses_col
from app.deps import get_current_user
from app.routers.surveys import _get_owned
from app.services import stats_service

router = APIRouter(prefix="/api/surveys", tags=["stats"])


@router.get("/{survey_id}/stats")
def get_stats(survey_id: str, user: dict = Depends(get_current_user)):
    survey = _get_owned(survey_id, user)
    return stats_service.get_stats_view(survey)


@router.get("/{survey_id}/stats/{qid}")
def get_question_stats(survey_id: str, qid: str, user: dict = Depends(get_current_user)):
    survey = _get_owned(survey_id, user)
    view = stats_service.get_stats_view(survey)
    for q in view["questions"]:
        if q["qid"] == qid:
            return q
    raise HTTPException(404, "题目不存在")


@router.get("/{survey_id}/responses")
def list_responses(survey_id: str, user: dict = Depends(get_current_user)):
    """填写明细（文本题全量内容、数字题均值来源）。"""
    survey = _get_owned(survey_id, user)
    docs = responses_col().find({"survey_id": survey["_id"]}).sort("submitted_at", -1)
    return [
        {
            "answers": d.get("answers", {}),
            "snapshot": d.get("snapshot", {}),
            "submitted_at": d.get("submitted_at"),
            "spent_seconds": d.get("spent_seconds", 0),
            "respondent": {
                "user_id": str(d["respondent"]["user_id"]) if d.get("respondent", {}).get("user_id") else None,
                "username": d.get("respondent", {}).get("username"),
                "anon_id": d.get("respondent", {}).get("anon_id"),
            },
            "survey_version": d.get("survey_version"),
        }
        for d in docs
    ]


@router.post("/{survey_id}/stats/rebuild")
def rebuild_stats(survey_id: str, user: dict = Depends(get_current_user)):
    """基于 responses 快照全量重建 stats（兜底/校验用）。"""
    survey = _get_owned(survey_id, user)
    result = stats_service.rebuild_stats(survey["_id"])
    return result
