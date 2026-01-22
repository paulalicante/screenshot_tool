"""
Screenshot Tool - A simple Windows screenshot utility
Features:
- Global hotkey (Ctrl+Shift+S) to capture full screen
- Global hotkey (Ctrl+Shift+R) to capture a region
- Auto-save with timestamps
- Auto-paste to VSCode Claude (optional)
- Thumbnail gallery to view recent screenshots
- Click thumbnails to open full images
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
from datetime import datetime
from pathlib import Path
import subprocess
import time
import traceback
import logging

# Set up crash logging
log_dir = Path.home() / "Pictures" / "Screenshots"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=log_dir / "screenshot_tool_crash.log",
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Check and install required packages
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])

try:
    from PIL import Image, ImageTk, ImageGrab
except ImportError:
    print("Installing Pillow...")
    install_package("Pillow")
    from PIL import Image, ImageTk, ImageGrab

try:
    import keyboard
except ImportError:
    print("Installing keyboard...")
    install_package("keyboard")
    import keyboard

try:
    import mss
except ImportError:
    print("Installing mss...")
    install_package("mss")
    import mss

try:
    import pyautogui
    import pygetwindow as gw
except ImportError:
    print("Installing pyautogui and pygetwindow...")
    install_package("pyautogui")
    install_package("pygetwindow")
    import pyautogui
    import pygetwindow as gw

# Optional: Virtual desktop support
try:
    from pyvda import AppView, VirtualDesktop
    PYVDA_AVAILABLE = True
except ImportError:
    PYVDA_AVAILABLE = False


class DelayCountdown:
    """Shows a countdown timer before capturing"""

    def __init__(self, seconds, callback):
        self.seconds_left = seconds
        self.callback = callback

        # Create small floating window
        self.window = tk.Toplevel()
        self.window.title("Countdown")
        self.window.attributes('-topmost', True)
        self.window.overrideredirect(True)  # No window decorations

        # Position in top-right corner of screen
        screen_w = self.window.winfo_screenwidth()
        self.window.geometry(f"150x80+{screen_w - 170}+20")

        # Style the window
        self.window.configure(bg='#333333')

        # Countdown label
        self.label = tk.Label(
            self.window,
            text=str(self.seconds_left),
            font=("Arial", 36, "bold"),
            fg="white",
            bg='#333333'
        )
        self.label.pack(expand=True)

        # Info label
        self.info_label = tk.Label(
            self.window,
            text="Set up your screen...",
            font=("Arial", 9),
            fg="#aaaaaa",
            bg='#333333'
        )
        self.info_label.pack()

        # Cancel button (small)
        cancel_btn = tk.Button(
            self.window,
            text="Cancel",
            command=self.cancel,
            font=("Arial", 8),
            bg='#555555',
            fg='white',
            relief=tk.FLAT,
            cursor='hand2'
        )
        cancel_btn.pack(pady=5)

        # Bind Escape to cancel
        self.window.bind('<Escape>', lambda e: self.cancel())

        # Start countdown
        self.tick()

    def tick(self):
        if self.seconds_left <= 0:
            self.window.destroy()
            self.callback(True)  # Capture now
            return

        self.label.config(text=str(self.seconds_left))

        # Change color as countdown progresses
        if self.seconds_left <= 2:
            self.label.config(fg='#ff5555')  # Red for last 2 seconds
        elif self.seconds_left <= 3:
            self.label.config(fg='#ffaa00')  # Orange

        self.seconds_left -= 1
        self.window.after(1000, self.tick)

    def cancel(self):
        self.window.destroy()
        self.callback(False)  # Cancelled


class WindowSelector:
    """Overlay for selecting a window to capture"""

    def __init__(self, callback):
        self.callback = callback
        self.handled = False  # Guard against multiple clicks

        # Create fullscreen semi-transparent overlay
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.15)  # Semi-transparent - enough to capture clicks
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black')

        # Instructions window (separate small window)
        self.info_window = tk.Toplevel()
        self.info_window.attributes('-topmost', True)
        self.info_window.overrideredirect(True)
        self.info_window.configure(bg='#333333')

        # Position info window at top center
        screen_w = self.info_window.winfo_screenwidth()
        self.info_window.geometry(f"350x50+{(screen_w - 350) // 2}+20")

        tk.Label(
            self.info_window,
            text="Click on any window to capture it\nPress ESC to cancel",
            font=("Arial", 11),
            fg="white",
            bg='#333333'
        ).pack(expand=True)

        # Bind click on overlay
        self.overlay.bind('<Button-1>', self.on_click)
        self.overlay.bind('<Escape>', self.on_cancel)
        self.info_window.bind('<Escape>', self.on_cancel)

        # Focus the overlay to receive clicks
        self.overlay.focus_force()
        self.overlay.lift()

    def on_click(self, event):
        """Get the window at click position"""
        # Guard against multiple click events
        if self.handled:
            return
        self.handled = True

        import win32gui
        import win32con

        # Get screen coordinates
        x, y = event.x_root, event.y_root

        # Close our overlays
        self.overlay.destroy()
        self.info_window.destroy()

        # Small delay to ensure overlay is gone
        time.sleep(0.1)

        # Get the window at this position
        hwnd = win32gui.WindowFromPoint((x, y))

        if hwnd:
            # Get the top-level parent window
            root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            if root_hwnd:
                hwnd = root_hwnd

            self.callback(hwnd)
        else:
            self.callback(None)

    def on_cancel(self, event):
        if self.handled:
            return
        self.handled = True
        self.overlay.destroy()
        self.info_window.destroy()
        self.callback(None)


class RegionSelector:
    """Fullscreen overlay for selecting a screen region - captures screen first"""

    def __init__(self, callback):
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None

        # FIRST: Capture the screen before showing any overlay
        with mss.mss() as sct:
            # Capture the primary monitor
            monitor = sct.monitors[1]  # Primary monitor
            screenshot = sct.grab(monitor)
            self.captured_image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Create fullscreen window
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black')

        # Get screen dimensions
        screen_width = self.overlay.winfo_screenwidth()
        screen_height = self.overlay.winfo_screenheight()

        # Create a dimmed version of the captured image for the overlay
        dimmed = self.captured_image.copy()
        # Apply dark overlay effect
        dark_overlay = Image.new('RGBA', dimmed.size, (0, 0, 0, 128))
        dimmed = dimmed.convert('RGBA')
        dimmed = Image.alpha_composite(dimmed, dark_overlay)
        dimmed = dimmed.convert('RGB')

        # Convert to PhotoImage for tkinter
        self.bg_photo = ImageTk.PhotoImage(dimmed)

        # Create canvas with the captured image as background
        self.canvas = tk.Canvas(
            self.overlay,
            highlightthickness=0,
            cursor='crosshair',
            width=screen_width,
            height=screen_height
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Set the dimmed screenshot as background
        self.canvas.create_image(0, 0, anchor='nw', image=self.bg_photo)

        # Instructions label
        self.label = tk.Label(
            self.overlay,
            text="Click and drag to select region. Press ESC to cancel.",
            font=("Arial", 14),
            fg="white",
            bg="black"
        )
        self.label.place(relx=0.5, y=30, anchor='center')

        # Bind events
        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.overlay.bind('<Escape>', self.on_cancel)

        # Focus the overlay
        self.overlay.focus_force()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        # Create rectangle with red outline
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline='red',
            width=2
        )

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(
                self.rect,
                self.start_x, self.start_y,
                event.x, event.y
            )

    def on_release(self, event):
        if self.start_x is None:
            return

        # Get the selected region coordinates
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)

        # Close overlay
        self.overlay.destroy()

        # Check if region is valid (at least 10x10 pixels)
        if x2 - x1 > 10 and y2 - y1 > 10:
            # Crop from the PRE-CAPTURED image (no overlay in it!)
            cropped = self.captured_image.crop((x1, y1, x2, y2))
            self.callback((x1, y1, x2, y2), cropped)
        else:
            self.callback(None, None)

    def on_cancel(self, event):
        self.overlay.destroy()
        self.callback(None, None)


class ScreenshotEditor:
    """Editor window for highlighting screenshots before saving"""

    # Highlight colors with semi-transparency (RGBA)
    COLORS = {
        'yellow': (255, 255, 0, 100),
        'green': (0, 255, 0, 100),
        'blue': (0, 150, 255, 100),
        'red': (255, 0, 0, 100),
    }

    def __init__(self, image, callback):
        """
        image: PIL Image to edit
        callback: function(edited_image or None) - None means cancelled
        """
        self.original_image = image.copy()
        self.image = image.copy().convert('RGBA')
        self.callback = callback
        self.current_color = 'yellow'
        self.drawing = False
        self.last_x = None
        self.last_y = None
        self.brush_size = 20
        self.horizontal_lock = False
        self.lock_y = None  # Y coordinate to lock to when horizontal lock is on
        self.draw_mode = 'highlight'  # 'highlight' or 'circle'
        self.center_x = None  # For circle mode
        self.center_y = None

        # Create highlight layer (transparent)
        self.highlight_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        # Preview layer for shapes being drawn (circles)
        self.preview_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))

        # Create editor window
        self.window = tk.Toplevel()
        self.window.title("Edit Screenshot - Highlighter")
        self.window.attributes('-topmost', True)

        # Calculate window size (fit to screen with some margin)
        screen_w = self.window.winfo_screenwidth() - 100
        screen_h = self.window.winfo_screenheight() - 150
        img_w, img_h = self.image.size

        # Scale if image is too large
        self.scale = min(1.0, screen_w / img_w, screen_h / img_h)
        self.display_w = int(img_w * self.scale)
        self.display_h = int(img_h * self.scale)

        # Toolbar frame
        toolbar = tk.Frame(self.window, bg='#f0f0f0', pady=5)
        toolbar.pack(fill=tk.X)

        # Color buttons
        tk.Label(toolbar, text="Highlight:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(10, 5))

        self.color_buttons = {}
        for color_name, rgba in self.COLORS.items():
            hex_color = '#{:02x}{:02x}{:02x}'.format(rgba[0], rgba[1], rgba[2])
            btn = tk.Button(
                toolbar, text="", width=3, bg=hex_color,
                relief=tk.RAISED, bd=2,
                command=lambda c=color_name: self.select_color(c)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.color_buttons[color_name] = btn

        # Highlight the default selected color
        self.color_buttons[self.current_color].config(relief=tk.SUNKEN, bd=3)

        # Mode buttons (Highlight vs Circle)
        tk.Label(toolbar, text="  Mode:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(10, 5))
        self.mode_buttons = {}

        btn_highlight = tk.Button(toolbar, text="Highlight", width=7,
                                  relief=tk.SUNKEN, bd=2,
                                  command=lambda: self.select_mode('highlight'))
        btn_highlight.pack(side=tk.LEFT, padx=2)
        self.mode_buttons['highlight'] = btn_highlight

        btn_circle = tk.Button(toolbar, text="Circle", width=7,
                               relief=tk.RAISED, bd=2,
                               command=lambda: self.select_mode('circle'))
        btn_circle.pack(side=tk.LEFT, padx=2)
        self.mode_buttons['circle'] = btn_circle

        btn_text = tk.Button(toolbar, text="Text", width=7,
                             relief=tk.RAISED, bd=2,
                             command=lambda: self.select_mode('text'))
        btn_text.pack(side=tk.LEFT, padx=2)
        self.mode_buttons['text'] = btn_text

        # Brush size
        tk.Label(toolbar, text="  Size:", bg='#f0f0f0').pack(side=tk.LEFT, padx=(10, 5))
        self.size_var = tk.IntVar(value=self.brush_size)
        size_scale = tk.Scale(toolbar, from_=5, to=50, orient=tk.HORIZONTAL,
                              variable=self.size_var, length=100, bg='#f0f0f0',
                              command=lambda v: setattr(self, 'brush_size', int(v)))
        size_scale.pack(side=tk.LEFT)

        # Horizontal lock checkbox
        self.lock_var = tk.BooleanVar(value=False)
        lock_check = tk.Checkbutton(toolbar, text="Straight Line", variable=self.lock_var,
                                    bg='#f0f0f0', activebackground='#f0f0f0',
                                    command=self.toggle_lock)
        lock_check.pack(side=tk.LEFT, padx=(15, 5))

        # Spacer
        tk.Frame(toolbar, bg='#f0f0f0').pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Save and Cancel buttons
        btn_cancel = tk.Button(toolbar, text="Cancel", bg='#f44336', fg='white',
                               command=self.cancel, padx=15)
        btn_cancel.pack(side=tk.RIGHT, padx=5)

        btn_save = tk.Button(toolbar, text="Save", bg='#4CAF50', fg='white',
                             command=self.save, padx=15)
        btn_save.pack(side=tk.RIGHT, padx=5)

        # Canvas for image
        self.canvas = tk.Canvas(self.window, width=self.display_w, height=self.display_h,
                                cursor='crosshair', bg='gray')
        self.canvas.pack(padx=10, pady=10)

        # Display the image
        self.update_display()

        # Bind mouse events
        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.window.bind('<Escape>', lambda e: self.cancel())

        # Center window
        self.window.update_idletasks()
        win_w = self.window.winfo_width()
        win_h = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() - win_w) // 2
        y = (self.window.winfo_screenheight() - win_h) // 2
        self.window.geometry(f'+{x}+{y}')

        # Focus
        self.window.focus_force()

        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

    def select_color(self, color_name):
        """Select a highlight color"""
        # Reset all buttons
        for name, btn in self.color_buttons.items():
            btn.config(relief=tk.RAISED, bd=2)
        # Highlight selected
        self.color_buttons[color_name].config(relief=tk.SUNKEN, bd=3)
        self.current_color = color_name

    def select_mode(self, mode):
        """Select drawing mode (highlight or circle)"""
        for name, btn in self.mode_buttons.items():
            btn.config(relief=tk.RAISED, bd=2)
        self.mode_buttons[mode].config(relief=tk.SUNKEN, bd=2)
        self.draw_mode = mode

    def toggle_lock(self):
        """Toggle horizontal lock mode"""
        self.horizontal_lock = self.lock_var.get()

    def update_display(self):
        """Update the canvas with current image + highlights"""
        # Composite highlight layer onto image
        display_img = Image.alpha_composite(self.image, self.highlight_layer)
        # Add preview layer (for shapes being drawn)
        display_img = Image.alpha_composite(display_img, self.preview_layer)

        # Convert to RGB for display
        display_img = display_img.convert('RGB')

        # Scale for display
        if self.scale < 1.0:
            display_img = display_img.resize((self.display_w, self.display_h), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(display_img)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

    def canvas_to_image_coords(self, x, y):
        """Convert canvas coordinates to image coordinates"""
        return int(x / self.scale), int(y / self.scale)

    def on_press(self, event):
        x, y = self.canvas_to_image_coords(event.x, event.y)

        if self.draw_mode == 'text':
            # Text mode - show dialog to enter text
            self.show_text_dialog(x, y)
            return

        self.drawing = True

        if self.draw_mode == 'circle':
            # Store center point for circle
            self.center_x, self.center_y = x, y
        else:
            # Highlight mode
            self.last_x, self.last_y = x, y
            # Lock the Y position if horizontal lock is enabled
            if self.horizontal_lock:
                self.lock_y = self.last_y
            self.draw_highlight(self.last_x, self.last_y)

    def on_drag(self, event):
        if self.drawing:
            x, y = self.canvas_to_image_coords(event.x, event.y)

            if self.draw_mode == 'circle':
                # Draw circle preview from center to current point
                self.draw_circle_preview(x, y)
            else:
                # Highlight mode
                # Use locked Y if horizontal lock is enabled
                if self.horizontal_lock and self.lock_y is not None:
                    y = self.lock_y
                self.draw_line(self.last_x, self.last_y, x, y)
                self.last_x, self.last_y = x, y

    def on_release(self, event):
        if self.drawing and self.draw_mode == 'circle':
            # Commit the circle to the highlight layer
            x, y = self.canvas_to_image_coords(event.x, event.y)
            self.commit_circle(x, y)

        self.drawing = False
        self.last_x = None
        self.last_y = None
        self.lock_y = None
        self.center_x = None
        self.center_y = None

    def draw_highlight(self, x, y):
        """Draw a highlight circle at position"""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]
        r = self.brush_size // 2
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
        self.update_display()

    def draw_line(self, x1, y1, x2, y2):
        """Draw a highlight line between two points"""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]
        draw.line([x1, y1, x2, y2], fill=color, width=self.brush_size)
        # Draw circles at endpoints for smooth lines
        r = self.brush_size // 2
        draw.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=color)
        self.update_display()

    def draw_circle_preview(self, x, y):
        """Draw a preview of the circle/oval being created"""
        from PIL import ImageDraw
        # Clear preview layer
        self.preview_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.preview_layer)
        color = self.COLORS[self.current_color]

        # Calculate radii based on distance from center
        rx = abs(x - self.center_x)
        ry = abs(y - self.center_y)

        if rx > 2 or ry > 2:  # Only draw if dragged a bit
            # Draw ellipse outline (thicker line for visibility)
            bbox = [self.center_x - rx, self.center_y - ry,
                    self.center_x + rx, self.center_y + ry]
            # Draw with stroke width based on brush size
            for offset in range(self.brush_size // 2):
                draw.ellipse([bbox[0] - offset, bbox[1] - offset,
                             bbox[2] + offset, bbox[3] + offset],
                            outline=color)

        self.update_display()

    def commit_circle(self, x, y):
        """Commit the circle to the highlight layer"""
        from PIL import ImageDraw
        # Clear preview
        self.preview_layer = Image.new('RGBA', self.image.size, (0, 0, 0, 0))

        # Draw final circle on highlight layer
        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]

        rx = abs(x - self.center_x)
        ry = abs(y - self.center_y)

        if rx > 2 or ry > 2:
            bbox = [self.center_x - rx, self.center_y - ry,
                    self.center_x + rx, self.center_y + ry]
            # Draw with stroke width
            for offset in range(self.brush_size // 2):
                draw.ellipse([bbox[0] - offset, bbox[1] - offset,
                             bbox[2] + offset, bbox[3] + offset],
                            outline=color)

        self.update_display()

    def show_text_dialog(self, x, y):
        """Show a dialog to enter text, then draw it at position"""
        from tkinter import simpledialog

        # Ask for text input
        text = simpledialog.askstring(
            "Add Text",
            "Enter text to add:",
            parent=self.window
        )

        if text:
            self.draw_text(x, y, text)

    def draw_text(self, x, y, text):
        """Draw text at the specified position"""
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(self.highlight_layer)
        color = self.COLORS[self.current_color]

        # Use brush_size to determine font size (scaled up for readability)
        font_size = self.brush_size * 2

        # Try to load a nice font, fall back to default
        try:
            # Try common Windows fonts
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except:
                # Fall back to default font
                font = ImageFont.load_default()

        # Draw text with a slight outline for better visibility
        # Draw outline by drawing text offset in each direction
        outline_color = (0, 0, 0, 150)  # Semi-transparent black
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        # Draw main text
        draw.text((x, y), text, font=font, fill=color)

        self.update_display()

    def save(self):
        """Save the edited image"""
        # Composite and convert to RGB
        final_image = Image.alpha_composite(self.image, self.highlight_layer)
        final_image = final_image.convert('RGB')
        self.window.destroy()
        self.callback(final_image)

    def cancel(self):
        """Cancel editing"""
        self.window.destroy()
        self.callback(None)


class ScreenshotTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screenshot Tool v1.05")
        self.root.geometry("600x550")
        self.root.minsize(400, 350)

        # Set up save directory
        self.save_dir = Path.home() / "Pictures" / "Screenshots"
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Push targets configuration
        self.config_file = self.save_dir / "screenshot_tool_config.json"
        self.push_targets = self.load_push_targets()

        # Hotkey configuration
        self.hotkey_full = "ctrl+shift+s"
        self.hotkey_region = "ctrl+shift+r"
        self.hotkey_window = "ctrl+shift+w"
        self.hotkeys_registered = False
        self._capture_in_progress = False  # Prevent multiple simultaneous captures

        # Screenshot counter for this session
        self.screenshot_count = 0

        # Auto-send settings
        self.auto_send_enabled = tk.BooleanVar(value=False)
        self.auto_send_target = tk.StringVar(value="")

        # Edit before save setting (default: True - show editor)
        self.edit_before_save = tk.BooleanVar(value=True)

        # Pin to all desktops setting
        self.pin_to_all_desktops = tk.BooleanVar(value=False)

        # Silent capture - don't switch desktop after capture
        self.silent_capture = tk.BooleanVar(value=False)

        # Drag and drop state
        self.drag_data = {"filepath": None, "widget": None}
        self.drag_label = None  # Floating label during drag
        self.folder_drop_targets = {}  # folder_name -> button widget

        # Track all floating windows for cleanup
        self.floating_windows = []

        # Build the UI
        self.setup_ui()

        # Apply pin setting after window is created
        self.root.after(500, self.apply_pin_setting)

        # Register global hotkeys
        self.register_hotkeys()

        # Load existing screenshots
        self.refresh_gallery()

        # Periodic cleanup of floating windows (every 5 seconds)
        self.schedule_cleanup()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Initialize settings variables (needed for settings dialog)
        self.capture_mode_var = tk.StringVar(value="Region")
        self.delay_var = tk.StringVar(value="0")
        self.thumbnail_scale = tk.IntVar(value=5)  # 1-10, 5 = current size (120x90)
        self.disk_limit_mb = tk.IntVar(value=500)  # Max disk space in MB
        self.archive_days = tk.IntVar(value=30)  # Days before suggesting cleanup

        # Create horizontal layout: left sidebar + right content
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT SIDEBAR
        sidebar = ttk.Frame(content_frame, padding="5")
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Spacer to align buttons with first row of thumbnails (leaves room for logo)
        ttk.Frame(sidebar, height=110).pack()

        # Sidebar buttons - stacked vertically
        btn_width = 20
        ttk.Button(
            sidebar, text="Region (Ctrl+Shift+R)",
            command=self.start_region_capture, width=btn_width
        ).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(
            sidebar, text="Screen (Ctrl+Shift+S)",
            command=self.capture_fullscreen, width=btn_width
        ).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(
            sidebar, text="Window (Ctrl+Shift+W)",
            command=self.start_window_capture, width=btn_width
        ).pack(fill=tk.X, pady=(0, 15))

        ttk.Button(
            sidebar, text="Import from File",
            command=self.import_image, width=btn_width
        ).pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            sidebar, text="Paste from Clipboard",
            command=self.paste_from_clipboard, width=btn_width
        ).pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            sidebar, text="\u2699 Settings",
            command=self.show_settings, width=btn_width
        ).pack(fill=tk.X, pady=(0, 15))

        # Disk usage indicator in sidebar
        self.disk_usage_var = tk.StringVar(value="")
        self.disk_label = tk.Label(sidebar, textvariable=self.disk_usage_var, font=("", 8), fg="gray")
        self.disk_label.pack(pady=(5, 0))

        # Spacer to push counter to bottom
        ttk.Frame(sidebar).pack(fill=tk.BOTH, expand=True)

        # Counter display at bottom of sidebar
        self.counter_var = tk.StringVar(value="Session: 0")
        counter_label = ttk.Label(sidebar, textvariable=self.counter_var, font=("", 8))
        counter_label.pack(pady=(10, 0))

        # VERTICAL DIVIDER
        divider = ttk.Separator(content_frame, orient=tk.VERTICAL)
        divider.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # RIGHT CONTENT AREA
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(right_frame, textvariable=self.status_var, foreground="gray")
        status_label.pack(fill=tk.X, pady=(0, 5))

        # Current folder filter (None = show all)
        self.current_folder = None

        # Folder bar
        folder_bar = ttk.Frame(right_frame)
        folder_bar.pack(fill=tk.X, pady=(0, 5))

        # Container for folder buttons (will be refreshed)
        self.folder_buttons_frame = ttk.Frame(folder_bar)
        self.folder_buttons_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # New folder button
        ttk.Button(folder_bar, text="+", width=3, command=self.create_new_folder).pack(side=tk.RIGHT, padx=(5, 0))

        # Build initial folder buttons
        self.refresh_folder_bar()

        # Canvas with scrollbar for gallery
        gallery_container = tk.Frame(right_frame, relief=tk.SUNKEN, bd=1, bg="#e8e8e8")
        gallery_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(gallery_container, bg="#f5f5f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(gallery_container, orient=tk.VERTICAL, command=self.canvas.yview)

        self.gallery_frame = tk.Frame(self.canvas, bg="#f5f5f5")

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.gallery_frame, anchor=tk.NW)

        # Configure canvas scrolling
        self.gallery_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

    def on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def register_hotkeys(self):
        try:
            keyboard.add_hotkey(self.hotkey_full, self.capture_fullscreen_threadsafe)
            keyboard.add_hotkey(self.hotkey_region, self.start_region_capture_threadsafe)
            keyboard.add_hotkey(self.hotkey_window, self.start_window_capture_threadsafe)
            self.hotkeys_registered = True
            print(f"Global hotkeys registered:")
            print(f"  {self.hotkey_region} - Region capture")
            print(f"  {self.hotkey_full} - Full screen capture")
            print(f"  {self.hotkey_window} - Window capture")
        except Exception as e:
            print(f"Failed to register hotkeys: {e}")
            self.status_var.set(f"Warning: Could not register global hotkeys - {e}")

    def unregister_hotkeys(self):
        if self.hotkeys_registered:
            try:
                keyboard.remove_hotkey(self.hotkey_full)
                keyboard.remove_hotkey(self.hotkey_region)
                keyboard.remove_hotkey(self.hotkey_window)
            except:
                pass

    def start_window_capture_threadsafe(self):
        # Prevent multiple hotkey triggers
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        # Delay to allow hotkey keys to be released before showing selector
        self.root.after(150, self.start_window_capture)

    def capture_fullscreen_threadsafe(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self.root.after(0, self.capture_fullscreen)

    def start_region_capture_threadsafe(self):
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self.root.after(0, self.start_region_capture)

    def do_capture(self):
        """Dispatch capture based on selected mode"""
        mode = self.capture_mode_var.get()
        if mode == "Region":
            self.start_region_capture()
        elif mode == "Window":
            self.start_window_capture()
        elif mode == "Full Screen":
            self.capture_fullscreen()

    def start_window_capture(self):
        """Start the window selection process"""
        delay = int(self.delay_var.get())

        if delay > 0:
            self.status_var.set(f"Countdown: {delay} seconds - set up your screen!")
            self.root.iconify()
            self.root.after(200, lambda: DelayCountdown(delay, self._on_window_delay_complete))
        else:
            self.status_var.set("Click on a window to capture...")
            self.root.update()
            self.root.iconify()
            self.root.after(200, self._show_window_selector)

    def _on_window_delay_complete(self, proceed):
        """Called when window delay countdown finishes"""
        if proceed:
            self._show_window_selector()
        else:
            self.root.deiconify()
            self.status_var.set("Capture cancelled")

    def _show_window_selector(self):
        """Show the window selector overlay"""
        WindowSelector(self.on_window_selected)

    def on_window_selected(self, hwnd):
        """Called when window selection is complete"""
        self._capture_in_progress = False  # Reset flag

        if hwnd is None:
            self.status_var.set("Window capture cancelled")
            if not self.silent_capture.get():
                self.root.deiconify()
            return

        # Only restore window if not in silent capture mode (and not using editor)
        if not self.silent_capture.get() or self.edit_before_save.get():
            self.root.deiconify()

        self.capture_window(hwnd)

    def capture_window(self, hwnd):
        """Capture a specific window by its handle"""
        import win32gui
        import win32ui
        import win32con
        from ctypes import windll

        try:
            self.status_var.set("Capturing window...")
            self.root.update()

            # Get window rectangle
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                self.status_var.set("Invalid window dimensions")
                return

            # Bring window to front briefly to ensure it's visible
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)
            except:
                pass

            # Capture using mss (more reliable)
            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            error_msg = f"Error capturing window: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def start_region_capture(self):
        """Start the region selection process"""
        delay = int(self.delay_var.get())

        if delay > 0:
            # Start countdown, then capture region
            self.status_var.set(f"Countdown: {delay} seconds - set up your screen!")
            self.root.iconify()
            self.root.after(200, lambda: DelayCountdown(delay, self._on_region_delay_complete))
        else:
            # No delay - capture immediately
            self.status_var.set("Select a region...")
            self.root.update()
            self.root.iconify()
            self.root.after(200, self._show_region_selector)

    def _on_region_delay_complete(self, proceed):
        """Called when region delay countdown finishes"""
        if proceed:
            self._show_region_selector()
        else:
            self.root.deiconify()
            self.status_var.set("Capture cancelled")

    def _show_region_selector(self):
        """Show the region selector overlay"""
        RegionSelector(self.on_region_selected)

    def on_region_selected(self, region, cropped_image):
        """Called when region selection is complete"""
        self._capture_in_progress = False  # Reset flag

        # Only restore main window if not in silent capture mode
        if not self.silent_capture.get():
            self.root.deiconify()

        if region is None or cropped_image is None:
            self.status_var.set("Region capture cancelled")
            if not self.silent_capture.get():
                self.root.deiconify()  # Show window on cancel
            return

        # Image is already captured and cropped by RegionSelector
        # Open editor or save directly
        if self.edit_before_save.get():
            self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
            # Editor needs window visible
            self.root.deiconify()
            ScreenshotEditor(cropped_image, self.on_editor_complete)
        else:
            self.save_screenshot(cropped_image)

    def capture_region(self, x1, y1, x2, y2):
        """Capture a specific region of the screen"""
        try:
            self.status_var.set("Capturing region...")
            self.root.update()

            # Small delay to ensure overlay is fully gone
            self.root.after(100)

            # Capture the region using mss
            with mss.mss() as sct:
                monitor = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            error_msg = f"Error capturing region: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def capture_fullscreen(self):
        """Capture the entire screen"""
        delay = int(self.delay_var.get())

        if delay > 0:
            # Start countdown, then capture
            self.status_var.set(f"Countdown: {delay} seconds - set up your screen!")
            self.root.iconify()
            self.root.after(200, lambda: DelayCountdown(delay, self._on_fullscreen_delay_complete))
        else:
            # No delay - hide window briefly then capture
            self.root.iconify()
            self.root.after(150, self._do_fullscreen_capture)

    def _on_fullscreen_delay_complete(self, proceed):
        """Called when fullscreen delay countdown finishes"""
        if proceed:
            self._do_fullscreen_capture()
        else:
            self._capture_in_progress = False  # Reset flag
            self.root.deiconify()
            self.status_var.set("Capture cancelled")

    def _do_fullscreen_capture(self):
        """Actually capture the fullscreen"""
        self._capture_in_progress = False  # Reset flag
        try:
            self.status_var.set("Capturing...")
            self.root.update()

            # Brief delay to allow any UI to settle
            self.root.after(100)

            # Capture the screen using mss (faster than PIL)
            with mss.mss() as sct:
                # Capture all monitors
                screenshot = sct.grab(sct.monitors[0])  # Monitor 0 = all monitors combined
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Open editor or save directly
            if self.edit_before_save.get():
                # Editor needs window visible
                self.root.deiconify()
                self.status_var.set("Edit screenshot (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                # Only restore window if not in silent capture mode
                if not self.silent_capture.get():
                    self.root.deiconify()
                self.save_screenshot(img)

        except Exception as e:
            self.root.deiconify()
            error_msg = f"Error capturing screenshot: {e}"
            self.status_var.set(error_msg)
            print(error_msg)
            messagebox.showerror("Error", error_msg)

    def on_editor_complete(self, edited_image):
        """Called when editor is done - save if image provided, discard if None"""
        if edited_image is None:
            self.status_var.set("Screenshot discarded")
            return

        # Save the edited image
        self.save_screenshot(edited_image)

    def save_screenshot(self, img):
        """Save a screenshot image to disk and copy to clipboard"""
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

        # Save to current folder if one is selected, otherwise root
        if self.current_folder:
            save_dir = self.save_dir / self.current_folder
            save_dir.mkdir(exist_ok=True)
        else:
            save_dir = self.save_dir
        filepath = save_dir / filename

        # Save the image
        img.save(str(filepath), "PNG")

        # Copy to clipboard for easy pasting
        self.copy_to_clipboard(img)

        # Update counter
        self.screenshot_count += 1
        self.counter_var.set(f"Screenshots this session: {self.screenshot_count}")

        # Update status
        folder_info = f" [{self.current_folder}]" if self.current_folder else ""
        self.status_var.set(f"Saved{folder_info} & copied: {filename}")

        # Refresh gallery
        self.refresh_gallery()

        # Flash effect / notification
        self.flash_notification()

        print(f"Screenshot saved: {filepath}")
        print("Image copied to clipboard - ready to paste!")

        # Auto-send to target if enabled
        if self.auto_send_enabled.get():
            target_name = self.auto_send_target.get()
            target = next((t for t in self.push_targets if t['name'] == target_name), None)
            if target:
                self.root.after(200, lambda: self.paste_to_target(target))

    def copy_to_clipboard(self, img):
        """Copy image to Windows clipboard using pywin32"""
        import io
        import win32clipboard

        try:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Save as BMP to memory
            output = io.BytesIO()
            img.save(output, 'BMP')
            bmp_data = output.getvalue()
            output.close()

            # Skip BMP file header (14 bytes) to get DIB data
            dib_data = bmp_data[14:]

            # Use win32clipboard (much more reliable than ctypes)
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib_data)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Clipboard error (image still saved): {e}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass

    def load_push_targets(self):
        """Load push targets from config file"""
        import json
        default_targets = [
            {
                "name": "VSCode Claude",
                "title_pattern": "Visual Studio Code",
                "click_x": None,  # None = don't click, just paste
                "click_y": None,
                "enabled": True
            },
            {
                "name": "WhatsApp",
                "title_pattern": "WhatsApp",
                "click_x": None,
                "click_y": None,
                "enabled": True
            },
            {
                "name": "Discord",
                "title_pattern": "Discord",
                "click_x": None,
                "click_y": None,
                "enabled": True
            },
            {
                "name": "Slack",
                "title_pattern": "Slack",
                "click_x": None,
                "click_y": None,
                "enabled": True
            },
            {
                "name": "Microsoft Teams",
                "title_pattern": "Microsoft Teams",
                "click_x": None,
                "click_y": None,
                "enabled": True
            }
        ]

        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get('push_targets', default_targets)
        except Exception as e:
            print(f"Error loading config: {e}")

        return default_targets

    def save_push_targets(self):
        """Save push targets and settings to config file"""
        import json
        try:
            config = {
                'push_targets': self.push_targets,
                'pin_to_all_desktops': self.pin_to_all_desktops.get(),
                'auto_send_enabled': self.auto_send_enabled.get(),
                'auto_send_target': self.auto_send_target.get(),
                'edit_before_save': self.edit_before_save.get(),
                'silent_capture': self.silent_capture.get()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def paste_to_target(self, target):
        """Paste clipboard content to a registered target application"""
        try:
            import win32gui
            import win32con

            # Find window by title pattern - search all windows
            hwnd = None
            target_pattern = target['title_pattern'].lower()

            def enum_callback(h, results):
                if win32gui.IsWindowVisible(h):
                    title = win32gui.GetWindowText(h)
                    if target_pattern in title.lower():
                        results.append(h)
                return True

            results = []
            win32gui.EnumWindows(enum_callback, results)

            if not results:
                self.status_var.set(f"'{target['name']}' window not found")
                return False

            hwnd = results[0]

            # Move target window to CURRENT desktop if pyvda is available
            if PYVDA_AVAILABLE:
                try:
                    current_desktop = VirtualDesktop.current()
                    target_view = AppView(hwnd)
                    target_desktop = target_view.desktop
                    # Only move if on a different desktop
                    if target_desktop and target_desktop != current_desktop:
                        target_view.move(current_desktop)
                        time.sleep(0.15)  # Give move time to complete
                except Exception as e:
                    print(f"Move to current desktop failed (continuing anyway): {e}")

            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)

            # Bring window to foreground - use robust method
            self._force_foreground_window(hwnd)

            time.sleep(0.2)

            # Click at position if specified
            if target.get('click_x') is not None and target.get('click_y') is not None:
                # Get window position
                rect = win32gui.GetWindowRect(hwnd)
                win_x, win_y = rect[0], rect[1]
                win_width = rect[2] - rect[0]
                win_height = rect[3] - rect[1]

                # Calculate click position based on offset type
                if target.get('offset_type') == 'relative_bottom_center':
                    click_x = win_x + win_width // 2 + target['click_x']
                    click_y = win_y + win_height + target['click_y']
                else:  # absolute from top-left
                    click_x = win_x + target['click_x']
                    click_y = win_y + target['click_y']

                pyautogui.click(click_x, click_y)
                time.sleep(0.1)

            # Paste
            pyautogui.hotkey('ctrl', 'v')
            self.status_var.set(f"Pasted to {target['name']}!")
            return True

        except Exception as e:
            self.status_var.set(f"Paste to {target['name']} failed: {e}")
            print(f"Paste error: {e}")
            return False

    def _force_foreground_window(self, hwnd):
        """Force a window to foreground by clicking on it"""
        import win32gui
        import win32con

        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)

            # Get window rectangle
            rect = win32gui.GetWindowRect(hwnd)

            # Click in the center of the window to activate it
            center_x = (rect[0] + rect[2]) // 2
            center_y = (rect[1] + rect[3]) // 2

            # Move mouse and click to activate window
            pyautogui.click(center_x, center_y)
            time.sleep(0.15)

        except Exception as e:
            print(f"Foreground switch error: {e}")

    def send_to_target(self, screenshot_path, target_name):
        """Copy image to clipboard and send to target"""
        try:
            # Load image and copy to clipboard
            img = Image.open(screenshot_path)
            self.copy_to_clipboard(img)

            # Find target
            target = next((t for t in self.push_targets if t['name'] == target_name), None)
            if target:
                self.root.after(100, lambda: self.paste_to_target(target))
        except Exception as e:
            self.status_var.set(f"Send failed: {e}")

    def register_new_target(self, on_complete=None):
        """Start the target registration process"""
        # Create instruction window
        reg_win = tk.Toplevel(self.root)
        reg_win.title("Register Push Target")
        reg_win.geometry("400x180")
        reg_win.transient(self.root)
        reg_win.attributes('-topmost', True)
        # Center on parent
        reg_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2
        reg_win.geometry(f"+{x}+{y}")

        frame = ttk.Frame(reg_win, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="Register a New Push Target",
            font=("", 12, "bold")
        ).pack(pady=(0, 15))

        ttk.Label(
            frame,
            text="Normal: Match window title and paste\n"
                 "(works for most apps)\n\n"
                 "Advanced: Capture exact click position\n"
                 "(for apps that need a specific input field)",
            justify=tk.LEFT
        ).pack(pady=(0, 15))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        def normal_mode():
            reg_win.destroy()
            self.register_simple_target(on_complete)

        def advanced_mode():
            reg_win.destroy()
            self.capture_target_position(on_complete)

        ttk.Button(btn_frame, text="Normal", command=normal_mode).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Advanced", command=advanced_mode).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=reg_win.destroy).pack(side=tk.LEFT, padx=5)

    def register_simple_target(self, on_complete=None):
        """Register a target with just window title matching (no click position)"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Push Target")
        dialog.geometry("350x200")
        dialog.transient(self.root)

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 350) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Target Name:").pack(anchor=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=40).pack(fill=tk.X, pady=(0, 10))

        ttk.Label(frame, text="Window Title Contains:").pack(anchor=tk.W)
        title_var = tk.StringVar()
        ttk.Entry(frame, textvariable=title_var, width=40).pack(fill=tk.X, pady=(0, 15))

        def save():
            name = name_var.get().strip()
            title = title_var.get().strip()
            if name and title:
                self.push_targets.append({
                    "name": name,
                    "title_pattern": title,
                    "click_x": None,
                    "click_y": None,
                    "enabled": True
                })
                self.save_push_targets()
                messagebox.showinfo("Success", f"Target '{name}' added!")
                dialog.destroy()
                if on_complete:
                    on_complete()
            else:
                messagebox.showwarning("Missing Info", "Please fill in both fields")

        ttk.Button(frame, text="Save", command=save).pack()

    def capture_target_position(self, on_complete=None):
        """Capture the target window and click position"""
        # Register temporary hotkey
        self.status_var.set("Click in target app, then press Ctrl+Shift+T...")
        self.root.iconify()

        def on_capture():
            try:
                import win32gui
                # Get foreground window
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                rect = win32gui.GetWindowRect(hwnd)

                # Get mouse position
                mouse_x, mouse_y = pyautogui.position()

                # Calculate offset from window top-left
                offset_x = mouse_x - rect[0]
                offset_y = mouse_y - rect[1]

                # Unregister hotkey
                keyboard.remove_hotkey('ctrl+shift+t')

                # Show dialog to name the target
                self.root.deiconify()
                self.root.after(100, lambda: self.finish_target_registration(
                    title, offset_x, offset_y, on_complete
                ))

            except Exception as e:
                print(f"Capture error: {e}")
                self.root.deiconify()

        keyboard.add_hotkey('ctrl+shift+t', on_capture)

    def finish_target_registration(self, window_title, offset_x, offset_y, on_complete=None):
        """Complete the target registration with a name dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Name Your Target")
        dialog.geometry("350x220")
        dialog.transient(self.root)

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 350) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 220) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=f"Window: {window_title[:40]}...").pack(anchor=tk.W)
        ttk.Label(frame, text=f"Click position: ({offset_x}, {offset_y})").pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(frame, text="Target Name:").pack(anchor=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=name_var, width=40).pack(fill=tk.X, pady=(0, 10))

        # Extract a reasonable title pattern
        title_pattern = window_title.split(" - ")[0] if " - " in window_title else window_title[:30]
        ttk.Label(frame, text="Window Title Pattern:").pack(anchor=tk.W)
        pattern_var = tk.StringVar(value=title_pattern)
        ttk.Entry(frame, textvariable=pattern_var, width=40).pack(fill=tk.X, pady=(0, 15))

        def save():
            name = name_var.get().strip()
            pattern = pattern_var.get().strip()
            if name and pattern:
                self.push_targets.append({
                    "name": name,
                    "title_pattern": pattern,
                    "click_x": offset_x,
                    "click_y": offset_y,
                    "offset_type": "absolute_from_top_left",
                    "enabled": True
                })
                self.save_push_targets()
                messagebox.showinfo("Success", f"Target '{name}' added!")
                dialog.destroy()
                if on_complete:
                    on_complete()

        ttk.Button(frame, text="Save Target", command=save).pack()

    def import_image(self):
        """Import an existing image from disk"""
        filetypes = [
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg *.jpeg"),
            ("All files", "*.*")
        ]

        filepath = filedialog.askopenfilename(
            title="Select Image to Import",
            filetypes=filetypes,
            initialdir=str(Path.home() / "Pictures")
        )

        if not filepath:
            return  # User cancelled

        try:
            # Load the image
            img = Image.open(filepath)

            # Convert to RGB if necessary (for consistency)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            self.status_var.set(f"Imported: {Path(filepath).name}")

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit imported image (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            error_msg = f"Error importing image: {e}"
            self.status_var.set(error_msg)
            messagebox.showerror("Import Error", error_msg)

    def paste_from_clipboard(self):
        """Import an image from the clipboard"""
        from PIL import ImageGrab

        try:
            # Try to get image from clipboard
            img = ImageGrab.grabclipboard()

            if img is None:
                self.status_var.set("No image in clipboard")
                messagebox.showinfo("Paste", "No image found in clipboard")
                return

            # Check if it's actually an image
            if not isinstance(img, Image.Image):
                # Sometimes it returns a list of file paths
                if isinstance(img, list) and len(img) > 0:
                    # Try to open the first file
                    img = Image.open(img[0])
                else:
                    self.status_var.set("Clipboard doesn't contain an image")
                    messagebox.showinfo("Paste", "Clipboard doesn't contain an image")
                    return

            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            self.status_var.set("Pasted image from clipboard")

            # Open editor or save directly
            if self.edit_before_save.get():
                self.status_var.set("Edit pasted image (add highlights, then Save or Cancel)")
                ScreenshotEditor(img, self.on_editor_complete)
            else:
                self.save_screenshot(img)

        except Exception as e:
            error_msg = f"Error pasting from clipboard: {e}"
            self.status_var.set(error_msg)
            messagebox.showerror("Paste Error", error_msg)

    def flash_notification(self):
        # Brief visual flash to confirm capture
        original_bg = self.root.cget("bg")
        self.root.configure(bg="green")
        self.root.after(100, lambda: self.root.configure(bg=original_bg))

    def apply_pin_setting(self):
        """Load settings from config file"""
        import json
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.pin_to_all_desktops.set(config.get('pin_to_all_desktops', False))
                    self.auto_send_enabled.set(config.get('auto_send_enabled', False))
                    self.auto_send_target.set(config.get('auto_send_target', ''))
                    self.edit_before_save.set(config.get('edit_before_save', True))
                    self.silent_capture.set(config.get('silent_capture', False))
        except Exception as e:
            print(f"Error loading settings: {e}")

    def pin_window(self):
        """Pin the window to appear on all virtual desktops"""
        global PYVDA_AVAILABLE, AppView, VirtualDesktop
        import win32gui

        if not PYVDA_AVAILABLE:
            # Try to install pyvda
            try:
                print("Installing pyvda for virtual desktop support...")
                install_package("pyvda")
                from pyvda import AppView, VirtualDesktop
                PYVDA_AVAILABLE = True
            except Exception as e:
                self._show_manual_pin_instructions()
                self.pin_to_all_desktops.set(False)
                return False

        try:
            # Make sure window is visible and get proper handle
            self.root.update()
            self.root.lift()

            # Try to find our window by title (more reliable than winfo_id)
            hwnd = win32gui.FindWindow(None, self.root.title())

            if not hwnd:
                # Fallback to winfo_id
                hwnd = int(self.root.winfo_id())
                # Get the root/parent window
                parent = win32gui.GetParent(hwnd)
                if parent:
                    hwnd = parent

            print(f"Attempting to pin window with hwnd: {hwnd}")

            # Pin using pyvda
            view = AppView(hwnd)
            view.pin()
            self.status_var.set("Window pinned to all desktops")
            return True
        except Exception as e:
            print(f"Pin failed: {e}")
            self._show_manual_pin_instructions()
            self.pin_to_all_desktops.set(False)
            return False

    def _show_manual_pin_instructions(self):
        """Show instructions for manually pinning the window"""
        messagebox.showinfo(
            "Pin to All Desktops",
            "Automatic pinning not available.\n\n"
            "To pin manually:\n"
            "1. Press Win+Tab to open Task View\n"
            "2. Right-click on this app's window\n"
            "3. Select 'Show this window on all desktops'\n\n"
            "Or: Right-click the app icon in taskbar → "
            "hover over the window preview → right-click → "
            "'Show this window on all desktops'"
        )

    def unpin_window(self):
        """Unpin the window from all virtual desktops"""
        if not PYVDA_AVAILABLE:
            return False

        try:
            hwnd = int(self.root.winfo_id())
            view = AppView(hwnd)
            view.unpin()
            self.status_var.set("Window unpinned from all desktops")
            return True
        except Exception as e:
            print(f"Unpin failed: {e}")
            return False

    def toggle_pin(self):
        """Toggle pin to all desktops - show instructions"""
        if self.pin_to_all_desktops.get():
            # Just show instructions - auto-pin is unreliable with tkinter
            self._show_manual_pin_instructions()
        # Save the setting (as a reminder that user wanted this)
        self.save_push_targets()

    def get_thumbnail_size(self):
        """Calculate thumbnail size based on scale (1-10)"""
        scale = self.thumbnail_scale.get()
        base_width, base_height = 120, 90  # Default size at scale 5

        # Scale 1 = 50% (0.5x), Scale 5 = 100% (1.0x), Scale 10 = 300% (3.0x)
        if scale <= 5:
            factor = 0.5 + (scale - 1) * 0.5 / 4
        else:
            factor = 1.0 + (scale - 5) * 2.0 / 5

        return (int(base_width * factor), int(base_height * factor))

    def update_disk_usage(self, show_warning=True):
        """Calculate and display total size of screenshots with color coding"""
        try:
            total_bytes = sum(f.stat().st_size for f in self.save_dir.glob("screenshot_*.png"))
            limit_bytes = self.disk_limit_mb.get() * 1024 * 1024
            usage_percent = (total_bytes / limit_bytes * 100) if limit_bytes > 0 else 0

            # Format size nicely
            if total_bytes < 1024:
                size_str = f"{total_bytes} B"
            elif total_bytes < 1024 * 1024:
                size_str = f"{total_bytes / 1024:.1f} KB"
            elif total_bytes < 1024 * 1024 * 1024:
                size_str = f"{total_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_bytes / (1024 * 1024 * 1024):.2f} GB"

            # Show usage with percentage
            limit_mb = self.disk_limit_mb.get()
            self.disk_usage_var.set(f"📁 {size_str} / {limit_mb} MB")

            # Color based on usage percentage
            if usage_percent < 50:
                color = "#228B22"  # Forest green
            elif usage_percent < 70:
                color = "#DAA520"  # Goldenrod (yellow-orange)
            elif usage_percent < 90:
                color = "#FF8C00"  # Dark orange
            else:
                color = "#DC143C"  # Crimson red

            self.disk_label.config(fg=color)

            # Show cleanup prompt at 90% (only once per session or when triggered)
            if show_warning and usage_percent >= 90 and not getattr(self, '_cleanup_prompted', False):
                self._cleanup_prompted = True
                self.root.after(500, self.prompt_cleanup)

        except:
            self.disk_usage_var.set("")

    def prompt_cleanup(self):
        """Prompt user to clean up old screenshots"""
        days = self.archive_days.get()
        result = messagebox.askyesno(
            "Disk Space Warning",
            f"Screenshot storage is over 90% of limit.\n\n"
            f"Would you like to delete screenshots older than {days} days?",
            icon="warning"
        )
        if result:
            self.cleanup_old_screenshots()

    def cleanup_old_screenshots(self):
        """Delete screenshots older than archive_days setting"""
        import datetime
        days = self.archive_days.get()
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        deleted_count = 0
        deleted_bytes = 0

        try:
            for f in self.save_dir.glob("screenshot_*.png"):
                file_time = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                if file_time < cutoff:
                    deleted_bytes += f.stat().st_size
                    f.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                size_mb = deleted_bytes / (1024 * 1024)
                messagebox.showinfo(
                    "Cleanup Complete",
                    f"Deleted {deleted_count} screenshot(s)\n"
                    f"Freed {size_mb:.1f} MB of space"
                )
                self._cleanup_prompted = False  # Allow future prompts
                self.refresh_gallery()
            else:
                messagebox.showinfo(
                    "Cleanup Complete",
                    f"No screenshots older than {days} days found."
                )
        except Exception as e:
            messagebox.showerror("Error", f"Cleanup failed: {e}")

    def manual_cleanup(self):
        """Manually trigger cleanup with confirmation"""
        days = self.archive_days.get()
        result = messagebox.askyesno(
            "Confirm Cleanup",
            f"Delete all screenshots older than {days} days?",
            icon="question"
        )
        if result:
            self.cleanup_old_screenshots()

    # ==================== FOLDER MANAGEMENT ====================

    def get_folders(self):
        """Get list of subfolders in the screenshot directory"""
        folders = []
        try:
            for item in self.save_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    folders.append(item.name)
            folders.sort()
        except Exception as e:
            print(f"Error reading folders: {e}")
        return folders

    def refresh_folder_bar(self):
        """Rebuild the folder buttons"""
        # Clear existing buttons and drop targets
        for widget in self.folder_buttons_frame.winfo_children():
            widget.destroy()
        self.folder_drop_targets = {}

        # Button style for folder tabs
        btn_style = {
            'font': ('Segoe UI', 9),
            'cursor': 'hand2',
            'relief': tk.FLAT,
            'bd': 1,
            'padx': 12,
            'pady': 4,
        }

        # "All" button (also a drop target for root)
        all_btn = tk.Button(
            self.folder_buttons_frame,
            text="All",
            bg='#e0e0e0' if self.current_folder is None else '#f5f5f5',
            fg='#333',
            activebackground='#d0d0d0',
            command=lambda: self.select_folder(None),
            **btn_style
        )
        all_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.folder_drop_targets[None] = all_btn  # None = root folder

        # Folder buttons
        for folder in self.get_folders():
            is_selected = self.current_folder == folder
            btn = tk.Button(
                self.folder_buttons_frame,
                text=folder,
                bg='#4a90d9' if is_selected else '#f5f5f5',
                fg='white' if is_selected else '#333',
                activebackground='#3a80c9' if is_selected else '#d0d0d0',
                command=lambda f=folder: self.select_folder(f),
                **btn_style
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.folder_drop_targets[folder] = btn

            # Right-click context menu for folder management
            btn.bind("<Button-3>", lambda e, f=folder: self.show_folder_menu(e, f))

    def select_folder(self, folder_name):
        """Select a folder to filter gallery"""
        self.current_folder = folder_name
        self.refresh_folder_bar()
        self.refresh_gallery()
        if folder_name:
            self.status_var.set(f"Showing: {folder_name}")
        else:
            self.status_var.set("Showing: All screenshots")

    def create_new_folder(self):
        """Create a new folder"""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Folder")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        # Center on parent
        dialog.geometry("300x120")
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 120) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Folder name:").pack(anchor=tk.W)
        name_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=name_var, width=30)
        entry.pack(fill=tk.X, pady=(5, 15))
        entry.focus()

        def create():
            name = name_var.get().strip()
            if not name:
                return
            # Sanitize folder name
            name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not name:
                messagebox.showerror("Error", "Invalid folder name")
                return
            folder_path = self.save_dir / name
            try:
                folder_path.mkdir(exist_ok=True)
                dialog.destroy()
                self.refresh_folder_bar()
                self.select_folder(name)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create folder: {e}")

        entry.bind("<Return>", lambda e: create())
        ttk.Button(frame, text="Create", command=create).pack()

    def show_folder_menu(self, event, folder_name):
        """Show context menu for folder management"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Rename...", command=lambda: self.rename_folder(folder_name))
        menu.add_command(label="Delete...", command=lambda: self.delete_folder(folder_name))
        menu.post(event.x_root, event.y_root)

    def rename_folder(self, old_name):
        """Rename a folder"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Folder")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        dialog.geometry("300x120")
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 120) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="New name:").pack(anchor=tk.W)
        name_var = tk.StringVar(value=old_name)
        entry = ttk.Entry(frame, textvariable=name_var, width=30)
        entry.pack(fill=tk.X, pady=(5, 15))
        entry.focus()
        entry.select_range(0, tk.END)

        def do_rename():
            new_name = name_var.get().strip()
            if not new_name or new_name == old_name:
                dialog.destroy()
                return
            # Sanitize folder name
            new_name = "".join(c for c in new_name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not new_name:
                messagebox.showerror("Error", "Invalid folder name")
                return

            old_path = self.save_dir / old_name
            new_path = self.save_dir / new_name

            if new_path.exists():
                messagebox.showerror("Error", f"Folder '{new_name}' already exists")
                return

            try:
                old_path.rename(new_path)
                dialog.destroy()
                # Update current folder if we renamed the active one
                if self.current_folder == old_name:
                    self.current_folder = new_name
                self.refresh_folder_bar()
                self.refresh_gallery()
                self.status_var.set(f"Renamed: {old_name} → {new_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not rename folder: {e}")

        entry.bind("<Return>", lambda e: do_rename())
        ttk.Button(frame, text="Rename", command=do_rename).pack()

    def delete_folder(self, folder_name):
        """Delete a folder (must be empty or move contents to root)"""
        folder_path = self.save_dir / folder_name
        images = list(folder_path.glob("*.png"))

        if images:
            result = messagebox.askyesnocancel(
                "Delete Folder",
                f"Folder '{folder_name}' contains {len(images)} image(s).\n\n"
                "Yes = Move images to root and delete folder\n"
                "No = Cancel"
            )
            if result is None or result is False:
                return
            # Move images to root
            import shutil
            for img in images:
                dest = self.save_dir / img.name
                if dest.exists():
                    # Add suffix if file exists
                    base = img.stem
                    dest = self.save_dir / f"{base}_moved{img.suffix}"
                shutil.move(str(img), str(dest))

        try:
            folder_path.rmdir()
            # Switch to All if we deleted the current folder
            if self.current_folder == folder_name:
                self.current_folder = None
            self.refresh_folder_bar()
            self.refresh_gallery()
            self.status_var.set(f"Deleted folder: {folder_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete folder: {e}")

    def move_to_folder(self, filepath, folder_name):
        """Move an image to a folder"""
        import shutil
        try:
            if folder_name:
                dest_dir = self.save_dir / folder_name
                dest_dir.mkdir(exist_ok=True)
            else:
                dest_dir = self.save_dir
            dest_path = dest_dir / filepath.name
            if dest_path.exists() and dest_path != filepath:
                if not messagebox.askyesno("File Exists", f"'{filepath.name}' already exists in {folder_name or 'root'}. Overwrite?"):
                    return
            shutil.move(str(filepath), str(dest_path))
            self.refresh_gallery()
            self.status_var.set(f"Moved to {folder_name or 'root'}: {filepath.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not move file: {e}")

    def show_move_menu(self, event, filepath):
        """Show popup menu for moving image to folder"""
        menu = tk.Menu(self.root, tearoff=0)

        # Get current folder of this file
        current_folder = None
        if filepath.parent != self.save_dir:
            current_folder = filepath.parent.name

        # Add "Root" option if not already in root
        if current_folder is not None:
            menu.add_command(label="Root (main folder)", command=lambda: self.move_to_folder(filepath, None))
            menu.add_separator()

        # Add folder options
        for folder in self.get_folders():
            if folder != current_folder:
                menu.add_command(label=folder, command=lambda f=folder: self.move_to_folder(filepath, f))

        menu.post(event.x_root, event.y_root)

    # ==================== DRAG AND DROP ====================

    def start_drag(self, event, filepath, photo):
        """Start dragging a thumbnail"""
        try:
            self.drag_data["filepath"] = filepath
            self.drag_data["start_x"] = event.x_root
            self.drag_data["start_y"] = event.y_root

            # Create floating drag label
            if self.drag_label:
                try:
                    self.drag_label.destroy()
                except:
                    pass

            self.drag_label = tk.Toplevel(self.root)
            self.drag_label.overrideredirect(True)  # No window decorations
            self.drag_label.attributes('-alpha', 0.7)  # Semi-transparent
            self.drag_label.attributes('-topmost', True)

            # Show mini version of the image
            label = tk.Label(self.drag_label, image=photo, bg='white', relief=tk.RAISED, bd=2)
            label.pack()
            label.image = photo  # Keep reference

            self.drag_label.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        except Exception as e:
            print(f"Error in start_drag: {e}")
            self.drag_label = None

    def do_drag(self, event):
        """Handle drag motion"""
        try:
            if self.drag_data["filepath"] and self.drag_label:
                # Move the floating label
                self.drag_label.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

                # Check if hovering over a drop target
                for folder_name, btn in self.folder_drop_targets.items():
                    try:
                        bx = btn.winfo_rootx()
                        by = btn.winfo_rooty()
                        bw = btn.winfo_width()
                        bh = btn.winfo_height()

                        if bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh:
                            # Highlight this button
                            btn.configure(bg='#4CAF50', fg='white')
                        else:
                            # Reset to normal (check if it's the selected folder)
                            is_selected = self.current_folder == folder_name
                            if folder_name is None:
                                btn.configure(bg='#e0e0e0' if self.current_folder is None else '#f5f5f5', fg='#333')
                            else:
                                btn.configure(
                                    bg='#4a90d9' if is_selected else '#f5f5f5',
                                    fg='white' if is_selected else '#333'
                                )
                    except:
                        pass
        except Exception as e:
            print(f"Error in do_drag: {e}")

    def end_drag(self, event):
        """End drag and check for drop target"""
        if not self.drag_data["filepath"]:
            return

        filepath = self.drag_data["filepath"]
        dropped = False

        # Check if dropped on a folder button
        for folder_name, btn in self.folder_drop_targets.items():
            try:
                bx = btn.winfo_rootx()
                by = btn.winfo_rooty()
                bw = btn.winfo_width()
                bh = btn.winfo_height()

                if bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh:
                    # Get current folder of this file
                    current_folder = None
                    if filepath.parent != self.save_dir:
                        current_folder = filepath.parent.name

                    # Only move if different folder
                    if folder_name != current_folder:
                        self.move_to_folder(filepath, folder_name)
                    dropped = True
                    break
            except:
                pass

        # Clean up
        try:
            if self.drag_label:
                self.drag_label.destroy()
                self.drag_label = None
        except:
            self.drag_label = None
        self.drag_data["filepath"] = None

        # Reset button colors
        try:
            self.refresh_folder_bar()
        except:
            pass

    # ==================== END FOLDER MANAGEMENT ====================

    def refresh_gallery(self):
        try:
            # Update disk usage display
            self.update_disk_usage()

            # Clear existing thumbnails
            for widget in self.gallery_frame.winfo_children():
                try:
                    widget.destroy()
                except:
                    pass
        except Exception as e:
            print(f"Error in refresh_gallery start: {e}")
            return

        # Get list of screenshots based on current folder filter
        try:
            if self.current_folder:
                # Show only images in selected folder
                search_dir = self.save_dir / self.current_folder
                screenshots = sorted(
                    search_dir.glob("*.png"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )[:30]
            else:
                # Show all images (root + subfolders)
                all_images = list(self.save_dir.glob("*.png"))
                # Also include images from subfolders
                for folder in self.get_folders():
                    all_images.extend((self.save_dir / folder).glob("*.png"))
                screenshots = sorted(
                    all_images,
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )[:30]
        except Exception as e:
            print(f"Error reading screenshots: {e}")
            screenshots = []

        if not screenshots:
            no_images_label = ttk.Label(
                self.gallery_frame,
                text="No screenshots yet. Press Ctrl+Shift+R to capture a region!"
            )
            no_images_label.pack(pady=20)
            return

        # Store references to prevent garbage collection
        self.thumbnail_images = []

        # Calculate thumbnails per row based on size
        thumb_width = self.get_thumbnail_size()[0]
        gallery_width = 560  # Approximate usable width
        thumbs_per_row = max(1, gallery_width // (thumb_width + 15))

        # Create thumbnail grid
        row_frame = None
        for i, screenshot_path in enumerate(screenshots):
            if i % thumbs_per_row == 0:
                row_frame = tk.Frame(self.gallery_frame, bg='#f5f5f5')
                row_frame.pack(fill=tk.X, pady=5)

            try:
                # Create thumbnail container
                thumb_frame = tk.Frame(row_frame, bg='white')
                thumb_frame.pack(side=tk.LEFT, padx=5)

                # Load and resize image based on thumbnail scale
                img = Image.open(screenshot_path)
                thumb_size = self.get_thumbnail_size()
                img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.thumbnail_images.append(photo)

                # Create container for image and overlay
                img_container = tk.Frame(thumb_frame, bg='white')
                img_container.pack()

                # Create clickable thumbnail with drag support
                thumb_label = tk.Label(img_container, image=photo, cursor="hand2", bg='white')
                thumb_label.pack()

                # Drag and drop bindings
                def make_drag_handlers(path, img_photo):
                    drag_started = [False]
                    start_pos = [0, 0]

                    def on_press(e):
                        start_pos[0] = e.x_root
                        start_pos[1] = e.y_root
                        drag_started[0] = False

                    def on_motion(e):
                        # Start drag if moved more than 5 pixels
                        if not drag_started[0]:
                            dx = abs(e.x_root - start_pos[0])
                            dy = abs(e.y_root - start_pos[1])
                            if dx > 5 or dy > 5:
                                drag_started[0] = True
                                self.start_drag(e, path, img_photo)
                        else:
                            self.do_drag(e)

                    def on_release(e):
                        if drag_started[0]:
                            self.end_drag(e)
                        else:
                            self.open_image(path)

                    return on_press, on_motion, on_release

                press_h, motion_h, release_h = make_drag_handlers(screenshot_path, photo)
                thumb_label.bind("<Button-1>", press_h)
                thumb_label.bind("<B1-Motion>", motion_h)
                thumb_label.bind("<ButtonRelease-1>", release_h)

                # Create hover menu handlers with floating overlay
                def create_hover_handlers(container, path):
                    overlay_window = None
                    hide_timer = None

                    def show_overlay(e):
                        nonlocal overlay_window, hide_timer

                        # Cancel any pending hide
                        if hide_timer:
                            container.after_cancel(hide_timer)
                            hide_timer = None

                        if overlay_window:
                            return

                        # Create floating toplevel window
                        overlay_window = tk.Toplevel(self.root)
                        overlay_window.overrideredirect(True)
                        overlay_window.attributes('-topmost', True)

                        # Track this window for cleanup
                        self.floating_windows.append(overlay_window)

                        # Menu buttons - simple monochrome style
                        btn_style = {'font': ("Segoe UI", 8), 'cursor': "hand2", 'relief': tk.FLAT,
                                     'fg': '#333', 'pady': 3, 'bd': 0, 'width': 8,
                                     'highlightthickness': 0, 'activeforeground': '#000',
                                     'bg': '#e8e8e8', 'activebackground': '#d0d0d0'}

                        frame = tk.Frame(overlay_window, bg='white', relief=tk.SOLID, bd=1)
                        frame.pack()

                        def close_and_run(func):
                            def wrapper():
                                hide_overlay_now()
                                func()
                            return wrapper

                        tk.Button(frame, text="Open", **btn_style,
                                 command=close_and_run(lambda: self.open_image(path))).pack(pady=1, padx=2)
                        tk.Button(frame, text="Edit", **btn_style,
                                 command=close_and_run(lambda: self.edit_screenshot(path))).pack(pady=1, padx=2)
                        tk.Button(frame, text="Copy", **btn_style,
                                 command=close_and_run(lambda: self.copy_file_to_clipboard(path))).pack(pady=1, padx=2)

                        def show_send_popup(e):
                            menu = tk.Menu(self.root, tearoff=0)
                            for target in self.push_targets:
                                if target.get('enabled', True):
                                    menu.add_command(label=target['name'],
                                                   command=lambda p=path, t=target['name']: self.send_to_target(p, t))
                            menu.post(e.x_root, e.y_root)
                            hide_overlay_now()

                        send_btn = tk.Button(frame, text="Send", **btn_style)
                        send_btn.bind("<Button-1>", show_send_popup)
                        send_btn.pack(pady=1, padx=2)

                        move_btn = tk.Button(frame, text="Move", **btn_style)
                        move_btn.bind("<Button-1>", lambda e: (self.show_move_menu(e, path), hide_overlay_now()))
                        move_btn.pack(pady=1, padx=2)

                        tk.Button(frame, text="Delete", **btn_style,
                                 command=close_and_run(lambda: self.delete_screenshot(path))).pack(pady=1, padx=2)

                        # Position overlay centered over the thumbnail
                        container.update_idletasks()
                        x = container.winfo_rootx() + container.winfo_width() // 2
                        y = container.winfo_rooty() + container.winfo_height() // 2
                        overlay_window.update_idletasks()
                        overlay_window.geometry(f"+{x - overlay_window.winfo_reqwidth()//2}+{y - overlay_window.winfo_reqheight()//2}")

                        # Keep overlay visible when mouse is over it
                        overlay_window.bind("<Enter>", lambda e: cancel_hide())
                        overlay_window.bind("<Leave>", lambda e: schedule_hide())

                    def cancel_hide():
                        nonlocal hide_timer
                        try:
                            if hide_timer:
                                container.after_cancel(hide_timer)
                                hide_timer = None
                        except:
                            pass

                    def schedule_hide():
                        nonlocal hide_timer
                        try:
                            hide_timer = container.after(100, hide_overlay_now)
                        except:
                            pass

                    def hide_overlay_now():
                        nonlocal overlay_window, hide_timer
                        try:
                            if hide_timer:
                                container.after_cancel(hide_timer)
                                hide_timer = None
                        except:
                            pass
                        try:
                            if overlay_window:
                                # Remove from tracking list
                                try:
                                    self.floating_windows.remove(overlay_window)
                                except:
                                    pass
                                overlay_window.destroy()
                                overlay_window = None
                        except:
                            overlay_window = None

                    container.bind("<Enter>", show_overlay)
                    container.bind("<Leave>", lambda e: schedule_hide())

                create_hover_handlers(img_container, screenshot_path)

            except Exception as e:
                print(f"Error loading thumbnail {screenshot_path}: {e}")

    def copy_file_to_clipboard(self, filepath):
        """Copy an existing image file to clipboard"""
        try:
            img = Image.open(filepath)
            self.copy_to_clipboard(img)
            self.status_var.set(f"Copied to clipboard: {filepath.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not copy image: {e}")

    def delete_screenshot(self, filepath):
        """Delete a screenshot file"""
        if messagebox.askyesno("Delete Screenshot", f"Delete {filepath.name}?"):
            try:
                os.remove(filepath)
                self.status_var.set(f"Deleted: {filepath.name}")
                self.refresh_gallery()
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete: {e}")

    def edit_screenshot(self, filepath):
        """Open an existing screenshot in the editor for annotations"""
        try:
            img = Image.open(filepath)
            self.status_var.set("Edit screenshot (add annotations, then Save or Cancel)")
            ScreenshotEditor(img, self.on_editor_complete)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image for editing: {e}")

    def open_image(self, filepath):
        """Open image in default system viewer"""
        try:
            os.startfile(str(filepath))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image: {e}")

    def open_save_folder(self):
        """Open the save folder in file explorer"""
        try:
            os.startfile(str(self.save_dir))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def show_settings(self):
        """Show the settings dialog"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.transient(self.root)
        settings_win.resizable(False, False)

        # Center on parent
        settings_win.geometry("350x700")
        settings_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - settings_win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - settings_win.winfo_height()) // 2
        settings_win.geometry(f"+{x}+{y}")

        # Main container with padding
        frame = ttk.Frame(settings_win, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Exit button reference (will be created at bottom, but need reference for callbacks)
        exit_btn_var = tk.StringVar(value="Exit")

        def mark_saved():
            """Update exit button to show changes were saved"""
            exit_btn_var.set("Exit - changes saved")

        def save_and_mark():
            """Save settings and update button"""
            self.save_push_targets()
            mark_saved()

        # Capture Mode
        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(mode_frame, text="Capture Mode:", width=15).pack(side=tk.LEFT)
        mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.capture_mode_var,
            values=["Region", "Window", "Full Screen"],
            state="readonly",
            width=15
        )
        mode_combo.pack(side=tk.LEFT, padx=(10, 0))
        mode_combo.bind("<<ComboboxSelected>>", lambda e: mark_saved())

        # Capture button for manual capture
        capture_btn = ttk.Button(mode_frame, text="Capture", command=self.do_capture, width=8)
        capture_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Delay
        delay_frame = ttk.Frame(frame)
        delay_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(delay_frame, text="Delay (seconds):", width=15).pack(side=tk.LEFT)
        delay_combo = ttk.Combobox(
            delay_frame,
            textvariable=self.delay_var,
            values=["0", "3", "5", "10"],
            state="readonly",
            width=15
        )
        delay_combo.pack(side=tk.LEFT, padx=(10, 0))
        delay_combo.bind("<<ComboboxSelected>>", lambda e: mark_saved())

        # Edit before save checkbox
        edit_check = ttk.Checkbutton(
            frame,
            text="Edit before save (open editor after capture)",
            variable=self.edit_before_save,
            command=save_and_mark
        )
        edit_check.pack(anchor=tk.W, pady=(0, 5))

        # Pin to all desktops checkbox
        def toggle_pin_and_mark():
            self.toggle_pin()
            mark_saved()

        pin_check = ttk.Checkbutton(
            frame,
            text="Show on all virtual desktops",
            variable=self.pin_to_all_desktops,
            command=toggle_pin_and_mark
        )
        pin_check.pack(anchor=tk.W, pady=(0, 5))

        # Silent capture checkbox - stay on current desktop after capture
        silent_check = ttk.Checkbutton(
            frame,
            text="Silent capture (stay on current desktop)",
            variable=self.silent_capture,
            command=save_and_mark
        )
        silent_check.pack(anchor=tk.W, pady=(0, 10))

        # Auto-send section
        auto_send_frame = ttk.Frame(frame)
        auto_send_frame.pack(fill=tk.X, pady=(0, 15))

        auto_send_check = ttk.Checkbutton(
            auto_send_frame,
            text="Auto-send to:",
            variable=self.auto_send_enabled,
            command=save_and_mark
        )
        auto_send_check.pack(side=tk.LEFT)

        # Get list of enabled target names
        target_names = [t['name'] for t in self.push_targets if t.get('enabled', True)]

        # Set default if not set or invalid
        if self.auto_send_target.get() not in target_names and target_names:
            self.auto_send_target.set(target_names[0])

        def on_target_change(event=None):
            save_and_mark()

        target_combo = ttk.Combobox(
            auto_send_frame,
            textvariable=self.auto_send_target,
            values=target_names,
            state="readonly",
            width=20
        )
        target_combo.pack(side=tk.LEFT, padx=(5, 0))
        target_combo.bind("<<ComboboxSelected>>", on_target_change)  # Save when changed

        # Store reference for refreshing after adding new targets
        self._target_combo = target_combo

        # Thumbnail size slider
        thumb_frame = ttk.Frame(frame)
        thumb_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(thumb_frame, text="Preview Size:", width=15).pack(side=tk.LEFT)

        # Show current size label
        size_label = ttk.Label(thumb_frame, text="", width=10)

        def update_size_label(*args):
            w, h = self.get_thumbnail_size()
            size_label.config(text=f"{w}x{h}")

        thumb_slider = ttk.Scale(
            thumb_frame,
            from_=1,
            to=10,
            variable=self.thumbnail_scale,
            orient=tk.HORIZONTAL,
            length=120,
            command=update_size_label  # Just update label while dragging
        )
        thumb_slider.pack(side=tk.LEFT, padx=(10, 5))
        # Refresh gallery only when slider is released, and mark as saved
        def on_slider_release(e):
            self.refresh_gallery()
            mark_saved()
        thumb_slider.bind("<ButtonRelease-1>", on_slider_release)
        size_label.pack(side=tk.LEFT)
        update_size_label()

        # Storage management section
        storage_frame = ttk.LabelFrame(frame, text="Storage Management", padding="10")
        storage_frame.pack(fill=tk.X, pady=(0, 15))

        # Disk limit
        limit_frame = ttk.Frame(storage_frame)
        limit_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(limit_frame, text="Disk Limit (MB):", width=15).pack(side=tk.LEFT)
        limit_combo = ttk.Combobox(
            limit_frame,
            textvariable=self.disk_limit_mb,
            values=["100", "250", "500", "1000", "2000", "5000"],
            width=10
        )
        limit_combo.pack(side=tk.LEFT, padx=(10, 0))
        def on_limit_change(e):
            self.update_disk_usage(show_warning=False)
            mark_saved()
        limit_combo.bind("<<ComboboxSelected>>", on_limit_change)

        # Archive days
        archive_frame = ttk.Frame(storage_frame)
        archive_frame.pack(fill=tk.X, pady=(5, 5))
        ttk.Label(archive_frame, text="Auto-cleanup age:", width=15).pack(side=tk.LEFT)
        archive_combo = ttk.Combobox(
            archive_frame,
            textvariable=self.archive_days,
            values=["7", "14", "30", "60", "90"],
            width=10
        )
        archive_combo.pack(side=tk.LEFT, padx=(10, 0))
        archive_combo.bind("<<ComboboxSelected>>", lambda e: mark_saved())
        ttk.Label(archive_frame, text="days").pack(side=tk.LEFT, padx=(5, 0))

        # Manual cleanup button
        cleanup_btn = ttk.Button(
            storage_frame,
            text="Clean Up Now",
            command=self.manual_cleanup
        )
        cleanup_btn.pack(pady=(5, 0))

        # Push Targets section
        targets_frame = ttk.LabelFrame(frame, text="Push Targets", padding="10")
        targets_frame.pack(fill=tk.X, pady=(0, 15))

        # List current targets
        targets_list = tk.Listbox(targets_frame, height=3, font=("", 9))
        for target in self.push_targets:
            status = "✓" if target.get('enabled', True) else "✗"
            targets_list.insert(tk.END, f"{status} {target['name']}")
        targets_list.pack(fill=tk.X, pady=(0, 10))

        targets_btn_frame = ttk.Frame(targets_frame)
        targets_btn_frame.pack(fill=tk.X)

        def refresh_targets_list():
            targets_list.delete(0, tk.END)
            for target in self.push_targets:
                status = "✓" if target.get('enabled', True) else "✗"
                targets_list.insert(tk.END, f"{status} {target['name']}")
            # Also update the auto-send dropdown
            new_target_names = [t['name'] for t in self.push_targets if t.get('enabled', True)]
            target_combo['values'] = new_target_names
            if self.auto_send_target.get() not in new_target_names and new_target_names:
                self.auto_send_target.set(new_target_names[0])

        def delete_selected_target():
            sel = targets_list.curselection()
            if sel:
                idx = sel[0]
                name = self.push_targets[idx]['name']
                if messagebox.askyesno("Delete Target", f"Delete '{name}'?"):
                    del self.push_targets[idx]
                    self.save_push_targets()
                    refresh_targets_list()

        ttk.Button(targets_btn_frame, text="Add New", command=lambda: self.register_new_target(refresh_targets_list)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(targets_btn_frame, text="Delete", command=delete_selected_target).pack(side=tk.LEFT)

        # Save location
        loc_frame = ttk.LabelFrame(frame, text="Save Location", padding="10")
        loc_frame.pack(fill=tk.X, pady=(0, 15))

        self.dir_var = tk.StringVar(value=str(self.save_dir))
        dir_label = ttk.Label(loc_frame, textvariable=self.dir_var, wraplength=280)
        dir_label.pack(fill=tk.X, pady=(0, 10))

        btn_frame = ttk.Frame(loc_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Change...", command=self.change_save_dir).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Open Folder", command=self.open_save_folder).pack(side=tk.LEFT)

        # Exit button (text changes when settings are saved)
        exit_btn = ttk.Button(frame, textvariable=exit_btn_var, command=settings_win.destroy, width=20)
        exit_btn.pack(pady=(10, 0))

    def change_save_dir(self):
        """Change the save directory"""
        new_dir = filedialog.askdirectory(
            initialdir=str(self.save_dir),
            title="Select Screenshot Save Location"
        )
        if new_dir:
            self.save_dir = Path(new_dir)
            self.dir_var.set(str(self.save_dir))
            self.refresh_gallery()
            self.status_var.set(f"Save location changed to: {new_dir}")

    def cleanup_floating_windows(self):
        """Cleanup any orphaned floating windows"""
        try:
            # Clean up drag label
            if self.drag_label:
                try:
                    self.drag_label.destroy()
                except:
                    pass
                self.drag_label = None

            # Clean up tracked floating windows
            for window in self.floating_windows[:]:
                try:
                    if window and window.winfo_exists():
                        window.destroy()
                except:
                    pass
                try:
                    self.floating_windows.remove(window)
                except:
                    pass
        except:
            pass

    def schedule_cleanup(self):
        """Schedule periodic cleanup of floating windows"""
        try:
            self.cleanup_floating_windows()
            # Schedule next cleanup in 5 seconds
            self.root.after(5000, self.schedule_cleanup)
        except:
            pass

    def on_close(self):
        """Clean up and close"""
        self.cleanup_floating_windows()
        self.unregister_hotkeys()
        self.root.destroy()

    def run(self):
        """Start the application"""
        print("Screenshot Tool started!")
        print(f"Screenshots will be saved to: {self.save_dir}")
        print(f"Hotkeys:")
        print(f"  {self.hotkey_region} - Capture region")
        print(f"  {self.hotkey_full} - Capture full screen")
        print(f"\nTip: Enable 'Auto-send' in Settings to automatically send screenshots to your preferred app!")

        # Auto-open settings on startup so user can see current config
        self.root.after(100, self.show_settings)

        try:
            self.root.mainloop()
        except Exception as e:
            # Log runtime crashes
            error_msg = f"RUNTIME CRASH: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            print(f"\n{'='*60}")
            print("RUNTIME ERROR - Error logged to:")
            print(f"{self.save_dir / 'screenshot_tool_crash.log'}")
            print(f"{'='*60}")
            print(error_msg)
            raise


if __name__ == "__main__":
    try:
        app = ScreenshotTool()
        app.run()
    except Exception as e:
        # Log the crash
        error_msg = f"CRASH: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        print(f"\n{'='*60}")
        print("APPLICATION CRASHED - Error logged to:")
        print(f"{log_dir / 'screenshot_tool_crash.log'}")
        print(f"{'='*60}")
        print(error_msg)
        input("\nPress Enter to exit...")
        sys.exit(1)
