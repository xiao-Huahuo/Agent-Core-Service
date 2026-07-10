@echo off

REM 启动 free-claude-code 代理
start "free-claude-code proxy" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath 'D:\Projects\Python\free-claude-code'; uv run uvicorn server:app --host 127.0.0.1 --port 8082"

REM 等待 3 秒，让代理先启动
timeout /t 3 /nobreak >nul

REM 启动 Claude Code
start "Claude Code DeepSeek" powershell -NoExit -ExecutionPolicy Bypass -Command "Set-Location -LiteralPath 'D:\Projects\Python\MetaWeave'; $env:ANTHROPIC_AUTH_TOKEN='freecc'; $env:ANTHROPIC_BASE_URL='http://localhost:8082'; claude.cmd --dangerously-skip-permissions"