$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\TennisMonitor.lnk"
$Shortcut = $WshShell.CreateShortcut($StartupPath)
$Shortcut.TargetPath = "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting\start_monitor.vbs"
$Shortcut.WorkingDirectory = "C:\Users\marca\OneDrive\Documents\claude-playground\tennis betting"
$Shortcut.Save()
Write-Host "Shortcut created at: $StartupPath"
