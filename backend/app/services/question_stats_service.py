from datetime import timezone

from fastapi import HTTPException

from app.db import legacy_question_bindings, responses, surveys
from app.serialization import document_view, json_value, object_id
from app.services import question_service


def _count(facets, name):
    return facets[name][0]["count"] if facets[name] else 0


def version_stats(version_id, user, survey_ids=None, start=None, end=None, offset=0, limit=30):
    version, _ = question_service.get_version(version_id, user)
    target = version["_id"]
    bindings = list(legacy_question_bindings().find({"question_version_id": target}))
    mapped_ids = list({binding["survey_id"] for binding in bindings})
    authorized = list(surveys().find({"$or": [
        {"owner_id": user["_id"], "$or": [{"questions.question_version_id": target}, {"_id": {"$in": mapped_ids}}]},
        {"question_stats_shares": {"$elemMatch": {"question_version_id": target, "grantee_id": user["_id"], "permission": "aggregate"}}},
    ]}, {"owner_id": 1}))
    allowed_ids = [document["_id"] for document in authorized]
    if survey_ids:
        selected = list(dict.fromkeys(object_id(value) for value in survey_ids))
        if not set(selected).issubset(set(allowed_ids)):
            raise HTTPException(403, "所选问卷超出统计授权范围")
        allowed_ids = selected
    own_ids = [document["_id"] for document in authorized if document["owner_id"] == user["_id"] and document["_id"] in allowed_ids]
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start and end and start > end:
        raise HTTPException(400, "开始时间不能晚于结束时间")
    document_filter = {"survey_id": {"$in": allowed_ids}}
    if start or end:
        document_filter["submitted_at"] = {}
        if start:
            document_filter["submitted_at"]["$gte"] = start
        if end:
            document_filter["submitted_at"]["$lte"] = end
    targets = [{"snapshot.questions.question_version_id": target}]
    for binding in bindings:
        if binding["survey_id"] not in allowed_ids:
            continue
        condition = {"survey_id": binding["survey_id"], "survey_version": binding["survey_version"],
            "snapshot.questions.question_version_id": {"$exists": False}}
        condition.update({f"snapshot.questions.{key}": value for key, value in binding["snapshot"].items()})
        targets.append(condition)
    pipeline = [{"$match": document_filter}, {"$unwind": "$snapshot.questions"}, {"$match": {"$or": targets}},
        {"$set": {"answer_entry": {"$arrayElemAt": [{"$filter": {"input": {"$objectToArray": "$answers"}, "as": "entry", "cond": {"$eq": ["$$entry.k", "$snapshot.questions.qid"]}}}, 0]}}},
        {"$set": {"answer": "$answer_entry.v"}}, {"$match": {"answer": {"$exists": True}, "$expr": {"$not": [{"$in": ["$answer", [None, "", []]]}]}}}]
    content = version["content"]
    if content["type"] in ("single", "multiple"):
        pipeline.extend([{"$set": {"answer": {"$cond": [{"$isArray": "$answer"}, {"$setIntersection": ["$answer", content.get("options", [])]}, []]}}},
            {"$match": {"$expr": {"$gt": [{"$size": "$answer"}, 0]}}}])
        if content["type"] == "single":
            pipeline.append({"$match": {"$expr": {"$eq": [{"$size": "$answer"}, 1]}}})
    elif content["type"] == "number":
        pipeline.extend([{"$match": {"$expr": {"$in": [{"$type": "$answer"}, ["int", "long", "double", "decimal", "string"]]}}},
            {"$set": {"numeric": {"$convert": {"input": "$answer", "to": "double", "onError": None, "onNull": None}}}},
            {"$match": {"numeric": {"$ne": None, "$gte": -1.7976931348623157e308, "$lte": 1.7976931348623157e308}}}])
    else:
        pipeline.append({"$match": {"answer": {"$type": "string"}}})
    facets = {"answers": [{"$count": "count"}], "responses": [{"$group": {"_id": "$_id"}}, {"$count": "count"}],
        "surveys": [{"$group": {"_id": "$survey_id"}}, {"$count": "count"}]}
    if content["type"] in ("single", "multiple"):
        facets["choices"] = [{"$unwind": "$answer"}, {"$group": {"_id": "$answer", "count": {"$sum": 1}}}]
    if content["type"] == "number":
        facets["numbers"] = [{"$group": {"_id": None, "num_count": {"$sum": 1}, "num_sum": {"$sum": "$numeric"}, "avg": {"$avg": "$numeric"}, "min": {"$min": "$numeric"}, "max": {"$max": "$numeric"}}}]
        facets["histogram"] = [{"$bucketAuto": {"groupBy": "$numeric", "buckets": 8}}]
    if content["type"] == "text":
        own_filter = {"$match": {"survey_id": {"$in": own_ids}}}
        facets["texts"] = [own_filter, {"$sort": {"submitted_at": -1, "_id": -1, "snapshot.questions.qid": 1}}, {"$skip": offset}, {"$limit": limit},
            {"$project": {"_id": 0, "answer": 1, "submitted_at": 1, "survey_id": 1, "qid": "$snapshot.questions.qid"}}]
        facets["text_total"] = [own_filter, {"$count": "count"}]
    aggregate = list(responses().aggregate([*pipeline, {"$facet": facets}]))[0]
    result = {"version": document_view(version), "content": content, "answer_count": _count(aggregate, "answers"),
        "response_count": _count(aggregate, "responses"), "survey_count": _count(aggregate, "surveys"), "authorized_survey_count": len(allowed_ids),
        "includes_shared_aggregates": any(value not in own_ids for value in allowed_ids), "scope": "仅包含自己的问卷与明确授权的聚合统计", "counting_unit": "题目实例作答次数"}
    if "choices" in aggregate:
        counts = {row["_id"]: row["count"] for row in aggregate["choices"]}
        result.update({"options": content.get("options", []), "counts": [counts.get(option, 0) for option in content.get("options", [])]})
    if "numbers" in aggregate:
        numbers = aggregate["numbers"][0] if aggregate["numbers"] else {"num_count": 0, "num_sum": 0, "avg": None, "min": None, "max": None}
        result.update({key: value for key, value in numbers.items() if key != "_id"})
        result["histogram"] = [{"min": row["_id"]["min"], "max": row["_id"]["max"], "count": row["count"]} for row in aggregate["histogram"]]
    if "texts" in aggregate:
        result["texts"] = {"items": aggregate["texts"], "total": _count(aggregate, "text_total"), "offset": offset, "limit": limit,
            "restricted_count": result["answer_count"] - _count(aggregate, "text_total")}
    return json_value(result)
