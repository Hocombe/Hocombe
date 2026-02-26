@echo off
title Portal Judicial - Vilagarcia - MODO RED (Servidor)
chcp 65001 >nul 2>&1
set BASE=%~dp0
set BASE=%BASE:~0,-1%
set PORTAL_DATOS_DIR=%BASE%\datos\vilagarcia
set PORTAL_CONFIG_DIR=%BASE%\config\vilagarcia
set PORTAL_BACKUP_DIR=%BASE%\backups\vilagarcia
set PORTAL_APPS_DIR=%BASE%\modulos
if not exist "%BASE%\Portal_Judicial\servidor.py" (
    echo ERROR: No se encontro Portal_Judicial\servidor.py
    pause
    exit /b 1
)
echo.
echo  ============================================================
echo   PORTAL JUDICIAL - Vilagarcia - MODO RED
echo   Este PC actuara como SERVIDOR para todos los demas
echo  ============================================================
echo.
echo  INSTRUCCIONES:
echo   1. Deja esta ventana abierta mientras trabajas
echo   2. La URL de red aparecera abajo en unos segundos
echo   3. Los demas PCs deben ejecutar ACCEDER_PORTAL.bat
echo   4. Para cerrar el portal cierra esta ventana
echo.
:: Buscar Python — primero el local (portable/SSD), luego el sistema
set PYTHON=%BASE%\python-env\Scripts\python.exe
if exist "%PYTHON%" goto :lanzar
:: python-embed en la raiz del propio proyecto (CORRECCIÓN)
set PYTHON=%BASE%\python-embed\python.exe
if exist "%PYTHON%" goto :lanzar
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
echo  Iniciando servidor en MODO RED...
echo.
:: Abrir puerto 5000 en el firewall de Windows (puede requerir admin)
netsh advfirewall firewall add rule name="Portal Judicial Vilagarcia" dir=in action=allow protocol=TCP localport=5000 >nul 2>&1
set PORTAL_RED=1
cd /d "%BASE%\Portal_Judicial"
"%PYTHON%" "%BASE%\Portal_Judicial\servidor.py" --red --puerto 5000
pause
