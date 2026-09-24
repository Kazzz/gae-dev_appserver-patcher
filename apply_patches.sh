#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $(basename "$0") SDK_ROOT" >&2
    exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATCH_PYTHON=${GAE_DEV_APPSERVER_PATCH_PYTHON:-python3}

"$PATCH_PYTHON" "$SCRIPT_DIR/apply_patches.py" --sdk-root "$1"
