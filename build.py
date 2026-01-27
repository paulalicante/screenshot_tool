"""
Build script for Otterly Screenshots
Creates a standalone .exe using PyInstaller
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("=" * 50)
    print("  Building Otterly Screenshots")
    print("=" * 50)
    print()

    app_dir = Path(__file__).parent.resolve()
    script_path = app_dir / "screenshot_tool.py"
    logo_path = app_dir / "logo.png"
    dist_dir = app_dir / "dist"

    # Check if PyInstaller is installed
    print("[1/3] Checking PyInstaller...")
    try:
        import PyInstaller
        print(f"  PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("  PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("  PyInstaller installed")

    # Build command
    print("\n[2/3] Building executable...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",           # Single .exe file
        "--windowed",          # No console window
        "--name", "OtterlyScreenshots",
        "--distpath", str(dist_dir),
        "--workpath", str(app_dir / "build"),
        "--specpath", str(app_dir),
        "--clean",             # Clean cache before building
    ]

    # Add logo as data file if it exists
    if logo_path.exists():
        cmd.extend(["--add-data", f"{logo_path};."])
        print(f"  Including logo: {logo_path}")

    # Add icon if we can create one
    ico_path = app_dir / "app_icon.ico"
    if logo_path.exists():
        try:
            from PIL import Image
            img = Image.open(logo_path)
            # Create multiple sizes for better Windows icon
            img_resized = img.copy()
            img_resized.thumbnail((256, 256), Image.Resampling.LANCZOS)
            img_resized.save(ico_path, format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
            cmd.extend(["--icon", str(ico_path)])
            print(f"  Using icon: {ico_path}")
        except Exception as e:
            print(f"  Could not create icon: {e}")

    cmd.append(str(script_path))

    print(f"\n  Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = dist_dir / "OtterlyScreenshots.exe"
        print("\n" + "=" * 50)
        print("  Build Successful!")
        print("=" * 50)
        print(f"\n  Executable: {exe_path}")
        print(f"  Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
        print("\n  Share this .exe file with testers!")
        print("  They can run it directly - no Python needed.")
    else:
        print("\n  Build FAILED!")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
