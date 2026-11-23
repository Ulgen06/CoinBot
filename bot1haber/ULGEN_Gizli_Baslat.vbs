Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

' Script'in bulundugu dizini otomatik tespit et
strScriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptPath

' 1. Temizlik: Eski islemleri kapat
WshShell.Run "taskkill /f /im python.exe /t", 0, True
WshShell.Run "taskkill /f /im pythonw.exe /t", 0, True

' 2. Botu Arka Planda Baslat
' pythonw.exe konsol penceresi acmadan calisir
pythonPath = """C:\Users\karas\AppData\Local\Programs\Python\Python313\pythonw.exe"""
WshShell.Run pythonPath & " run.py", 0, False

' 3. Dashboard'u ac (5 saniye bekleme süresi ile)
WshShell.Run "cmd /c timeout /t 5 >nul && start http://localhost:9001", 0, False

Set WshShell = Nothing
Set fso = Nothing
