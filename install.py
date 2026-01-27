"""
Otterly Screenshots Installer
Installs the app as a permanent Windows feature:
- Creates desktop shortcut
- Creates Start Menu entry
- Optionally adds to Windows Startup (auto-start)
"""

import os
import sys
from pathlib import Path

def create_shortcut(shortcut_path, target_path, working_dir, icon_path=None, description=""):
    """Create a Windows shortcut using PowerShell"""
    # Use PowerShell to create shortcut (works without extra dependencies)
    ps_script = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target_path}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.Description = "{description}"
'''
    if icon_path:
        ps_script += f'$Shortcut.IconLocation = "{icon_path}"\n'
    ps_script += '$Shortcut.Save()'

    import subprocess
    result = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        capture_output=True, text=True
    )
    return result.returncode == 0

def main():
    print("=" * 50)
    print("  Otterly Screenshots Installer")
    print("=" * 50)
    print()

    # Get paths
    app_dir = Path(__file__).parent.resolve()
    python_exe = sys.executable
    script_path = app_dir / "screenshot_tool.py"
    logo_path = app_dir / "logo.png"

    # Create a batch file launcher (cleaner than calling python directly)
    launcher_path = app_dir / "OtterlyScreenshots.bat"
    launcher_content = f'''@echo off
cd /d "{app_dir}"
start "" pythonw "{script_path}"
'''
    with open(launcher_path, 'w') as f:
        f.write(launcher_content)
    print(f"Created launcher: {launcher_path}")

    # Shortcut paths
    desktop = Path.home() / "Desktop"
    start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    # 1. Desktop shortcut
    print("\n[1/3] Creating Desktop shortcut...")
    desktop_shortcut = desktop / "Otterly Screenshots.lnk"
    if create_shortcut(
        str(desktop_shortcut),
        str(launcher_path),
        str(app_dir),
        description="Otterly Screenshots - Quick screenshot tool"
    ):
        print(f"  OK: {desktop_shortcut}")
    else:
        print("  FAILED: Could not create desktop shortcut")

    # 2. Start Menu shortcut
    print("\n[2/3] Creating Start Menu entry...")
    start_menu_shortcut = start_menu / "Otterly Screenshots.lnk"
    if create_shortcut(
        str(start_menu_shortcut),
        str(launcher_path),
        str(app_dir),
        description="Otterly Screenshots - Quick screenshot tool"
    ):
        print(f"  OK: {start_menu_shortcut}")
    else:
        print("  FAILED: Could not create Start Menu entry")

    # 3. Startup (optional)
    print("\n[3/3] Auto-start with Windows?")
    response = input("  Add to Windows Startup? (y/n): ").strip().lower()
    if response == 'y':
        startup_shortcut = startup / "Otterly Screenshots.lnk"
        if create_shortcut(
            str(startup_shortcut),
            str(launcher_path),
            str(app_dir),
            description="Otterly Screenshots - Quick screenshot tool"
        ):
            print(f"  OK: {startup_shortcut}")
            print("  The app will now start automatically when Windows boots.")
        else:
            print("  FAILED: Could not add to Startup")
    else:
        print("  Skipped auto-start")

    print("\n" + "=" * 50)
    print("  Installation Complete!")
    print("=" * 50)
    print("\nYou can now:")
    print("  - Launch from Desktop shortcut")
    print("  - Search 'Otterly' in Start Menu")
    print("  - Use hotkeys: Ctrl+Shift+R (region), Ctrl+Shift+S (screen)")
    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
