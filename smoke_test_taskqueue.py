#!/usr/bin/env python3
"""Transactional Task Queue要求のPython 3 protobuf変換を確認します。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """コマンドライン引数を解析します。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path, help="Google Cloud SDKのルート")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """TaskQueueBulkAddRequestがgRPC要求へ変換できることを確認します。"""

    args = parse_args(argv)
    appengine_root = args.sdk_root.resolve() / "platform" / "google_appengine"
    sys.path.insert(0, str(appengine_root))

    try:
        import wrapper_util

        paths = wrapper_util.Paths(str(appengine_root))
        sys.path[1:1] = paths.script_paths("dev_appserver.py")
        from google.appengine.api import api_base_pb2
        from google.appengine.api.taskqueue import taskqueue_service_bytes_pb2
        from google.appengine.tools.devappserver2 import datastore_grpc_stub
        from google.appengine.tools.devappserver2 import grpc_service_pb2
    except ImportError as error:
        print(
            "エラー: dev_appserverが使用するPython環境で実行してください: "
            f"{error}",
            file=sys.stderr,
        )
        return 1

    request = taskqueue_service_bytes_pb2.TaskQueueBulkAddRequest()
    if hasattr(request, "Encode"):
        print("エラー: Python 3 protobuf要求に想定外のEncode()があります", file=sys.stderr)
        return 1

    class FakeCallHandler:
        """Datastore Emulatorへ渡すgRPC要求を記録します。"""

        def __init__(self) -> None:
            self.request = None

        def HandleCall(self, grpc_request, unused_timeout):
            """空の正常応答を返します。"""

            del unused_timeout
            self.request = grpc_request
            return grpc_service_pb2.Response(response=b"")

    handler = FakeCallHandler()
    stub = datastore_grpc_stub.DatastoreGrpcStub("localhost:1")
    stub._call_handler_stub = handler
    stub.MakeSyncCall(
        "datastore_v3",
        "AddActions",
        request,
        api_base_pb2.VoidProto(),
    )

    if handler.request is None or handler.request.request != request.SerializeToString():
        print("エラー: protobufのシリアライズ結果が一致しません", file=sys.stderr)
        return 1

    print("Transactional Task Queue要求をPython 3 protobufでシリアライズできました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
