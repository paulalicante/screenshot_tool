# Otterly Screenshots

A lightweight Windows screenshot tool with annotation features, built with Python and tkinter.

## Features

- **Global Hotkeys**
  - `Ctrl+Shift+R` - Capture a screen region
  - `Ctrl+Shift+S` - Capture full screen

- **Screenshot Editor** - Edit before saving with:
  - **Highlight** - Draw semi-transparent highlights (yellow, green, blue, red)
  - **Straight Line** - Lock to horizontal for clean text highlighting
  - **Circle/Oval** - Click center and drag to draw circles around items
  - **Text** - Add text annotations anywhere on the image
  - Adjustable brush/font size

- **Gallery View** - Browse recent screenshots with context menu (right-click):
  - Open - View in default image viewer
  - Edit - Re-open in editor to add more annotations (saves as new file)
  - Copy - Copy image to clipboard
  - Send - Send to configured apps
  - Move - Move to a folder
  - Delete - Remove the screenshot

- **Auto-paste to VSCode Claude** - Optional feature to automatically paste screenshots

## Installation

### Prerequisites
- Python 3.8+
- Windows 10/11

### Setup

1. Clone the repository:
   ```cmd
   git clone https://github.com/YOUR_USERNAME/screenshot_tool.git
   cd screenshot_tool
   ```

2. Install dependencies (auto-installed on first run, or manually):
   ```cmd
   pip install Pillow keyboard mss pyautogui pygetwindow pywin32
   ```

3. Run the tool:
   ```cmd
   python screenshot_tool.py
   ```

   Or double-click `run_screenshot_tool.bat`

## Usage

### Taking Screenshots

1. Press `Ctrl+Shift+R` to capture a region (click and drag to select)
2. Press `Ctrl+Shift+S` to capture the full screen
3. The editor opens automatically - add annotations or just click Save

### Editor Controls

| Tool | Description |
|------|-------------|
| Highlight | Freehand semi-transparent highlighting |
| Circle | Click center, drag outward to size |
| Text | Click to place, enter text in dialog |
| Straight Line | Checkbox - locks highlight to horizontal |
| Size | Slider - controls brush/font size |
| Colors | Yellow, Green, Blue, Red |

### Managing Screenshots

- Right-click any thumbnail to see the context menu
- Screenshots are saved to `~/Pictures/Screenshots/`
- Organize with folders and drag-and-drop
- Edited images save as new files (originals preserved)

## Screenshots Location

```
C:\Users\[YourUsername]\Pictures\Screenshots\
```

Files are named with timestamps: `screenshot_20260118_143022.png`

## Requirements

- Windows 10/11
- Python 3.8+
- Dependencies: Pillow, keyboard, mss, pyautogui, pygetwindow, pywin32

## License

MIT License - feel free to use and modify.
