#!/usr/bin/env python3
"""Go runtime の環境変数が Windows の子プロセスへ渡せる型か確認します。"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def main() -> int:
    """Go のプロセス起動直前に生成される環境変数を確認します。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path)
    args = parser.parse_args()

    appengine_root = args.sdk_root.resolve() / "platform" / "google_appengine"
    sys.path.insert(0, str(appengine_root))
    import wrapper_util

    sys.path[1:1] = wrapper_util.Paths(str(appengine_root)).script_paths(
        "dev_appserver.py"
    )
    from google.appengine.tools.devappserver2 import runtime_config_pb2
    from google.appengine.tools.devappserver2.go import instance_factory

    runtime_config = runtime_config_pb2.Config()
    variable = runtime_config.environ.add()
    variable.key = b"LOCAL_TEST_KEY"
    variable.value = b"LOCAL_TEST_VALUE"

    factory = instance_factory.GoRuntimeInstanceFactory.__new__(
        instance_factory.GoRuntimeInstanceFactory
    )
    factory._application_lock = threading.Lock()
    factory._go_application = SimpleNamespace(
        maybe_build=lambda _: False,
        get_environment=lambda: {"BASE": "value"},
        go_executable="go.exe",
    )
    factory._runtime_config_getter = lambda: runtime_config
    factory._module_configuration = object()
    factory._start_process_flavor = 0
    factory._modified_since_last_build = False
    factory._last_build_error = None
    factory.request_data = None
    factory.max_concurrent_requests = 8
    factory.max_background_threads = 10

    captured: dict[str, str] = {}

    def capture_proxy(_executable, _config_getter, _module, environ, **_kwargs):
        captured.update(environ)
        return object()

    with mock.patch.object(
        instance_factory.http_runtime, "HttpRuntimeProxy", side_effect=capture_proxy
    ), mock.patch.object(instance_factory.instance, "Instance", return_value=object()):
        factory.new_instance("0")

    if captured.get("LOCAL_TEST_KEY") != "LOCAL_TEST_VALUE" or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in captured.items()
    ):
        raise AssertionError("Go runtime の環境変数に文字列以外が含まれています")

    print("Go runtime の環境変数を文字列として渡せます。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
