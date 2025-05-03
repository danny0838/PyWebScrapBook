:: Compile portable executable for Windows (x86/x64).
:: Add --onefile to compile as single executable (less performant).
::
:: NOTE: webscrapbook package should be installed in non-editable mode.
::
@echo off
set "dir=%~dp0.."
set "build=%dir%\build"
set "dist=%dir%\dist"
set "res=%dir%\tools\compile"
if "%~1"=="--onefile" (
  set "onefile=--onefile"
) else (
  set "onefile="
)

:: Check if the module has been installed
pip show webscrapbook >nul 2>nul
if %errorlevel% neq 0 (
  echo ERROR: webscrapbook is not installed
  exit /b %errorlevel%
)

python -m pip install --upgrade pyinstaller

:: Clean the build folder
if exist "%build%" rmdir /s /q "%build%"

pyinstaller "%res%\wsb.py" %onefile% --noconfirm ^
  --workpath "%build%" --specpath "%build%" --distpath "%dist%" -n wsb ^
  --hidden-import webscrapbook.cli ^
  --add-data "%dir%\webscrapbook\resources:webscrapbook\resources" ^
  --add-data "%dir%\webscrapbook\themes:webscrapbook\themes"
if %errorlevel% neq 0 exit /b %errorlevel%
