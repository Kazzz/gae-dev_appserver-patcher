#!/usr/bin/env python3
"""GCSアップロードの分割データをクエリなしで確定できるか検証します。"""

from __future__ import annotations

import argparse
import ast
import io
from pathlib import Path


def load_get_content(sdk_root: Path, partial_model: type):
    """SDKの_get_content本体を副作用なしで取り出します。"""

    path = (
        sdk_root
        / "platform/google_appengine/lib/cloudstorage/cloudstorage/cloudstorage_stub.py"
    )
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    stub_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "CloudStorageStub"
    )
    function = next(
        node
        for node in stub_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_get_content"
    )
    function.decorator_list = []
    extracted = ast.Module(body=[function], type_ignores=[])
    namespace = {"_AE_GCSPartialFile_": partial_model}
    exec(compile(extracted, str(path), "exec"), namespace)
    return namespace["_get_content"]


def main() -> int:
    """分割データと欠損時の扱いを確認します。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path)
    args = parser.parse_args()

    class FakePart:
        """分割データのメタデータです。"""

        def __init__(self, start: int, end: int, blob_key: str) -> None:
            self.start = start
            self.end = end
            self.partial_content = blob_key
            self.deleted = False

        def key(self):
            return self

        def name(self) -> str:
            return f"{self.start:020d}"

        def delete(self) -> None:
            self.deleted = True

    parts = {
        "00000000000000000000": FakePart(0, 7, "part-0"),
        "00000000000000000007": FakePart(7, 12, "part-1"),
    }

    class FakeQuery:
        """従来のDatastore列挙で空になるケースを模擬します。"""

        def ancestor(self, unused_parent):
            return self

        def order(self, unused_key):
            return []

    class FakePartials:
        """キーによる取得では保存済みデータを返します。"""

        @staticmethod
        def all(namespace):
            assert namespace == ""
            return FakeQuery()

        @staticmethod
        def get_by_key_name(name, parent):
            assert parent is file_info
            return parts.get(name)

    class FakeStorage:
        """2個の分割データを保持します。"""

        def __init__(self) -> None:
            self.deleted = []

        def OpenBlob(self, key):
            return io.BytesIO({"part-0": b"payload", "part-1": b"chunk"}[key])

        def DeleteBlob(self, key):
            self.deleted.append(key)

    class FakeFileInfo:
        """確定対象のアップロードです。"""

        next_offset = 12

        def __init__(self) -> None:
            self.deleted = False

        def delete(self) -> None:
            self.deleted = True

    file_info = FakeFileInfo()
    storage = FakeStorage()
    stub = type("FakeStub", (), {"blob_storage": storage})()
    get_content = load_get_content(args.sdk_root.resolve(), FakePartials)
    error, content = get_content(stub, file_info)
    if error or content != b"payloadchunk" or storage.deleted != ["part-0", "part-1"]:
        raise AssertionError("分割データをBlobへ集約できませんでした")
    if not all(part.deleted for part in parts.values()):
        raise AssertionError("確定済みの分割メタデータが残っています")

    parts.pop("00000000000000000007")
    file_info.deleted = False
    error, content = get_content(stub, file_info)
    if not error or content or not file_info.deleted:
        raise AssertionError("分割データの欠損を検出できませんでした")

    print("GCS分割データの集約を確認しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
