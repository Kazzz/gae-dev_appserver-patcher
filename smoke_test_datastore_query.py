#!/usr/bin/env python3
"""Datastoreクエリ応答のv3/v4互換性を確認します。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """通常応答、カーソル終端、結果付き応答を検証します。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path)
    args = parser.parse_args()

    appengine_root = args.sdk_root.resolve() / "platform" / "google_appengine"
    sys.path.insert(0, str(appengine_root))
    try:
        import wrapper_util

        sys.path[1:1] = wrapper_util.Paths(str(appengine_root)).script_paths(
            "dev_appserver.py"
        )
        from google.appengine.datastore import datastore_pb
        from google.appengine.datastore import datastore_stub_util
        from google.appengine.datastore import datastore_v4_pb2
        from google.appengine.tools.devappserver2 import datastore_grpc_stub
        from google.appengine.tools.devappserver2 import grpc_service_pb2
    except ImportError as error:
        print(f"エラー: dev_appserverのPython環境が必要です: {error}", file=sys.stderr)
        return 1

    parse = datastore_grpc_stub.DatastoreGrpcStub._ParseResponseWithCompatibility
    converter = datastore_stub_util.get_service_converter()

    normal = datastore_pb.QueryResult()
    normal.more_results = True
    normal.cursor.cursor = 42
    normal.cursor.app = "test-app"
    parsed = datastore_pb.QueryResult()
    parse("Next", parsed, normal.SerializeToString())
    if parsed != normal:
        raise AssertionError("通常のv3応答が変化しました")

    cursor_only = datastore_pb.QueryResult()
    cursor_only.cursor.cursor = 43
    parsed = datastore_pb.QueryResult()
    parse("Next", parsed, cursor_only.SerializeToString())
    if parsed != cursor_only:
        raise AssertionError("通常のv3カーソルが変化しました")

    for call in ("RunQuery", "Next"):
        if call == "RunQuery":
            v4_response = datastore_v4_pb2.RunQueryResponse()
        else:
            v4_response = datastore_v4_pb2.ContinueQueryResponse()
        v4_response.batch.more_results = (
            datastore_v4_pb2.QueryResultBatch.NO_MORE_RESULTS
        )
        parsed = datastore_pb.QueryResult()
        parse(call, parsed, v4_response.SerializeToString())
        if call == "RunQuery":
            expected = converter.v4_run_query_resp_to_v3_query_result(v4_response)
        else:
            expected = converter.v4_to_v3_query_result(v4_response.batch)
        if parsed != expected or parsed.HasField("cursor"):
            raise AssertionError(f"{call}のカーソル終端を変換できませんでした")

    continued = datastore_v4_pb2.ContinueQueryResponse()
    continued.batch.entity_result_type = datastore_v4_pb2.EntityResult.FULL
    entity = continued.batch.entity_result.add().entity
    entity.key.partition_id.dataset_id = "test-app"
    path_element = entity.key.path_element.add()
    path_element.kind = "Sample"
    path_element.id = 1
    continued.batch.more_results = datastore_v4_pb2.QueryResultBatch.NOT_FINISHED
    parsed = datastore_pb.QueryResult()
    parse("Next", parsed, continued.SerializeToString())
    expected = converter.v4_to_v3_query_result(continued.batch)
    if parsed != expected or len(parsed.result) != 1 or not parsed.more_results:
        raise AssertionError("結果を含むv4継続応答を変換できませんでした")

    class FakeCallHandler:
        """Datastore Emulatorからの応答を模擬します。"""

        def HandleCall(self, unused_request, unused_timeout):
            """カーソル終端応答を返します。"""

            del unused_request, unused_timeout
            terminal = datastore_v4_pb2.ContinueQueryResponse()
            terminal.batch.more_results = (
                datastore_v4_pb2.QueryResultBatch.NO_MORE_RESULTS
            )
            return grpc_service_pb2.Response(response=terminal.SerializeToString())

    stub = datastore_grpc_stub.DatastoreGrpcStub("localhost:1")
    stub._call_handler_stub = FakeCallHandler()
    parsed = datastore_pb.QueryResult()
    stub.MakeSyncCall("datastore_v3", "Next", datastore_pb.NextRequest(), parsed)
    if parsed.HasField("cursor") or parsed.more_results:
        raise AssertionError("gRPC経由のカーソル終端応答を変換できませんでした")

    try:
        parse("Next", datastore_pb.QueryResult(), b"\x0a\x01")
    except Exception:
        pass
    else:
        raise AssertionError("壊れた応答を正常扱いしました")

    print("Datastoreクエリ応答とカーソル終端の互換性を確認しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
