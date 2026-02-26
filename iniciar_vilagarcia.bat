@echo off
title Portal Judicial - Tribunal de Vilagarcia (puerto 5000)
set BASE=%~dp0
set BASE=%BASE:~0,-1%
set PORTAL_DATOS_DIR=%BASE%\datos\vilagarcia
set PORTAL_CONFIG_DIR=%BASE%\config\vilagarcia
set PORTAL_BACKUP_DIR=%BASE%\backups\vilagarcia
set PORTAL_APPS_DIR=%BASE%\modulos
set SERVIDOR=%BASE%\Portal_Judicial\servidor.py
:: Buscar Python — primero el local (portable/SSD), luego el sistema
set PYTHON=%BASE%\python-env\Scripts\python.exe
if exist "%PYTHON%" goto :lanzar
:: python-embed en la raiz del propio proyecto (CORRECCIÓN)
set PYTHON=%BASE%\python-embed\python.exe
if exist "%PYTHON%" goto :lanzar
:: Fallback: buscar en Portal_Judicial_PORTABLE hermano (instalacion normal)
set PORTABLE=%BASE%\..\Portal_Judicial_PORTABLE
set PYTHON=%PORTABLE%\python-env\Scripts\python.exe
if exist "%PYTHON%" goto :lanzar
set PYTHON=%PORTABLE%\python-embed\python.exe
if exist "%PYTHON%" goto :lanzar
where py >nul 2>&1
if not errorlevel 1 ( set PYTHON=py & goto :lanzar )
where python >nul 2>&1
if not errorlevel 1 ( set PYTHON=python & goto :lanzar )
echo ERROR: No se encontro Python instalado.
pause
exit /b 1
:lanzar
echo.
echo  ================================================
echo   PORTAL JUDICIAL - Tribunal de Vilagarcia
echo   Puerto: 5000
echo  ================================================
echo.
cd /d "%BASE%\Portal_Judicial"
"%PYTHON%" "%SERVIDOR%" --puerto 5000
pause
