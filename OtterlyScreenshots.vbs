Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "G:\My Drive\MyProjects\screenshot_tool"
WshShell.Run """C:\Python314\pythonw.exe"" ""G:\My Drive\MyProjects\screenshot_tool\screenshot_tool_pyqt.py""", 0, False
