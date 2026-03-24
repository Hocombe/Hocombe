' =====================================================
' Portal Judicial Unificado - Lanzador Silencioso
' Tribunal de Instancia de Vilagarcía de Arousa
' =====================================================
' Ejecuta el servidor Python SIN mostrar ventana CMD
' Doble clic para abrir el portal en el navegador
' =====================================================

Option Explicit

Dim objShell, objFSO
Dim strBase, strPython, strServidor
Dim strPyPaths(6), i

Set objShell = CreateObject("WScript.Shell")
Set objFSO   = CreateObject("Scripting.FileSystemObject")

' Carpeta donde está este .vbs
strBase     = objFSO.GetParentFolderName(WScript.ScriptFullName)
strServidor = strBase & "\servidor.py"

' Verificar que existe el servidor
If Not objFSO.FileExists(strServidor) Then
    MsgBox "No se encontró servidor.py en:" & vbCrLf & strBase, vbCritical, "Portal Judicial"
    WScript.Quit
End If

' ── Buscar Python ────────────────────────────────
' Orden de búsqueda:
'   1. python-portable\python.exe  (en la misma carpeta)
'   2. python-portable\pythonw.exe
'   3. python en PATH del sistema
strPyPaths(0) = strBase & "\python-portable\python.exe"
strPyPaths(1) = strBase & "\python-portable\pythonw.exe"
strPyPaths(2) = strBase & "\python\python.exe"
strPyPaths(3) = strBase & "\python\pythonw.exe"
strPyPaths(4) = "python"
strPyPaths(5) = "python3"
strPyPaths(6) = "py"

strPython = ""
For i = 0 To 3
    If objFSO.FileExists(strPyPaths(i)) Then
        strPython = strPyPaths(i)
        Exit For
    End If
Next

' Si no encontró portable, usar el del sistema (PATH)
If strPython = "" Then
    ' Verificar que python está en PATH
    Dim objExec
    On Error Resume Next
    Set objExec = objShell.Exec("python --version")
    If Err.Number = 0 Then
        strPython = "python"
    Else
        Set objExec = objShell.Exec("py --version")
        If Err.Number = 0 Then
            strPython = "py"
        End If
    End If
    On Error GoTo 0
End If

If strPython = "" Then
    MsgBox "No se encontró Python instalado." & vbCrLf & vbCrLf & _
           "Opciones:" & vbCrLf & _
           "  1. Instala Python desde python.org" & vbCrLf & _
           "  2. Pon Python portable en:" & vbCrLf & _
           "     " & strBase & "\python-portable\", _
           vbCritical, "Portal Judicial"
    WScript.Quit
End If

' ── Lanzar servidor SIN ventana ──────────────────
' WindowStyle = 0  → ventana oculta
' bWaitOnReturn = False → no esperar
Dim strCmd
strCmd = Chr(34) & strPython & Chr(34) & " " & Chr(34) & strServidor & Chr(34)
objShell.Run strCmd, 0, False

' ── Esperar a que el servidor arranque ───────────
WScript.Sleep 2500

' ── Abrir navegador ──────────────────────────────
' El servidor elige puerto dinámico y abre el navegador solo.
' Este bloque es por si acaso falla el auto-open.
' Leemos el puerto del log más reciente
Dim strLogDir, strLogHoy, strPuerto
strLogDir = strBase & "\logs"
strLogHoy = strLogDir & "\portal_" & Year(Now) & _
            Right("0" & Month(Now), 2) & Right("0" & Day(Now), 2) & ".log"
strPuerto = ""

If objFSO.FileExists(strLogHoy) Then
    Dim objFile, strLine
    Set objFile = objFSO.OpenTextFile(strLogHoy, 1) ' 1=ForReading
    Do While Not objFile.AtEndOfStream
        strLine = objFile.ReadLine
        If InStr(strLine, "Servidor iniciado en puerto") > 0 Then
            ' Extraer número de puerto
            Dim arrParts
            arrParts = Split(strLine, "puerto ")
            If UBound(arrParts) >= 1 Then
                strPuerto = Trim(arrParts(1))
            End If
        End If
    Loop
    objFile.Close
End If

If strPuerto <> "" Then
    objShell.Run "http://localhost:" & strPuerto, 1, False
End If

' Limpiar
Set objShell = Nothing
Set objFSO   = Nothing
