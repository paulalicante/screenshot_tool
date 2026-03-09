Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

appDir = FSO.GetParentFolderName(WScript.ScriptFullName)
venvPythonw = appDir & "\.venv\Scripts\pythonw.exe"
venvPython = appDir & "\.venv\Scripts\python.exe"
fallbackPythonw = "C:\Python314\pythonw.exe"
fallbackPython = "C:\Python314\python.exe"
scriptPath = appDir & "\screenshot_tool_pyqt.py"
debugLogPath = appDir & "\launcher_debug.log"

Sub AppendDebug(msg)
    On Error Resume Next
    Set f = FSO.OpenTextFile(debugLogPath, 8, True)
    f.WriteLine Now & " - " & msg
    f.Close
    On Error GoTo 0
End Sub

WshShell.CurrentDirectory = appDir

If FSO.FileExists(venvPythonw) Then
    AppendDebug "Trying hidden launch via venv pythonw"
    startTime = Timer
    exitCode = WshShell.Run(Chr(34) & venvPythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, True)
    elapsed = Timer - startTime
    AppendDebug "Hidden launch exited. code=" & exitCode & " elapsed=" & elapsed
    If exitCode <> 0 Or elapsed < 3 Then
        If FSO.FileExists(venvPython) Then
            visibleCmd = "cmd /k " & Chr(34) & Chr(34) & venvPython & Chr(34) & " " & Chr(34) & scriptPath & Chr(34) & Chr(34)
            AppendDebug "Fallback visible launch via venv python: " & visibleCmd
            WshShell.Run visibleCmd, 1, False
        ElseIf FSO.FileExists(fallbackPython) Then
            visibleCmd = "cmd /k " & Chr(34) & Chr(34) & fallbackPython & Chr(34) & " " & Chr(34) & scriptPath & Chr(34) & Chr(34)
            AppendDebug "Fallback visible launch via system python: " & visibleCmd
            WshShell.Run visibleCmd, 1, False
        Else
            AppendDebug "Fallback failed: no python.exe found"
            WshShell.Popup "App exited immediately (code " & exitCode & "), and no python.exe fallback was found.", 10, "Otterly Screenshots", 16
        End If
    End If
ElseIf FSO.FileExists(fallbackPythonw) Then
    AppendDebug "Trying hidden launch via system pythonw"
    startTime = Timer
    exitCode = WshShell.Run(Chr(34) & fallbackPythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, True)
    elapsed = Timer - startTime
    AppendDebug "Hidden launch exited. code=" & exitCode & " elapsed=" & elapsed
    If exitCode <> 0 Or elapsed < 3 Then
        If FSO.FileExists(fallbackPython) Then
            visibleCmd = "cmd /k " & Chr(34) & Chr(34) & fallbackPython & Chr(34) & " " & Chr(34) & scriptPath & Chr(34) & Chr(34)
            AppendDebug "Fallback visible launch via system python: " & visibleCmd
            WshShell.Run visibleCmd, 1, False
        Else
            AppendDebug "Fallback failed: no python.exe found"
            WshShell.Popup "App exited immediately (code " & exitCode & "), and no python.exe fallback was found.", 10, "Otterly Screenshots", 16
        End If
    End If
Else
    AppendDebug "Launch failed: no pythonw found"
    WshShell.Popup "Python interpreter not found. Expected .venv\Scripts\pythonw.exe", 10, "Otterly Screenshots", 16
End If
