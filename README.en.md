# gae-dev_appserver-patcher

[日本語版 README](README.md)

This tool applies compatibility patches to the Google App Engine `dev_appserver.py` included with the Google Cloud SDK in a reproducible and safe way.

It checks the version of the `app-engine-python` component and the SHA-256 hashes of the target files. It changes only files in a known original state; it leaves already patched files unchanged and stops without changing files in an unknown state.

## Publication and support scope

This project was created by GPT-5.6 Sol and GPT-6.0 Sol and has been reviewed by a human. It is independently published by the author and has not been approved or endorsed by Google.

These patches are provided for Go applications on the Google App Engine standard environment. They have not been tested with applications written in other languages, such as Java.

Maintenance of this project will end if Google provides a `dev_appserver.py` that works fully with Python 3.

## Why this repository exists

Legacy Go applications on the Google App Engine standard environment still need the `dev_appserver.py` included with the Google Cloud SDK for local development. However, `dev_appserver.py` contains code that bridges App Engine APIs from the Python 2 era with current versions of Python 3, protobuf, gRPC, and the Datastore Emulator. Depending on the combination in use, the following problems can occur:

- A Go application fails to build or its child process fails to start.
- A transactional Task Queue request cannot be serialized.
- Datastore query results or cursors cannot be read correctly.
- Datastore Viewer cannot display kind or entity lists.
- A chunked upload to Cloud Storage is finalized as an empty Blob.

These problems require changes to compatibility code inside the SDK; changing the application code cannot resolve them. Editing SDK files by hand also makes the fixes difficult to reproduce in another development environment and makes it easy to miss changes overwritten by an SDK update or to apply fixes to an untested version.

This repository therefore maintains the required fixes separately from any application project so they can be shared by multiple projects. It checks the target component version and each file's SHA-256 hash so that it applies patches only to verified original files, makes no changes to already patched files, and stops without modifying files in an unknown state.

## Supported version

- `app-engine-python` 1.9.118
- Build number `20250822133333`

Compatibility is determined by the version and build number of the `app-engine-python` component that provides the target files, rather than by the version of the Google Cloud SDK as a whole.

## Included patches

`manifest.json` defines the common patches for macOS/Linux and Windows. `windows-manifest.json` defines the Windows-specific patch. The numbers indicate patch order.

### 001: Fix Go debug build arguments (`go-gcflags`)

Fixes an issue where the value of `-gcflags` contains literal quotation marks during a Go debug build, causing the Go compiler to receive the wrong argument. It passes `all=-N -l` as one argument instead of `"all=-N -l"`.

### 002: Use public protobuf modules (`public-protobuf`)

Fixes generated gRPC code that imports Google-internal protobuf modules unavailable in a normal Google Cloud SDK installation. It changes the imports and runtime domain to the public `google.protobuf` equivalents.

### 003: Serialize Task Queue requests with either protobuf API (`taskqueue-protobuf-serialization`)

Fixes serialization failures when a transactional Task Queue request object from the Python 3 protobuf implementation does not provide `Encode()`. It uses `Encode()` for the older format and `SerializeToString()` for the Python 3 format.

### 004: Convert Datastore query responses (`datastore-query-response`)

Fixes cases where a v4/v1 `RunQuery` or `Next` response from the Datastore Emulator cannot be read as the v3 `QueryResult` expected by the legacy App Engine API. It preserves normal v3 responses and detects and converts v4/v1 responses only when needed. It also detects a v4 response that can otherwise be misread as a v3 cursor without raising an error.

### 005: Convert Go child process environment variables (`go-env-strings`, Windows only)

Fixes a Go child process startup failure with `environment can only contain strings` when environment variable keys or values obtained from protobuf remain as `bytes` or `memoryview` on Windows. It decodes them as UTF-8 and sets them as strings.

### 006: List kinds in Datastore Viewer (`datastore-viewer-kinds`)

Fixes failures when Datastore Viewer uses a CompiledQuery path that is incompatible with the Datastore Emulator to list kinds. It retrieves kind names with a keys-only query that disables compilation.

### 007: List entities in Datastore Viewer (`datastore-viewer-entities`)

Fixes failures when Datastore Viewer needs CompiledQuery or `Count()` to list entities. It disables query compilation and requests one extra entity to determine whether another page exists. Consequently, the displayed count is a lower bound indicating the entities through the current page and whether a next page exists, not the total number of entities.

### 008: Retrieve Cloud Storage upload chunks directly (`cloudstorage-direct-chunks`)

Fixes cases where listing upload chunks with a query fails while finalizing a Cloud Storage upload through Blobstore, resulting in an empty Blob. It retrieves each chunk directly by the known key derived from its start offset, detects missing chunks, and combines the data.

