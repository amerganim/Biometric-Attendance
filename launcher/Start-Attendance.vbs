' Biometric Attendance — double-click launcher (no console window).
' Runs the app with the project's bundled Python (pythonw.exe) so a non-technical
' user never has to open a terminal. Lives in the "launcher" folder; the project
' root is its parent.
Option Explicit
Dim fso, sh, appDir, pythonw, mainPy
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
pythonw = appDir & "\.venv\Scripts\pythonw.exe"
mainPy = appDir & "\main.py"

If Not fso.FileExists(pythonw) Then
    MsgBox "Setup not found at:" & vbCrLf & pythonw & vbCrLf & vbCrLf & _
           "Please run the one-time setup first (see launcher\README).", _
           vbExclamation, "Biometric Attendance"
    WScript.Quit 1
End If

sh.CurrentDirectory = appDir
' 0 = hidden window, False = don't wait for the app to exit.
sh.Run """" & pythonw & """ """ & mainPy & """", 0, False
