@echo off
title Portal Judicial - Acceso de Cliente
chcp 65001 >nul 2>&1
set BASE=%~dp0
set BASE=%BASE:~0,-1%
:: Buscar la URL guardada por el servidor en modo red
set URL_FILE=%BASE%\config\vilagarcia\servidor_url.txt
if exist "%URL_FILE%" (
    set /p PORTAL_URL=<"%URL_FILE%"
    echo.
    echo  Conectando al Portal Judicial...
    echo  Servidor: %PORTAL_URL%
    echo.
    start "" "%PORTAL_URL%"
    exit /b 0
)
:: Si no hay fichero, preguntar la IP manualmente
echo.
echo  ============================================================
echo   PORTAL JUDICIAL - Acceso de Cliente
echo  ============================================================
echo.
echo  No se encontro la URL del servidor automaticamente.
echo.
echo  Pregunta al PC servidor cual es su direccion IP
echo  (aparece en la ventana del servidor como "URL en red:")
echo.
set /p IP_SERVIDOR="  Introduce la IP del servidor (ej: 192.168.1.10): "
if "%IP_SERVIDOR%"=="" (
    echo No introduciste ninguna IP. Cerrando.
    pause
    exit /b 1
)
set PORTAL_URL=http://%IP_SERVIDOR%:5000
echo.
echo  Abriendo: %PORTAL_URL%
echo.
:: Guardar para la proxima vez
if not exist "%BASE%\config\vilagarcia" mkdir "%BASE%\config\vilagarcia"
echo %PORTAL_URL%> "%URL_FILE%"
start "" "%PORTAL_URL%"
