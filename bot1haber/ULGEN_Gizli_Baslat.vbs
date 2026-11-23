Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

strScriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptPath

' Evrensel pythonw veya pyw ile arka planda baslat
On Error Resume Next
WshShell.Run "pyw run.py", 0, False
If Err.Number <> 0 Then
    Err.Clear
    WshShell.Run "pythonw run.py", 0, False
End If
On Error GoTo 0

WshShell.Run "cmd /c timeout /t 5 >nul && start http://localhost:9001", 0, False

Set WshShell = Nothing
Set fso = Nothing
