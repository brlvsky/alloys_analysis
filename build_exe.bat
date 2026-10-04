@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ==================================================
echo   Сборка PSD-Lab.exe
echo ==================================================

if exist ".venv\Scripts\python.exe" goto have_venv
echo Создаю окружение Python в папке .venv ...
py -3.12 -m venv .venv
if errorlevel 1 python -m venv .venv
if errorlevel 1 goto no_python

:have_venv
echo Устанавливаю библиотеки - в первый раз это займёт несколько минут ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" tools\make_icons.py
if errorlevel 1 goto fail
".venv\Scripts\python.exe" tools\build_exe.py
if errorlevel 1 goto fail

echo.
echo Готово!
echo   Программа:          dist\PSD-Lab\PSD-Lab.exe
echo   Архив для переноса: dist\PSD-Lab-1.0-win64.zip
echo   Скриншоты проверки: out\screens_exe
start "" explorer "dist"
pause
exit /b 0

:no_python
echo.
echo Не найден Python 3.12. Установите его командой:
echo     winget install Python.Python.3.12
echo затем закройте это окно и запустите build_exe.bat ещё раз.
pause
exit /b 1

:fail
echo.
echo ОШИБКА сборки. Скопируйте текст выше и отправьте его Claude.
pause
exit /b 1
