import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from bson import BSON

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def collection_digest(collection):
    digest = sha256()
    count = 0
    for document in collection.find({}).sort("_id", 1):
        digest.update(BSON.encode(document))
        count += 1
    return {"count": count, "sha256": digest.hexdigest()}


def backup_database(database, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"database": database.name, "created_at": datetime.now(timezone.utc).isoformat(), "collections": {}}
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in database.list_collection_names():
            digest = sha256()
            count = 0
            with archive.open(f"{name}.bson", "w") as output:
                for document in database[name].find({}).sort("_id", 1):
                    encoded = BSON.encode(document)
                    output.write(encoded)
                    digest.update(encoded)
                    count += 1
            manifest["collections"][name] = {"count": count, "sha256": digest.hexdigest()}
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return str(target)


def main():
    parser = argparse.ArgumentParser(description="第二阶段兼容迁移：默认只读试运行；--apply 前自动生成 BSON 备份")
    parser.add_argument("--database", required=True)
    parser.add_argument("--uri", default="mongodb://127.0.0.1:27017")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup")
    args = parser.parse_args()
    import app.config as config
    config.DB_NAME = args.database
    config.MONGODB_URI = args.uri
    from app.db import get_db, init_db
    from app.services.migration_service import migrate_stage2
    database = get_db()
    before = collection_digest(database["responses"])
    backup = None
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = Path(args.backup) if args.backup else Path(__file__).resolve().parents[2] / ".backups" / f"{args.database}-{stamp}.zip"
        backup = backup_database(database, target)
        init_db()
    report = migrate_stage2(dry_run=not args.apply)
    report.update({"database": database.name, "backup": backup, "responses_before": before,
        "responses_after": collection_digest(database["responses"])})
    report["responses_unchanged"] = report["responses_before"] == report["responses_after"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["conflicts"] or not report["responses_unchanged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
