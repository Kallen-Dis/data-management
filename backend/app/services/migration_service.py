import json
from copy import deepcopy
from hashlib import sha256

from app.db import legacy_question_bindings, responses, surveys
from app.services import question_service


def snapshot_identity(question):
    return {"qid": question["qid"], "type": question["type"], "title": question.get("title", ""), "options": question.get("options", [])}


def fingerprint(question):
    return sha256(json.dumps(snapshot_identity(question), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def migrate_stage2(dry_run=True):
    seen_bindings = set()
    report = {"dry_run": dry_run, "surveys_scanned": 0, "surveys_updated": 0, "current_questions": 0,
        "legacy_bindings": 0, "verified_bindings": 0, "snapshot_only_bindings": 0, "conflicts": []}
    for survey in surveys().find({}):
        report["surveys_scanned"] += 1
        missing = [question for question in survey.get("questions", []) if not question.get("question_version_id")]
        report["current_questions"] += len(missing)
        locked = bool(survey.get("ever_published") or survey.get("published_at") or survey.get("status") in ("published", "closed") or responses().find_one({"survey_id": survey["_id"]}, {"_id": 1}))
        if not missing and survey.get("schema_version") == 2 and survey.get("ever_published", False) == locked:
            continue
        report["surveys_updated"] += 1
        if dry_run:
            continue
        questions = deepcopy(survey.get("questions", []))
        for question in questions:
            if question.get("question_version_id"):
                continue
            series, version = question_service.create_series(question, {"_id": survey["owner_id"]}, listed=True,
                origin_key=f"legacy-current:{survey['_id']}:{survey['version']}:{question['qid']}", completeness="legacy_current")
            question.update({"question_series_id": series["_id"], "question_version_id": version["_id"]})
        if surveys().update_one({"_id": survey["_id"], "version": survey["version"], "questions": survey.get("questions", [])},
            {"$set": {"questions": questions, "schema_version": 2, "ever_published": locked}}).matched_count != 1:
            report["conflicts"].append(str(survey["_id"]))
    for response in responses().find({"snapshot.questions": {"$elemMatch": {"question_version_id": {"$exists": False}}}}):
        if str(response["survey_id"]) in report["conflicts"]:
            continue
        survey = surveys().find_one({"_id": response["survey_id"]})
        if survey is None:
            report["conflicts"].append(f"orphan-response:{response['_id']}")
            continue
        for question in response.get("snapshot", {}).get("questions", []):
            if question.get("question_version_id"):
                continue
            source = {"survey_id": response["survey_id"], "survey_version": response["survey_version"],
                "qid": question["qid"], "snapshot_fingerprint": fingerprint(question)}
            binding_key = tuple(source.values())
            if binding_key in seen_bindings or legacy_question_bindings().find_one(source):
                continue
            seen_bindings.add(binding_key)
            report["legacy_bindings"] += 1
            current = next((item for item in survey.get("questions", []) if item["qid"] == question["qid"]), None)
            verified = bool(current and response["survey_version"] == survey["version"] and snapshot_identity(current) == snapshot_identity(question))
            report["verified_bindings" if verified else "snapshot_only_bindings"] += 1
            if dry_run:
                continue
            if verified:
                series_id, version_id = current["question_series_id"], current["question_version_id"]
            else:
                series, version = question_service.create_series(question, {"_id": survey["owner_id"]}, change_note="第一阶段历史答卷导入，原始约束未知",
                    origin_key=f"legacy-response:{response['survey_id']}:{response['survey_version']}:{question['qid']}:{source['snapshot_fingerprint']}", completeness="snapshot_only")
                series_id, version_id = series["_id"], version["_id"]
            legacy_question_bindings().update_one(source, {"$setOnInsert": {**source, "snapshot": snapshot_identity(question),
                "question_series_id": series_id, "question_version_id": version_id,
                "confidence": "verified_revision" if verified else "snapshot_only", "created_at": question_service.now()}}, upsert=True)
    return report
