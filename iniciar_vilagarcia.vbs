' =====================================================
' Portal Judicial Multitribunal - Lanzador Silencioso
' Tribunal de Vilagarcia de Arousa - Puerto 5000
' =====================================================
' Doble clic: inicia el servidor en segundo plano
' y abre el portal en el navegador sin ventana CMD
' =====================================================
Option Explicit
Dim objShell, objFSO
Dim strBase, strPython, strServidor, strPortable
Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")
' Carpeta donde esta este .vbs (raiz del proyecto)
strBase     = objFSO.GetParentFolderName(WScript.ScriptFullName)
strServidor = strBase & "\Portal_Judicial\servidor.py"
' Verificar que existe el servidor
If Not objFSO.FileExists(strServidor) Then
    MsgBox "No se encontro Portal_Judicial\servidor.py en:" & vbCrLf & strBase, vbCritical, "Portal Judicial"
    WScript.Quit
End If
' ── Variables de entorno para Vilagarcia ──────────
objShell.Environment("Process")("PORTAL_DATOS_DIR")  = strBase & "\datos\vilagarcia"
objShell.Environment("Process")("PORTAL_CONFIG_DIR") = strBase & "\config\vilagarcia"
objShell.Environment("Process")("PORTAL_BACKUP_DIR") = strBase & "\backups\vilagarcia"
objShell.Environment("Process")("PORTAL_APPS_DIR")   = strBase & "\modulos"
' ── Buscar Python ─────────────────────────────────
' 1. python-env local  (portable / SSD)
' 2. python-embed en la raiz del propio proyecto (CORRECCIÓN)
' 3. python-env en Portal_Judicial_PORTABLE hermano
' 4. python-embed en Portal_Judicial_PORTABLE hermano
' 5. Python del sistema (PATH)
strPortable = objFSO.GetParentFolderName(strBase) & "\Portal_Judicial_PORTABLE"
strPython   = ""
If objFSO.FileExists(strBase & "\python-env\Scripts\python.exe") Then
    strPython = strBase & "\python-env\Scripts\python.exe"
ElseIf objFSO.FileExists(strBase & "\python-embed\python.exe") Then
    strPython = strBase & "\python-embed\python.exe"
ElseIf objFSO.FileExists(strPortable & "\python-env\Scripts\python.exe") Then
    strPython = strPortable & "\python-env\Scripts\python.exe"
ElseIf objFSO.FileExists(strPortable & "\python-embed\python.exe") Then
    strPython = strPortable & "\python-embed\python.exe"
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
           "Verifica que la carpeta python-embed\ existe en:" & vbCrLf & strBase, _
           vbCritical, "Portal Judicial"
    WScript.Quit
End If
' ── Lanzar servidor SIN ventana (WindowStyle = 0) ─
Dim strCmd
strCmd = Chr(34) & strPython & Chr(34) & " " & Chr(34) & strServidor & Chr(34) & " --puerto 5000"
objShell.Run strCmd, 0, False
' ── Esperar a que el servidor arranque ────────────
WScript.Sleep 2500
' ── Abrir navegador en el puerto de Vilagarcia ────
objShell.Run "http://localhost:5000", 1, False
Set objShell = Nothing
Set objFSO   = Nothing
