import json
import zipfile
from contextlib import nullcontext
from uuid import uuid4

import pytest
from bson import BSON

from app.db import get_db
from scripts.migrate_stage2 import backup_database, collection_digest
from scripts import restore_backup
from tests.test_stage2_services import legacy_fixture, owner


def test_backup_restore_preserves_bson_and_refuses_existing_target(tmp_path, monkeypatch):
    database = get_db()
    _, original = legacy_fixture(owner())
    backup = tmp_path / "before-migration.zip"
    backup_database(database, backup)
    target = f"survey_restore_{uuid4().hex}_test"
    monkeypatch.setattr(restore_backup, "MongoClient", lambda uri: nullcontext(database.client))
    try:
        report = restore_backup.restore_database(backup, "unused", target)
        assert report["restored"]["responses"] == 1
        assert BSON.encode(database.client[target].responses.find_one({"_id": original["_id"]})) == BSON.encode(original)
        assert collection_digest(database.responses) == collection_digest(database.client[target].responses)
        with pytest.raises(ValueError, match="必须为空"):
            restore_backup.restore_database(backup, "unused", target)
        with pytest.raises(ValueError, match="不允许覆盖"):
            restore_backup.restore_database(backup, "unused", database.name)
    finally:
        database.client.drop_database(target)


def test_corrupted_backup_is_rejected_before_database_connection(tmp_path, monkeypatch):
    database = get_db()
    legacy_fixture(owner())
    backup = tmp_path / "source.zip"
    corrupted = tmp_path / "corrupted.zip"
    backup_database(database, backup)
    with zipfile.ZipFile(backup) as source, zipfile.ZipFile(corrupted, "x") as output:
        for name in source.namelist():
            content = source.read(name)
            if name == "manifest.json":
                manifest = json.loads(content)
                manifest["collections"]["responses"]["sha256"] = "invalid"
                content = json.dumps(manifest).encode()
            output.writestr(name, content)
    def unexpected_connection(uri):
        pytest.fail("损坏备份不应连接数据库")
    monkeypatch.setattr(restore_backup, "MongoClient", unexpected_connection)
    with pytest.raises(ValueError, match="备份校验失败"):
        restore_backup.restore_database(corrupted, "unused", "unused_restore_test")
