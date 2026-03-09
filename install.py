"""
Otterly Screenshots Installer
Installs the app as a permanent Windows feature:
- Creates desktop shortcut
- Creates Start Menu entry
- Adds to Windows Startup (auto-start)
- Enables pin-to-all-virtual-desktops in config
"""

import os
import sys
import json
from pathlib import Path


def create_shortcut(shortcut_path, target_path, working_dir, icon_path=None, description="", arguments=""):
    """Create a Windows shortcut using PowerShell"""
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.Description = "{description}"
'''
    if arguments:
        ps_script += f"$Shortcut.Arguments = '{arguments}'\n"
    if icon_path:
        ps_script += f'$Shortcut.IconLocation = "{icon_path}"\n'
    ps_script += '$Shortcut.Save()'

    import subprocess
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True, text=True
    )
    return result.returncode == 0


def enable_pin_in_config():
    """Enable pin_to_all_desktops in the app config"""
    config_dir = Path.home() / "Pictures" / "Screenshots"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "screenshot_tool_config.json"

    config = {}
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except Exception:
            pass

    config['pin_to_all_desktops'] = True

    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


def main():
    print("=" * 50)
    print("  Otterly Screenshots Installer")
    print("=" * 50)
    print()

    # Get paths
    app_dir = Path(__file__).parent.resolve()
    script_path = app_dir / "screenshot_tool_pyqt.py"

    if not script_path.exists():
        # Fall back to original if PyQt version not present
        script_path = app_dir / "screenshot_tool.py"

    # Create a VBS launcher (no console flash, unlike .bat)
    launcher_vbs = app_dir / "OtterlyScreenshots.vbs"
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

appDir = FSO.GetParentFolderName(WScript.ScriptFullName)
venvPythonw = appDir & "\\.venv\\Scripts\\pythonw.exe"
venvPython = appDir & "\\.venv\\Scripts\\python.exe"
fallbackPythonw = "C:\\Python314\\pythonw.exe"
fallbackPython = "C:\\Python314\\python.exe"
scriptPath = appDir & "\\{script_path.name}"

WshShell.CurrentDirectory = appDir

If FSO.FileExists(venvPythonw) Then
    startTime = Timer
    exitCode = WshShell.Run(Chr(34) & venvPythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, True)
    elapsed = Timer - startTime
    If exitCode <> 0 Or elapsed < 3 Then
        If FSO.FileExists(venvPython) Then
            visibleCmd = "cmd /k " & Chr(34) & Chr(34) & venvPython & Chr(34) & " " & Chr(34) & scriptPath & Chr(34) & Chr(34)
            WshShell.Run visibleCmd, 1, False
        ElseIf FSO.FileExists(fallbackPython) Then
            visibleCmd = "cmd /k " & Chr(34) & Chr(34) & fallbackPython & Chr(34) & " " & Chr(34) & scriptPath & Chr(34) & Chr(34)
            WshShell.Run visibleCmd, 1, False
        Else
            WshShell.Popup "App exited immediately (code " & exitCode & "), and no python.exe fallback was found.", 10, "Otterly Screenshots", 16
        End If
    End If
ElseIf FSO.FileExists(fallbackPythonw) Then
    startTime = Timer
    exitCode = WshShell.Run(Chr(34) & fallbackPythonw & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, True)
    elapsed = Timer - startTime
    If exitCode <> 0 Or elapsed < 3 Then
        If FSO.FileExists(fallbackPython) Then
            visibleCmd = "cmd /k " & Chr(34) & Chr(34) & fallbackPython & Chr(34) & " " & Chr(34) & scriptPath & Chr(34) & Chr(34)
            WshShell.Run visibleCmd, 1, False
        Else
            WshShell.Popup "App exited immediately (code " & exitCode & "), and no python.exe fallback was found.", 10, "Otterly Screenshots", 16
        End If
    End If
Else
    WshShell.Popup "Python interpreter not found. Expected .venv\\Scripts\\pythonw.exe", 10, "Otterly Screenshots", 16
End If
'''
    with open(launcher_vbs, 'w') as f:
        f.write(vbs_content)
    print(f"Created launcher: {launcher_vbs}")

    # Also keep a .bat for convenience
    launcher_bat = app_dir / "OtterlyScreenshots.bat"
    bat_content = f'''@echo off
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

if exist "%APP_DIR%\\.venv\\Scripts\\pythonw.exe" (
    start "" "%APP_DIR%\\.venv\\Scripts\\pythonw.exe" "%APP_DIR%{script_path.name}"
    exit /b 0
)

if exist "C:\\Python314\\pythonw.exe" (
    start "" "C:\\Python314\\pythonw.exe" "%APP_DIR%{script_path.name}"
    exit /b 0
)

echo Python interpreter not found.
echo Expected: "%APP_DIR%\\.venv\\Scripts\\pythonw.exe"
pause
'''
    with open(launcher_bat, 'w') as f:
        f.write(bat_content)

    # Shortcut paths
    desktop = Path.home() / "Desktop"
    start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    # Use wscript.exe to run the VBS launcher (for shortcuts)
    wscript = r"C:\Windows\System32\wscript.exe"

    # 1. Desktop shortcut
    print("\n[1/4] Creating Desktop shortcut...")
    desktop_shortcut = desktop / "Otterly Screenshots.lnk"
    if create_shortcut(
        str(desktop_shortcut),
        wscript,
        str(app_dir),
        description="Otterly Screenshots - Quick screenshot tool",
        arguments=f'"{launcher_vbs}"'
    ):
        print(f"  OK: {desktop_shortcut}")
    else:
        print("  FAILED: Could not create desktop shortcut")

    # 2. Start Menu shortcut
    print("\n[2/4] Creating Start Menu entry...")
    start_menu_shortcut = start_menu / "Otterly Screenshots.lnk"
    if create_shortcut(
        str(start_menu_shortcut),
        wscript,
        str(app_dir),
        description="Otterly Screenshots - Quick screenshot tool",
        arguments=f'"{launcher_vbs}"'
    ):
        print(f"  OK: {start_menu_shortcut}")
    else:
        print("  FAILED: Could not create Start Menu entry")

    # 3. Startup - auto-start with Windows
    print("\n[3/4] Adding to Windows Startup...")
    startup_shortcut = startup / "Otterly Screenshots.lnk"
    if create_shortcut(
        str(startup_shortcut),
        wscript,
        str(app_dir),
        description="Otterly Screenshots - Quick screenshot tool",
        arguments=f'"{launcher_vbs}"'
    ):
        print(f"  OK: {startup_shortcut}")
        print("  The app will start automatically when Windows boots.")
    else:
        print("  FAILED: Could not add to Startup")

    # 4. Enable pin-to-all-desktops in config
    print("\n[4/4] Enabling pin-to-all-virtual-desktops...")
    try:
        enable_pin_in_config()
        print("  OK: App will pin itself to all virtual desktops on launch")
    except Exception as e:
        print(f"  FAILED: {e}")

    print("\n" + "=" * 50)
    print("  Installation Complete!")
    print("=" * 50)
    print("\nOtterly Screenshots will:")
    print("  - Start automatically with Windows")
    print("  - Appear on all virtual desktops")
    print("  - Be available via taskbar on every desktop")
    print("\nYou can also:")
    print("  - Launch from Desktop shortcut")
    print("  - Search 'Otterly' in Start Menu")
    print("  - Use hotkeys: Ctrl+Shift+R (region), Ctrl+Shift+S (screen)")
    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
