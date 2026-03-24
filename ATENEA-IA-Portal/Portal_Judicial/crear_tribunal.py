#!/usr/bin/env python3
"""
Dar de alta un nuevo tribunal en el portal multitribunal.

Uso:
    python crear_tribunal.py --id pontevedra --nombre "Tribunal de Pontevedra" --puerto 5001

El script:
  1. Crea los directorios de datos, config y backups para el tribunal
  2. Genera el archivo tribunal.json con el nombre del tribunal
  3. Genera el archivo iniciar_{id}.bat para arrancar el servidor

Puertos sugeridos:
    vilagarcia  → 5000  (ya existe)
    pontevedra  → 5001
    caldas      → 5002
    cambados    → 5003
    ...
"""
import argparse
import os
import json

# Raíz del proyecto (carpeta padre de Portal_Judicial)
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def crear_tribunal(tid, nombre, puerto):
    datos_dir  = os.path.join(RAIZ, 'datos',   tid)
    config_dir = os.path.join(RAIZ, 'config',  tid)
    backup_dir = os.path.join(RAIZ, 'backups', tid)

    # ── Crear carpetas ────────────────────────────────────
    carpetas = [
        datos_dir,
        os.path.join(datos_dir,  'usuarios'),
        config_dir,
        os.path.join(config_dir, 'usuarios'),
        backup_dir,
    ]
    print(f"\nCreando estructura para '{nombre}' (id: {tid}) en puerto {puerto}...\n")
    for d in carpetas:
        os.makedirs(d, exist_ok=True)
        print(f"  OK{d}")

    # ── Config inicial del tribunal ───────────────────────
    tribunal_json = os.path.join(config_dir, 'tribunal.json')
    with open(tribunal_json, 'w', encoding='utf-8') as f:
        json.dump({
            'titulo':    f'Portal Judicial — {nombre}',
            'subtitulo': nombre
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  OK{tribunal_json}")

    # ── Generar .bat de arranque ──────────────────────────
    # Usa %BASE% (%~dp0) para funcionar en cualquier ubicacion
    bat_path = os.path.join(RAIZ, f'iniciar_{tid}.bat')
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(f"""@echo off
title Portal Judicial - {nombre} (puerto {puerto})

set BASE=%~dp0
set BASE=%BASE:~0,-1%

:: Rutas relativas a esta carpeta (funcionan en cualquier ubicacion)
set PORTAL_DATOS_DIR=%BASE%\\datos\\{tid}
set PORTAL_CONFIG_DIR=%BASE%\\config\\{tid}
set PORTAL_BACKUP_DIR=%BASE%\\backups\\{tid}
set PORTAL_APPS_DIR=%BASE%\\modulos

:: Buscar Python — primero el local (portable/SSD), luego el sistema
set PYTHON=%BASE%\\python-env\\Scripts\\python.exe
if exist "%PYTHON%" goto :lanzar

:: Fallback: buscar en Portal_Judicial_PORTABLE hermano (instalacion normal)
set PORTABLE=%BASE%\\..\\Portal_Judicial_PORTABLE
set PYTHON=%PORTABLE%\\python-env\\Scripts\\python.exe
if exist "%PYTHON%" goto :lanzar

set PYTHON=%PORTABLE%\\python-embed\\python.exe
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
echo   PORTAL JUDICIAL - {nombre}
echo   Puerto: {puerto}
echo  ================================================
echo.
cd /d "%BASE%\\Portal_Judicial"
"%PYTHON%" "%BASE%\\Portal_Judicial\\servidor.py" --puerto {puerto}
pause
""")
    print(f"  OK{bat_path}")

    # ── Generar .vbs lanzador silencioso ──────────────────
    vbs_path = os.path.join(RAIZ, f'iniciar_{tid}.vbs')
    with open(vbs_path, 'w', encoding='utf-8') as f:
        f.write(f"""' Portal Judicial Multitribunal - Lanzador Silencioso
' {nombre} - Puerto {puerto}
Option Explicit

Dim objShell, objFSO
Dim strBase, strPython, strServidor, strPortable

Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")

strBase     = objFSO.GetParentFolderName(WScript.ScriptFullName)
strServidor = strBase & "\\Portal_Judicial\\servidor.py"

If Not objFSO.FileExists(strServidor) Then
    MsgBox "No se encontro Portal_Judicial\\servidor.py en:" & vbCrLf & strBase, vbCritical, "Portal Judicial"
    WScript.Quit
End If

objShell.Environment("Process")("PORTAL_DATOS_DIR")  = strBase & "\\datos\\{tid}"
objShell.Environment("Process")("PORTAL_CONFIG_DIR") = strBase & "\\config\\{tid}"
objShell.Environment("Process")("PORTAL_BACKUP_DIR") = strBase & "\\backups\\{tid}"
objShell.Environment("Process")("PORTAL_APPS_DIR")   = strBase & "\\modulos"

strPortable = objFSO.GetParentFolderName(strBase) & "\\Portal_Judicial_PORTABLE"
strPython   = ""

If objFSO.FileExists(strBase & "\\python-env\\Scripts\\python.exe") Then
    strPython = strBase & "\\python-env\\Scripts\\python.exe"
ElseIf objFSO.FileExists(strPortable & "\\python-env\\Scripts\\python.exe") Then
    strPython = strPortable & "\\python-env\\Scripts\\python.exe"
ElseIf objFSO.FileExists(strPortable & "\\python-embed\\python.exe") Then
    strPython = strPortable & "\\python-embed\\python.exe"
End If

If strPython = "" Then
    Dim objExec
    On Error Resume Next
    Set objExec = objShell.Exec("python --version")
    If Err.Number = 0 Then
        strPython = "python"
    Else
        Set objExec = objShell.Exec("py --version")
        If Err.Number = 0 Then strPython = "py"
    End If
    On Error GoTo 0
End If

If strPython = "" Then
    MsgBox "No se encontro Python instalado." & vbCrLf & vbCrLf & _
           "Verifica que la carpeta python-env\\ existe en:" & vbCrLf & strBase, _
           vbCritical, "Portal Judicial"
    WScript.Quit
End If

Dim strCmd
strCmd = Chr(34) & strPython & Chr(34) & " " & Chr(34) & strServidor & Chr(34) & " --puerto {puerto}"
objShell.Run strCmd, 0, False

WScript.Sleep 2500

objShell.Run "http://localhost:{puerto}", 1, False

Set objShell = Nothing
Set objFSO   = Nothing
""")
    print(f"  OK{vbs_path}")

    # ── Generar _red.bat para modo red ────────────────────
    red_path = os.path.join(RAIZ, f'iniciar_{tid}_red.bat')
    with open(red_path, 'w', encoding='utf-8') as f:
        f.write(f"""@echo off
title Portal Judicial - {nombre} - MODO RED (Servidor)
chcp 65001 >nul 2>&1

set BASE=%~dp0
set BASE=%BASE:~0,-1%

set PORTAL_DATOS_DIR=%BASE%\\datos\\{tid}
set PORTAL_CONFIG_DIR=%BASE%\\config\\{tid}
set PORTAL_BACKUP_DIR=%BASE%\\backups\\{tid}
set PORTAL_APPS_DIR=%BASE%\\modulos

if not exist "%BASE%\\Portal_Judicial\\servidor.py" (
    echo ERROR: No se encontro Portal_Judicial\\servidor.py
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   PORTAL JUDICIAL - {nombre} - MODO RED
echo   Este PC actuara como SERVIDOR para todos los demas
echo  ============================================================
echo.
echo  INSTRUCCIONES:
echo   1. Deja esta ventana abierta mientras trabajas
echo   2. La URL de red aparecera abajo en unos segundos
echo   3. Los demas PCs deben ejecutar ACCEDER_PORTAL.bat
echo   4. Para cerrar el portal cierra esta ventana
echo.

set PYTHON=%BASE%\\python-env\\Scripts\\python.exe
if exist "%PYTHON%" goto :lanzar

set PORTABLE=%BASE%\\..\\Portal_Judicial_PORTABLE
set PYTHON=%PORTABLE%\\python-env\\Scripts\\python.exe
if exist "%PYTHON%" goto :lanzar

set PYTHON=%PORTABLE%\\python-embed\\python.exe
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

netsh advfirewall firewall add rule name="Portal Judicial {tid}" dir=in action=allow protocol=TCP localport={puerto} >nul 2>&1

set PORTAL_RED=1
cd /d "%BASE%\\Portal_Judicial"
"%PYTHON%" "%BASE%\\Portal_Judicial\\servidor.py" --red --puerto {puerto}

pause
""")
    print(f"  OK{red_path}")

    # ── Resumen ───────────────────────────────────────────
    sep = '-' * 55
    print(f"""
{sep}
  [OK] Tribunal dado de alta correctamente

  ID:       {tid}
  Nombre:   {nombre}
  Puerto:   {puerto}
  Datos:    {datos_dir}
  Config:   {config_dir}
  Backups:  {backup_dir}

  >> Para iniciarlo:
       iniciar_{tid}.vbs      (silencioso, sin ventana CMD)
       iniciar_{tid}.bat      (con ventana, para ver errores)
       iniciar_{tid}_red.bat  (modo red, para compartir en LAN)

  URL local:
       http://localhost:{puerto}
{sep}
""")


if __name__ == '__main__':
    p = argparse.ArgumentParser(
        description='Dar de alta un tribunal en el portal multitribunal'
    )
    p.add_argument('--id',
                   required=True,
                   help='ID corto sin espacios ni tildes (ej: pontevedra)')
    p.add_argument('--nombre',
                   required=True,
                   help='Nombre completo del tribunal (ej: "Tribunal de Pontevedra")')
    p.add_argument('--puerto',
                   required=True,
                   type=int,
                   help='Puerto único para este tribunal (5001, 5002, …)')
    args = p.parse_args()

    # Validaciones básicas
    if not args.id.replace('-', '').replace('_', '').isalnum():
        print("ERROR: El ID solo puede contener letras, numeros, guiones y guiones bajos.")
        exit(1)
    if args.puerto < 1024 or args.puerto > 65535:
        print("ERROR: El puerto debe estar entre 1024 y 65535.")
        exit(1)

    crear_tribunal(args.id, args.nombre, args.puerto)
