"""
Otterly Screenshots Uninstaller
Removes shortcuts and startup entries (does not delete the app itself)
"""

from pathlib import Path

def main():
    print("=" * 50)
    print("  Otterly Screenshots Uninstaller")
    print("=" * 50)
    print()

    # Shortcut paths
    desktop = Path.home() / "Desktop"
    start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    app_dir = Path(__file__).parent.resolve()

    shortcuts = [
        desktop / "Otterly Screenshots.lnk",
        start_menu / "Otterly Screenshots.lnk",
        startup / "Otterly Screenshots.lnk",
        app_dir / "OtterlyScreenshots.bat",
    ]

    print("Removing shortcuts...")
    for shortcut in shortcuts:
        if shortcut.exists():
            try:
                shortcut.unlink()
                print(f"  Removed: {shortcut}")
            except Exception as e:
                print(f"  FAILED: {shortcut} - {e}")
        else:
            print(f"  Not found: {shortcut}")

    print("\n" + "=" * 50)
    print("  Uninstall Complete!")
    print("=" * 50)
    print("\nThe app files remain in:")
    print(f"  {app_dir}")
    print("\nYou can delete that folder manually if desired.")
    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
