Set oShell = CreateObject("WScript.Shell")
Dim sDesktop, sDir
sDesktop = oShell.SpecialFolders("Desktop")
sDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Raccourci Démarrer
Dim oStart
Set oStart = oShell.CreateShortcut(sDesktop & "\AMOKK - Démarrer.lnk")
oStart.TargetPath       = sDir & "\AMOKK-start.bat"
oStart.WorkingDirectory = sDir
oStart.Description      = "Démarrer AMOKK"
oStart.IconLocation     = "shell32.dll,137"
oStart.WindowStyle      = 7
oStart.Save

' Raccourci Arrêter
Dim oStop
Set oStop = oShell.CreateShortcut(sDesktop & "\AMOKK - Arrêter.lnk")
oStop.TargetPath       = sDir & "\AMOKK-stop.bat"
oStop.WorkingDirectory = sDir
oStop.Description      = "Arrêter AMOKK"
oStop.IconLocation     = "shell32.dll,131"
oStop.WindowStyle      = 7
oStop.Save

MsgBox "Raccourcis créés sur le Bureau !" & Chr(10) & Chr(10) & "- AMOKK - Démarrer" & Chr(10) & "- AMOKK - Arrêter", 64, "AMOKK"
