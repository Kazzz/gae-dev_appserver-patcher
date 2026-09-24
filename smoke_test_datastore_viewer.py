#!/usr/bin/env python3
"""Datastore Viewerの種類一覧取得でCompiledQueryを使わないことを確認します。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest import mock


def main() -> int:
    """種類一覧の取得条件と結果を検証します。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path)
    args = parser.parse_args()

    appengine_root = args.sdk_root.resolve() / "platform" / "google_appengine"
    sys.path.insert(0, str(appengine_root))
    import wrapper_util

    sys.path[1:1] = wrapper_util.Paths(str(appengine_root)).script_paths(
        "dev_appserver.py"
    )
    from google.appengine.tools.devappserver2.admin import datastore_viewer

    class FakeKey:
        """種類名を返すキーです。"""

        def __init__(self, name: str) -> None:
            self._name = name

        def name(self) -> str:
            return self._name

    query = mock.Mock()
    query.Get.return_value = [FakeKey("Zoo"), FakeKey("Alpha")]
    with mock.patch.object(datastore_viewer.datastore, "Query", return_value=query) as make_query:
        kinds = datastore_viewer.DatastoreRequestHandler._get_kinds("local-test")

    make_query.assert_called_once_with(
        datastore_viewer.metadata.Kind.kind(),
        _namespace="local-test",
        keys_only=True,
        compile=False,
    )
    query.Get.assert_called_once_with(10000, 0)
    if kinds != ["Alpha", "Zoo"]:
        raise AssertionError(f"種類一覧が正しくありません: {kinds}")

    rows = [object() for _ in range(21)]
    query = mock.Mock()
    query.Get.return_value = rows
    with mock.patch.object(datastore_viewer.datastore, "Query", return_value=query) as make_query:
        entities, visible_total = datastore_viewer._get_entities(
            "Sample", "local-test", None, 0, 20
        )
    make_query.assert_called_once_with(
        "Sample", _namespace="local-test", compile=False
    )
    query.Get.assert_called_once_with(21, 0)
    query.Count.assert_not_called()
    if entities != rows[:20] or visible_total != 21:
        raise AssertionError("次ページを含む一覧件数が正しくありません")

    print("Datastore Viewerの種類一覧とエンティティ一覧を確認しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
