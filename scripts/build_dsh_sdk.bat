@echo off
REM Build the DSH Runtime SDK embedded in MetaWeave.
REM With no argument, clone the locked repository. An optional local repository is an offline clone source.
setlocal
set "SCRIPT_DIR=%~dp0"
if "%~1"=="" (
  python "%SCRIPT_DIR%build_dsh_windows_bundle.py"
) else (
  python "%SCRIPT_DIR%build_dsh_windows_bundle.py" --dsh-root "%~1"
)
if errorlevel 1 exit /b %errorlevel%
echo DSH Runtime SDK production completed.
