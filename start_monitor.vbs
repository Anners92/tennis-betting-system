Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw """ & Replace(WScript.ScriptFullName, "start_monitor.vbs", "local_monitor.py") & """", 0, False
