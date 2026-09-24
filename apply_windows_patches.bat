@echo off
setlocal

if "%~1"=="" (
    echo SDK root is required. 1>&2
    exit /b 2
)

set "SDK_ROOT=%~1"
set "PATCH_SCRIPT=%~dp0apply_patches.py"

if defined GAE_DEV_APPSERVER_PATCH_PYTHON (
    "%GAE_DEV_APPSERVER_PATCH_PYTHON%" "%PATCH_SCRIPT%" --sdk-root "%SDK_ROOT%"
) else (
    py -3 "%PATCH_SCRIPT%" --sdk-root "%SDK_ROOT%"
)
if errorlevel 1 exit /b 1

if defined GAE_DEV_APPSERVER_PATCH_PYTHON (
    "%GAE_DEV_APPSERVER_PATCH_PYTHON%" "%PATCH_SCRIPT%" --sdk-root "%SDK_ROOT%" --manifest windows-manifest.json
) else (
    py -3 "%PATCH_SCRIPT%" --sdk-root "%SDK_ROOT%" --manifest windows-manifest.json
)
if errorlevel 1 exit /b 1

exit /b 0
