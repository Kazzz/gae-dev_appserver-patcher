@echo off
setlocal

if "%~1"=="" (
    echo Usage: %~nx0 SDK_ROOT 1>&2
    exit /b 2
)

set "SDK_ROOT=%~1"
set "VERIFY_SCRIPT=%~dp0verify_patches.py"

if defined GAE_DEV_APPSERVER_PATCH_PYTHON (
    "%GAE_DEV_APPSERVER_PATCH_PYTHON%" "%VERIFY_SCRIPT%" --sdk-root "%SDK_ROOT%"
) else (
    py -3 "%VERIFY_SCRIPT%" --sdk-root "%SDK_ROOT%"
)
if errorlevel 1 exit /b 1

if defined GAE_DEV_APPSERVER_PATCH_PYTHON (
    "%GAE_DEV_APPSERVER_PATCH_PYTHON%" "%VERIFY_SCRIPT%" --sdk-root "%SDK_ROOT%" --manifest windows-manifest.json
) else (
    py -3 "%VERIFY_SCRIPT%" --sdk-root "%SDK_ROOT%" --manifest windows-manifest.json
)
if errorlevel 1 exit /b 1

exit /b 0
