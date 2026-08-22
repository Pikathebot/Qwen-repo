$projectDir = "D:\JARVIS"
$compiledExe = "$projectDir\dist\run_jarvis.exe"
$rootExe = "$projectDir\run_jarvis.exe"
$pythonw = "$projectDir\.venv\Scripts\pythonw.exe"
$targetScript = "$projectDir\run_jarvis.py"
$iconPath = "$projectDir\desktop\assets\jarvis.ico"


# Resolve Target Binary
if (Test-Path $compiledExe) {
    $targetPath = $compiledExe
    $targetArgs = ""
} elseif (Test-Path $rootExe) {
    $targetPath = $rootExe
    $targetArgs = ""
} else {
    $targetPath = $pythonw
    $targetArgs = "`"$targetScript`""
}

# 1. Project Directory Shortcut
$shortcutPath = "$projectDir\Jarvis Assistant.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $targetPath
if ($targetArgs) { $Shortcut.Arguments = $targetArgs }
$Shortcut.WorkingDirectory = $projectDir
$Shortcut.IconLocation = "$iconPath, 0"
$Shortcut.Description = "Jarvis Local AI Assistant"
$Shortcut.Save()

# 2. Desktop Shortcut
$desktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$desktopShortcutPath = "$desktopPath\Jarvis Assistant.lnk"
$DesktopShortcut = $WshShell.CreateShortcut($desktopShortcutPath)
$DesktopShortcut.TargetPath = $targetPath
if ($targetArgs) { $DesktopShortcut.Arguments = $targetArgs }
$DesktopShortcut.WorkingDirectory = $projectDir
$DesktopShortcut.IconLocation = "$iconPath, 0"
$DesktopShortcut.Description = "Jarvis Local AI Assistant"
$DesktopShortcut.Save()


Write-Host "Created shortcuts:"
Write-Host " - $shortcutPath"
Write-Host " - $desktopShortcutPath"
Write-Host "You can right-click 'Jarvis Assistant' shortcut -> 'Pin to taskbar'!"
