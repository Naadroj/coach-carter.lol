Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")

' Dossier du script (contient pystray, PIL copiés localement)
Dim sDir
sDir = oFSO.GetParentFolderName(WScript.ScriptFullName)

' Ajouter le dossier projet au PYTHONPATH pour trouver pystray/PIL localement
Dim sCurrentPath
sCurrentPath = oShell.Environment("PROCESS")("PYTHONPATH")
If sCurrentPath = "" Then
    oShell.Environment("PROCESS")("PYTHONPATH") = sDir
Else
    oShell.Environment("PROCESS")("PYTHONPATH") = sDir & ";" & sCurrentPath
End If

' Lancer amokk_tray.py sans fenêtre console
oShell.Run """C:\Python314\pythonw.exe"" """ & sDir & "\amokk_tray.py""", 0, False
