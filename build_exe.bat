@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ==================================================
echo   Сборка PSD-Lab.exe
echo ==================================================

if exist ".venv\Scripts\python.exe" goto have_venv
rem недоделанное окружение от прошлой попытки - удалить
if exist ".venv" rmdir /s /q ".venv"

echo Ищу Python 3.11 или новее ...
for %%V in (-3.12 -3.13 -3.11 -3.14 -3) do (
    if not exist ".venv\Scripts\python.exe" call :try_py %%V
)
if exist ".venv\Scripts\python.exe" goto have_venv
call :try_python
if exist ".venv\Scripts\python.exe" goto have_venv

rem Подходящего Python нет - ставим 3.12 через установщик py (если он есть)
where py >nul 2>&1
if errorlevel 1 goto no_python
echo.
echo Python 3.12 не установлен. Устанавливаю: py install 3.12
echo (если появятся вопросы - отвечайте Y и Enter)
echo.
py install 3.12
call :try_py -3.12
if exist ".venv\Scripts\python.exe" goto have_venv
goto no_python

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
echo   Архив для переноса: dist\PSD-Lab-1.1-win64.zip
echo   Скриншоты проверки: out\screens_exe
start "" explorer "dist"
pause
exit /b 0

:no_python
echo.
echo Не удалось найти или установить Python.
echo Установите его вручную: откройте PowerShell и выполните
echo     winget install Python.Python.3.12
echo затем закройте это окно и запустите build_exe.bat ещё раз.
pause
exit /b 1

:fail
echo.
echo ОШИБКА сборки. Скопируйте текст выше и отправьте его Claude.
pause
exit /b 1

rem ---------- подпрограммы ----------
:try_py
py %1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
echo Нашёл Python: py %1
py %1 -m venv .venv
exit /b 0

:try_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
echo Нашёл Python: python
python -m venv .venv
exit /b 0
