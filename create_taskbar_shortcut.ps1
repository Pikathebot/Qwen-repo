$projectDir = "D:\JARVIS"
$pythonw = "$projectDir\.venv\Scripts\pythonw.exe"
$targetScript = "$projectDir\run_jarvis.py"
$iconPath = "$projectDir\desktop\assets\jarvis.ico"

# 1. Project Directory Shortcut
$shortcutPath = "$projectDir\Jarvis Assistant.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $pythonw
$Shortcut.Arguments = "`"$targetScript`""
$Shortcut.WorkingDirectory = $projectDir
$Shortcut.IconLocation = "$iconPath, 0"
$Shortcut.Description = "Jarvis Local AI Assistant"
$Shortcut.Save()

# 2. Desktop Shortcut
$desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$desktopShortcutPath = "$desktopPath\Jarvis Assistant.lnk"
$DesktopShortcut = $WshShell.CreateShortcut($desktopShortcutPath)
$DesktopShortcut.TargetPath = $pythonw
$DesktopShortcut.Arguments = "`"$targetScript`""
$DesktopShortcut.WorkingDirectory = $projectDir
$DesktopShortcut.IconLocation = "$iconPath, 0"
$DesktopShortcut.Description = "Jarvis Local AI Assistant"
$DesktopShortcut.Save()

Write-Host "Created shortcuts:"
Write-Host " - $shortcutPath"
Write-Host " - $desktopShortcutPath"
Write-Host "You can right-click 'Jarvis Assistant' shortcut -> 'Pin to taskbar'!"
