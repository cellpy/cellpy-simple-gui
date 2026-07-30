@echo off
REM Launch cellpy-simple-gui from the repo root.
REM Usage: run [--server] [--no-open] [--port N]
cd /d "%~dp0"
uv run --extra export cellpy-simple-gui %*