## Setup

```text
git clone https://github.com/Kazzz/gae-dev_appserver-patcher.git
cd gae-dev_appserver-patcher
```

No additional Python packages are required to apply the patches. Prepare a clean Google Cloud SDK installation as the target. Do not run `gcloud components update` on a patched SDK; rebuild from a clean SDK when updating.

## Applying the patches

On macOS/Linux, apply the common patches:

```text
./apply_patches.sh /path/to/google-cloud-sdk
```

On Windows, apply the common patches followed by the Windows-specific patch:

```text
apply_windows_patches.bat E:\google\google-cloud-sdk
```

To use a Python interpreter other than `py -3`, set `GAE_DEV_APPSERVER_PATCH_PYTHON` to its absolute path:

```text
set GAE_DEV_APPSERVER_PATCH_PYTHON=E:\Python312\python.exe
apply_windows_patches.bat E:\google\google-cloud-sdk
```

The process is idempotent. Running the same command again does not modify files that are already patched.

## Verifying patch status

Calling the verification command from a startup script detects patches lost during an SDK update before `dev_appserver.py` starts.

macOS/Linux:

```text
./verify_patches.sh /path/to/google-cloud-sdk
```

Windows:

```text
verify_windows_patches.bat E:\google\google-cloud-sdk
```

You can also call the Python script directly:

```text
python3 verify_patches.py --sdk-root /path/to/google-cloud-sdk
python3 verify_patches.py --sdk-root /path/to/google-cloud-sdk --manifest windows-manifest.json
```

## Using it from an application project

To use this repository from multiple projects, provide its location through an environment variable and apply or verify the patches immediately before starting `dev_appserver.py`.

On Windows, you can apply both the common and Windows-specific patches idempotently:

```bat
set "GAE_DEV_APPSERVER_PATCHER_ROOT=E:\gae-dev_appserver-patcher"
call "%GAE_DEV_APPSERVER_PATCHER_ROOT%\apply_windows_patches.bat" "%CLOUD_SDK_ROOT%"
if errorlevel 1 exit /b 1
```

On macOS/Linux, you can check at each startup that the previously applied common patches are still present:

```sh
GAE_DEV_APPSERVER_PATCHER_ROOT=/path/to/gae-dev_appserver-patcher
"$GAE_DEV_APPSERVER_PATCHER_ROOT/verify_patches.sh" "$CLOUD_SDK_ROOT" || exit 1
```

If applying or verifying patches fails, do not start the development server. Check the SDK version and the state of its files.

## Smoke tests

After applying the patches, run the tests for the features you use:

```text
python3 smoke_test_datastore_viewer.py --sdk-root /path/to/google-cloud-sdk
python3 smoke_test_cloudstorage_chunks.py --sdk-root /path/to/google-cloud-sdk
```

The transactional Task Queue and Datastore query response tests require the Python environment used by `dev_appserver` and `grpcio`:

```text
/path/to/dev_appserver/python smoke_test_taskqueue.py --sdk-root /path/to/google-cloud-sdk
/path/to/dev_appserver/python smoke_test_datastore_query.py --sdk-root /path/to/google-cloud-sdk
```

To check the Go environment variable conversion on Windows:

```text
py -3 smoke_test_go_env.py --sdk-root E:\google\google-cloud-sdk
```

When running the Datastore Viewer test on macOS, use a Python environment that includes the `cgi` module used by the SDK's admin console (for example, `/usr/bin/python3`). Python 3.14 no longer includes `cgi`, so importing the module fails regardless of whether the patch works.

## Known limitations

- The patcher rejects an SDK that was previously modified by hand because its hash does not match. Prepare a separate clean SDK installation.
- The count shown in Datastore Viewer is a lower bound indicating the entities through the current page and whether a next page exists; it is not the total count.
- CSV files finalized as empty Blobs before the fix cannot be recovered. Upload them again after applying the patch.
- The Task Queue page in the admin console is not covered by the smoke tests. Check it separately in your environment.

## Maintenance when the SDK changes

1. Extract the new SDK into a directory separate from the existing installation.
2. Run `apply_patches.py` and confirm that it stops because the version has not been verified.
3. Review the differences from the official version and check whether the upstream issues have been fixed.
4. Remove patches that are no longer needed, or update the patches and their SHA-256 hashes in the manifests using the new official files as the baseline.
5. Apply and verify the patches, then run the relevant smoke tests before switching to the new SDK.

Each patch file is a single-hunk unified diff. `apply_patches.py` writes a file only when the target text occurs exactly once and the resulting SHA-256 hash matches the manifest.
