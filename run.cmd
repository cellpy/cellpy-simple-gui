@echo off
REM Launch cellpy-simple-gui from the repo root.
REM Usage: run [--server] [--no-open] [--port N]
cd /d "%~dp0"
echo Launching cellpy-simple-gui from %CD%
for /f "delims=" %%i in ('uv --version') do echo Using %%i
echo It sometimes takes a while to start the server...
uv run --extra export cellpy-simple-gui %*
