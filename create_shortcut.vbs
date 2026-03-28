Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")

Dim sDir
sDir = oFSO.GetParentFolderName(WScript.ScriptFullName)

Dim sDesktop
sDesktop = oShell.SpecialFolders("Desktop")

Dim oLink
Set oLink = oShell.CreateShortcut(sDesktop & "\AMOKK.lnk")
oLink.TargetPath       = "wscript.exe"
oLink.Arguments        = """" & sDir & "\AMOKK.vbs"""
oLink.WorkingDirectory = sDir
oLink.Description      = "AMOKK - Coach IA League of Legends"
oLink.IconLocation     = "shell32.dll,13"
oLink.Save

MsgBox "Raccourci AMOKK créé sur le Bureau !", 64, "AMOKK"
