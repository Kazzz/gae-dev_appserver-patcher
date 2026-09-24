#!/usr/bin/env python3
"""dev_appserverへ既知の互換パッチを安全に適用します。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class PatchDefinition:
    """検証済みパッチの定義です。"""

    patch_id: str
    description: str
    target_file: Path
    patch_file: Path
    original_sha256: str
    patched_sha256: str


def calculate_sha256(path: Path) -> str:
    """ファイルのSHA-256を返します。"""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_patch_blocks(path: Path) -> Tuple[str, str]:
    """単一ハンクの統一diffから適用前後の文字列を取得します。"""

    before: List[str] = []
    after: List[str] = []
    in_hunk = False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith("@@"):
            if in_hunk:
                raise ValueError(f"複数ハンクのパッチには対応していません: {path}")
            in_hunk = True
            continue
        if not in_hunk or line.startswith("\\ No newline"):
            continue
        if line.startswith(" "):
            before.append(line[1:])
            after.append(line[1:])
        elif line.startswith("-"):
            before.append(line[1:])
        elif line.startswith("+"):
            after.append(line[1:])
        else:
            raise ValueError(f"解釈できないパッチ行です: {path}: {line.rstrip()}")

    if not in_hunk or not before or not after:
        raise ValueError(f"有効な単一ハンクがありません: {path}")
    return "".join(before), "".join(after)


def load_manifest(
    manifest_path: Path, sdk_root: Path
) -> Tuple[Dict[str, object], List[PatchDefinition]]:
    """マニフェストを読み込み、SDKルートを基準にパッチ定義を構築します。"""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    patches = [
        PatchDefinition(
            patch_id=item["id"],
            description=item["description"],
            target_file=sdk_root / item["file"],
            patch_file=manifest_path.parent / item["patch_file"],
            original_sha256=item["original_sha256"],
            patched_sha256=item["patched_sha256"],
        )
        for item in manifest["patches"]
    ]
    return manifest, patches


def verify_component(sdk_root: Path, expected: Dict[str, object]) -> None:
    """対象App Engineコンポーネントのバージョンを検証します。"""

    snapshot_path = sdk_root / ".install" / "app-engine-python.snapshot.json"
    if not snapshot_path.is_file():
        raise RuntimeError(f"コンポーネント情報が見つかりません: {snapshot_path}")

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    component = next(
        (item for item in snapshot["components"] if item["id"] == expected["id"]),
        None,
    )
    if component is None:
        raise RuntimeError(f"{expected['id']}コンポーネントが見つかりません")

    actual_version = component["version"]
    if (
        actual_version["version_string"] != expected["version_string"]
        or actual_version["build_number"] != expected["build_number"]
    ):
        raise RuntimeError(
            "未検証のapp-engine-pythonです: "
            f"version={actual_version['version_string']}, "
            f"build={actual_version['build_number']}"
        )


def apply_patch(patch: PatchDefinition, check_only: bool) -> str:
    """1件のパッチを検証または適用します。"""

    if not patch.target_file.is_file():
        raise RuntimeError(f"対象ファイルが見つかりません: {patch.target_file}")

    current_sha256 = calculate_sha256(patch.target_file)
    if current_sha256 == patch.patched_sha256:
        return "適用済み"
    if current_sha256 != patch.original_sha256:
        raise RuntimeError(
            f"未知のファイル状態です: {patch.target_file}\n"
            f"  current:  {current_sha256}\n"
            f"  original: {patch.original_sha256}\n"
            f"  patched:  {patch.patched_sha256}"
        )
    if check_only:
        raise RuntimeError(f"未適用のパッチがあります: {patch.patch_id}")

    before, after = read_patch_blocks(patch.patch_file)
    content = patch.target_file.read_text(encoding="utf-8")
    occurrences = content.count(before)
    if occurrences != 1:
        raise RuntimeError(
            f"置換対象が1件ではありません: {patch.target_file} ({occurrences}件)"
        )

    patched_content = content.replace(before, after, 1)
    candidate_sha256 = hashlib.sha256(patched_content.encode("utf-8")).hexdigest()
    if candidate_sha256 != patch.patched_sha256:
        raise RuntimeError(
            f"適用予定内容のSHA-256が一致しません: {patch.target_file}\n"
            f"  actual:   {candidate_sha256}\n"
            f"  expected: {patch.patched_sha256}"
        )

    with patch.target_file.open("w", encoding="utf-8", newline="\n") as target:
        target.write(patched_content)
    applied_sha256 = calculate_sha256(patch.target_file)
    if applied_sha256 != patch.patched_sha256:
        raise RuntimeError(
            f"適用後のSHA-256が一致しません: {patch.target_file}\n"
            f"  actual:   {applied_sha256}\n"
            f"  expected: {patch.patched_sha256}"
        )
    return "適用完了"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """コマンドライン引数を解析します。"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-root", required=True, type=Path, help="Google Cloud SDKのルート")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.json"),
        help="このスクリプトのディレクトリを基準にしたパッチ定義ファイル",
    )
    parser.add_argument("--check", action="store_true", help="変更せず適用状態だけを検証")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """パッチの検証または適用を実行します。"""

    args = parse_args(argv)
    base_dir = Path(__file__).resolve().parent
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = base_dir / manifest_path
    sdk_root = args.sdk_root.resolve()
    try:
        manifest, patches = load_manifest(manifest_path, sdk_root)
        verify_component(sdk_root, manifest["component"])
        for index, patch in enumerate(patches):
            later_hashes = {
                later_patch.patched_sha256
                for later_patch in patches[index + 1 :]
                if later_patch.target_file == patch.target_file
            }
            if (
                patch.target_file.is_file()
                and calculate_sha256(patch.target_file) in later_hashes
            ):
                print(f"[適用済み] {patch.patch_id}: {patch.description}")
                continue
            status = apply_patch(patch, args.check)
            print(f"[{status}] {patch.patch_id}: {patch.description}")
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
