import argparse
import json
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

from bson import BSON, decode_file_iter
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def restore_database(archive_path, uri, target_name):
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if target_name == manifest["database"]:
            raise ValueError("请恢复到新的数据库名，不允许覆盖原数据库")
        for name, expected in manifest["collections"].items():
            digest = sha256()
            count = 0
            with archive.open(f"{name}.bson") as source:
                for document in decode_file_iter(source):
                    digest.update(BSON.encode(document))
                    count += 1
            if digest.hexdigest() != expected["sha256"] or count != expected["count"]:
                raise ValueError(f"备份校验失败：{name}")
        with MongoClient(uri) as client:
            database = client[target_name]
            if database.list_collection_names():
                raise ValueError("目标数据库必须为空；本工具不会删除或覆盖任何集合")
            restored = {}
            for name in manifest["collections"]:
                database.create_collection(name)
                restored[name] = 0
                with archive.open(f"{name}.bson") as source:
                    for document in decode_file_iter(source):
                        database[name].insert_one(document)
                        restored[name] += 1
    return {"database": target_name, "restored": restored, "note": "原始 BSON 已恢复；启动对应阶段应用以初始化索引和校验器"}


def main():
    parser = argparse.ArgumentParser(description="校验迁移备份并恢复到全新的数据库，禁止覆盖原库")
    parser.add_argument("archive")
    parser.add_argument("--database", required=True)
    parser.add_argument("--uri", default="mongodb://127.0.0.1:27017")
    args = parser.parse_args()
    print(json.dumps(restore_database(args.archive, args.uri, args.database), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
