"""
Otterly Screenshots - PyQt6 Version
A modern Windows screenshot utility with Solarized Light theme

Features:
- Global hotkeys (Ctrl+Shift+S/R/W) for screen, region, window capture
- Gallery with folder organization and drag-drop
- Screenshot editor with highlight, circle, and text tools
- Toast notifications and auto-send to apps
"""

import sys
import os
import json
import shutil
import logging
import traceback
import sqlite3
import subprocess
import threading
import time
import hashlib
from collections import OrderedDict, deque
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from io import BytesIO
import ctypes
import struct


def _show_startup_error(message: str) -> None:
    """Show a native Windows error dialog before startup exits."""
    print(message)
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "Otterly Screenshots Startup Error", 0x10)
    except Exception:
        pass

def _install_python_package(package_name: str) -> bool:
    """Install a required package with explicit success/failure handling."""
    print(f"Installing {package_name}...")
    try:
        install_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name, "--quiet"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        _show_startup_error(
            f"Timed out while installing required dependency '{package_name}'.\n"
            f"Python: {sys.executable}"
        )
        return False

    if install_result.returncode != 0:
        stderr_line = (install_result.stderr or "").strip().splitlines()
        detail = stderr_line[-1] if stderr_line else "Unknown pip error"
        _show_startup_error(
            f"Failed to install required dependency '{package_name}'.\n"
            f"Python: {sys.executable}\n"
            f"pip exit code: {install_result.returncode}\n"
            f"Details: {detail}"
        )
        return False

    return True


def _prefer_system_cpp_runtime():
    """Load Windows' own C++ runtime before Qt does.

    PyQt6 ships msvcp140.dll 14.26 (2020). The offline speech engine (ctranslate2, voice
    notes) is built against a newer one and crashes with an access violation when the old
    copy is already loaded. Windows reuses a DLL that is already loaded by name, so loading
    System32's newer copy first makes Qt and the speech engine share it. Qt runs fine on
    the newer runtime; this costs a few milliseconds."""
    if sys.platform != 'win32':
        return
    sysdir = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    for name in ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
        path = os.path.join(sysdir, name)
        if os.path.exists(path):
            try:
                ctypes.WinDLL(path)
            except OSError:
                pass


_prefer_system_cpp_runtime()

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
        QSlider, QComboBox, QCheckBox, QDialog, QLineEdit,
        QMessageBox, QFileDialog, QMenu, QGridLayout, QSizePolicy,
        QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
        QInputDialog, QToolBar, QSpinBox, QListWidget, QListWidgetItem,
        QToolButton, QDialogButtonBox, QWidgetAction, QSizeGrip
    )
    from PyQt6.QtCore import (
        Qt, QPoint, QTimer, QSize, QRect, QRectF, QThread, pyqtSignal,
        QMimeData, QUrl, QPropertyAnimation, QEasingCurve, QObject
    )
    from PyQt6.QtGui import (
        QFont, QMouseEvent, QPixmap, QImage, QPainter, QPen, QBrush,
        QColor, QCursor, QDrag, QIcon, QPainterPath, QFontMetrics,
        QWheelEvent, QKeyEvent, QPolygon, QLinearGradient
    )
except ImportError:
    if not _install_python_package("PyQt6"):
        raise SystemExit(1)
    try:
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QFrame, QSplitter, QScrollArea,
            QSlider, QComboBox, QCheckBox, QDialog, QLineEdit,
            QMessageBox, QFileDialog, QMenu, QGridLayout, QSizePolicy,
            QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
            QInputDialog, QToolBar, QSpinBox, QListWidget, QListWidgetItem,
            QToolButton, QDialogButtonBox, QWidgetAction, QSizeGrip
        )
        from PyQt6.QtCore import (
            Qt, QPoint, QTimer, QSize, QRect, QRectF, QThread, pyqtSignal,
            QMimeData, QUrl, QPropertyAnimation, QEasingCurve
        )
        from PyQt6.QtGui import (
            QFont, QMouseEvent, QPixmap, QImage, QPainter, QPen, QBrush,
            QColor, QCursor, QDrag, QIcon, QPainterPath, QFontMetrics,
            QWheelEvent, QKeyEvent, QPolygon, QLinearGradient
        )
    except ImportError as import_error:
        _show_startup_error(
            "PyQt6 import still failed after installation attempt.\n"
            f"Python: {sys.executable}\n"
            f"Details: {import_error}"
        )
        raise SystemExit(1)

# External dependencies
try:
    from PIL import Image, ImageGrab
except ImportError:
    if not _install_python_package("Pillow"):
        raise SystemExit(1)
    from PIL import Image, ImageGrab

try:
    import keyboard
except ImportError:
    if not _install_python_package("keyboard"):
        raise SystemExit(1)
    import keyboard

try:
    import mss
except ImportError:
    if not _install_python_package("mss"):
        raise SystemExit(1)
    import mss

# Win32 imports for window management and clipboard
try:
    import win32gui
    import win32con
    import win32clipboard
    import win32ui
except ImportError:
    if not _install_python_package("pywin32"):
        raise SystemExit(1)
    import win32gui
    import win32con
    import win32clipboard
    import win32ui

# Optional: Virtual desktop support
try:
    from pyvda import AppView, VirtualDesktop
    PYVDA_AVAILABLE = True
except ImportError:
    PYVDA_AVAILABLE = False

# ============================================================================
# CONSTANTS & THEME
# ============================================================================

APP_NAME = "Otterly Screenshots"
APP_VERSION = "2.0"


def get_display_scale() -> float:
    """Get the actual display scale factor by comparing physical (mss) to Qt logical screen size.
    PyQt6 sets Per-Monitor DPI Aware V2, so GetSystemMetrics returns physical pixels (same as mss).
    Qt's screen.geometry() returns logical pixels, giving us the true scale factor."""
    try:
        with mss.mss() as sct:
            physical_w = sct.monitors[1]['width']  # Physical pixels from mss
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                logical_w = screen.geometry().width()  # Qt logical pixels
                if logical_w > 0:
                    scale = physical_w / logical_w
                    if scale >= 1.0:
                        return scale
    except Exception:
        pass
    # Fallback: try Windows DPI API
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        return dpi / 96.0
    except Exception:
        pass
    return 1.0

# Theme Presets
THEMES = {
    'solarized_dark': {
        'name': 'Solarized Dark',
        'BG_LIGHT': '#FDF6E3',
        'BG_CONTENT': '#EEE8D5',
        'BG_DARK': '#073642',
        'BG_DARKER': '#002B36',
        'BG_SIDEBAR': '#073642',
        'BG_GALLERY': '#073642',
        'BG_TITLEBAR': '#073642',
        'TEXT_DARK': '#073642',
        'TEXT_MUTED': '#93A1A1',
        'TEXT_LIGHT': '#FDF6E3',
        'TEXT_GRAY': '#657B83',
        'TEXT_TITLEBAR': '#FDF6E3',
        'TEXT_SIDEBAR': '#93A1A1',
        'TEXT_GALLERY': '#FDF6E3',
        'ACCENT': '#268BD2',
        'SUCCESS': '#859900',
        'WARNING': '#CB4B16',
        'ERROR': '#DC322F',
        'BORDER': '#002B36',
        'BUTTON_BG': '#586E75',
        'BUTTON_TEXT': '#FDF6E3',
        'BUTTON_HOVER': '#657B83',
    },
    'warm_contrast': {
        'name': 'Warm Contrast',
        'BG_LIGHT': '#FDF6E3',
        'BG_CONTENT': '#EEE8D5',
        'BG_DARK': '#073642',
        'BG_DARKER': '#002B36',
        'BG_SIDEBAR': '#FDF6E3',
        'BG_GALLERY': '#073642',
        'BG_TITLEBAR': '#FDF6E3',
        'TEXT_DARK': '#073642',
        'TEXT_MUTED': '#657B83',
        'TEXT_LIGHT': '#FDF6E3',
        'TEXT_GRAY': '#657B83',
        'TEXT_TITLEBAR': '#073642',
        'TEXT_SIDEBAR': '#073642',
        'TEXT_GALLERY': '#FDF6E3',
        'ACCENT': '#D79921',
        'SUCCESS': '#859900',
        'WARNING': '#CB4B16',
        'ERROR': '#DC322F',
        'BORDER': '#D3CBB7',
        'BUTTON_BG': '#D79921',
        'BUTTON_TEXT': '#ffffff',
        'BUTTON_HOVER': '#B58900',
    },
    'charcoal': {
        'name': 'Charcoal',
        'BG_LIGHT': '#3d3d3d',
        'BG_CONTENT': '#2d2d2d',
        'BG_DARK': '#1a1a1a',
        'BG_DARKER': '#111111',
        'BG_SIDEBAR': '#1a1a1a',
        'BG_GALLERY': '#1a1a1a',
        'BG_TITLEBAR': '#1a1a1a',
        'TEXT_DARK': '#e0e0e0',
        'TEXT_MUTED': '#888888',
        'TEXT_LIGHT': '#e0e0e0',
        'TEXT_GRAY': '#aaaaaa',
        'TEXT_TITLEBAR': '#e0e0e0',
        'TEXT_SIDEBAR': '#e0e0e0',
        'TEXT_GALLERY': '#e0e0e0',
        'ACCENT': '#6B9FCE',
        'SUCCESS': '#7CB342',
        'WARNING': '#FFA726',
        'ERROR': '#EF5350',
        'BORDER': '#333333',
        'BUTTON_BG': '#2d2d2d',
        'BUTTON_TEXT': '#e0e0e0',
        'BUTTON_HOVER': '#3d3d3d',
    },
    'midnight': {
        'name': 'Midnight Blue',
        'BG_LIGHT': '#2c3e50',
        'BG_CONTENT': '#243342',
        'BG_DARK': '#1a252f',
        'BG_DARKER': '#151d25',
        'BG_SIDEBAR': '#1a252f',
        'BG_GALLERY': '#1a252f',
        'BG_TITLEBAR': '#1a252f',
        'TEXT_DARK': '#ecf0f1',
        'TEXT_MUTED': '#7f8c8d',
        'TEXT_LIGHT': '#ecf0f1',
        'TEXT_GRAY': '#95a5a6',
        'TEXT_TITLEBAR': '#ecf0f1',
        'TEXT_SIDEBAR': '#ecf0f1',
        'TEXT_GALLERY': '#ecf0f1',
        'ACCENT': '#3498db',
        'SUCCESS': '#2ecc71',
        'WARNING': '#f39c12',
        'ERROR': '#e74c3c',
        'BORDER': '#243342',
        'BUTTON_BG': '#2c3e50',
        'BUTTON_TEXT': '#ecf0f1',
        'BUTTON_HOVER': '#34495e',
    },
    'light': {
        'name': 'Light',
        'BG_LIGHT': '#ffffff',
        'BG_CONTENT': '#f5f5f5',
        'BG_DARK': '#e8e8e8',
        'BG_DARKER': '#d0d0d0',
        'BG_SIDEBAR': '#f0f0f0',
        'BG_GALLERY': '#ffffff',
        'BG_TITLEBAR': '#f0f0f0',
        'TEXT_DARK': '#333333',
        'TEXT_MUTED': '#666666',
        'TEXT_LIGHT': '#ffffff',
        'TEXT_GRAY': '#888888',
        'TEXT_TITLEBAR': '#333333',
        'TEXT_SIDEBAR': '#333333',
        'TEXT_GALLERY': '#333333',
        'ACCENT': '#2196F3',
        'SUCCESS': '#4CAF50',
        'WARNING': '#FF9800',
        'ERROR': '#f44336',
        'BORDER': '#dddddd',
        'BUTTON_BG': '#2196F3',
        'BUTTON_TEXT': '#ffffff',
        'BUTTON_HOVER': '#1976D2',
    },
}

# Active theme storage
_active_theme = 'solarized_dark'

def get_theme_names() -> list:
    """Get list of available theme names"""
    return [(k, v['name']) for k, v in THEMES.items()]

def set_active_theme(theme_key: str):
    """Set the active theme"""
    global _active_theme
    if theme_key in THEMES:
        _active_theme = theme_key

def get_active_theme() -> str:
    """Get the active theme key"""
    return _active_theme


class Theme:
    """Dynamic theme class that reads from active theme preset"""

    @staticmethod
    def _get(key: str) -> str:
        return THEMES[_active_theme].get(key, '#FF00FF')  # Magenta for missing

    @property
    def BG_LIGHT(self): return self._get('BG_LIGHT')
    @property
    def BG_CONTENT(self): return self._get('BG_CONTENT')
    @property
    def BG_DARK(self): return self._get('BG_DARK')
    @property
    def BG_DARKER(self): return self._get('BG_DARKER')
    @property
    def BG_SIDEBAR(self): return self._get('BG_SIDEBAR')
    @property
    def BG_GALLERY(self): return self._get('BG_GALLERY')
    @property
    def BG_TITLEBAR(self): return self._get('BG_TITLEBAR')
    @property
    def TEXT_DARK(self): return self._get('TEXT_DARK')
    @property
    def TEXT_MUTED(self): return self._get('TEXT_MUTED')
    @property
    def TEXT_LIGHT(self): return self._get('TEXT_LIGHT')
    @property
    def TEXT_GRAY(self): return self._get('TEXT_GRAY')
    @property
    def TEXT_TITLEBAR(self): return self._get('TEXT_TITLEBAR')
    @property
    def TEXT_SIDEBAR(self): return self._get('TEXT_SIDEBAR')
    @property
    def TEXT_GALLERY(self): return self._get('TEXT_GALLERY')
    @property
    def ACCENT(self): return self._get('ACCENT')
    @property
    def SUCCESS(self): return self._get('SUCCESS')
    @property
    def WARNING(self): return self._get('WARNING')
    @property
    def ERROR(self): return self._get('ERROR')
    @property
    def BORDER(self): return self._get('BORDER')
    @property
    def BUTTON_BG(self): return self._get('BUTTON_BG')
    @property
    def BUTTON_TEXT(self): return self._get('BUTTON_TEXT')
    @property
    def BUTTON_HOVER(self): return self._get('BUTTON_HOVER')

    # Highlight colors (same for all themes)
    HIGHLIGHT_YELLOW = (255, 255, 0, 100)
    HIGHLIGHT_GREEN = (0, 255, 0, 100)
    HIGHLIGHT_BLUE = (0, 150, 255, 100)
    HIGHLIGHT_RED = (255, 0, 0, 100)

# Create theme instance
Theme = Theme()


# Paths
SAVE_DIR = Path.home() / "Pictures" / "Screenshots"
CONFIG_FILE = SAVE_DIR / "screenshot_tool_config.json"
OCR_DB_PATH = SAVE_DIR / "ocr_index.db"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
STARTUP_TRACE_PATH = SAVE_DIR / "startup_trace.log"
# Small copies of every screenshot, so the gallery never has to decode full-size files twice.
# Kept outside the save folder so OCR re-index, storage totals and folder lists never see them.
THUMB_CACHE_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "OtterlyScreenshots" / "thumbs"
THUMB_MASTER_W, THUMB_MASTER_H = 640, 480


def _trace_startup(message: str) -> None:
    """Append startup diagnostics to a plain text trace file."""
    try:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STARTUP_TRACE_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {message}\n")
    except Exception:
        pass

# OCR setup
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    OCR_AVAILABLE = Path(TESSERACT_CMD).exists()
except ImportError:
    OCR_AVAILABLE = False

# Set up logging
SAVE_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=SAVE_DIR / "screenshot_tool_crash.log",
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ============================================================================
# OCR INDEX
# ============================================================================

class OcrIndex:
    """SQLite-backed full-text index for screenshot OCR content."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(str(self.db_path), timeout=10)

    def _init_db(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS ocr (
                    filepath TEXT PRIMARY KEY,
                    text     TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_filepath ON ocr(filepath)")

    def index_file(self, filepath: Path, text: str):
        with self._connect() as con:
            con.execute("""
                INSERT INTO ocr (filepath, text, indexed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET text=excluded.text, indexed_at=excluded.indexed_at
            """, (str(filepath), text, datetime.now().isoformat()))

    def is_indexed(self, filepath: Path) -> bool:
        with self._connect() as con:
            row = con.execute("SELECT 1 FROM ocr WHERE filepath=?", (str(filepath),)).fetchone()
            return row is not None

    def get_indexed_filepaths(self, filepaths: List[Path]) -> set:
        """Return a set of filepaths (as strings) that already exist in the OCR index."""
        if not filepaths:
            return set()

        path_strings = [str(p) for p in filepaths]
        indexed = set()

        # SQLite has a practical parameter limit, so query in chunks.
        chunk_size = 500
        with self._connect() as con:
            for i in range(0, len(path_strings), chunk_size):
                chunk = path_strings[i:i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                sql = f"SELECT filepath FROM ocr WHERE filepath IN ({placeholders})"
                rows = con.execute(sql, chunk).fetchall()
                indexed.update(r[0] for r in rows)

        return indexed

    def search(self, query: str) -> List[Path]:
        """Return list of Paths whose OCR text contains all query words."""
        words = [w.strip().lower() for w in query.split() if w.strip()]
        if not words:
            return []
        with self._connect() as con:
            sql = "SELECT filepath FROM ocr WHERE " + " AND ".join(
                ["lower(text) LIKE ?"] * len(words))
            params = [f"%{w}%" for w in words]
            rows = con.execute(sql, params).fetchall()
        return [Path(r[0]) for r in rows]

    def get_text(self, filepath: Path) -> str | None:
        """Return OCR text for a file, or None if not indexed."""
        with self._connect() as con:
            row = con.execute("SELECT text FROM ocr WHERE filepath=?", (str(filepath),)).fetchone()
            return row[0] if row else None

    def remove_file(self, filepath: Path):
        with self._connect() as con:
            con.execute("DELETE FROM ocr WHERE filepath=?", (str(filepath),))

    def count(self) -> int:
        with self._connect() as con:
            return con.execute("SELECT COUNT(*) FROM ocr").fetchone()[0]


class OcrWorker(QThread):
    """Background thread: runs Tesseract on one image and stores result in OcrIndex."""
    finished = pyqtSignal(str, str)   # filepath, extracted_text

    def __init__(self, filepath: Path, index: OcrIndex):
        super().__init__()
        self.filepath = filepath
        self.index = index

    def run(self):
        if not OCR_AVAILABLE:
            return
        try:
            img = Image.open(str(self.filepath))
            text = pytesseract.image_to_string(img, lang='eng')
            self.index.index_file(self.filepath, text)
            self.finished.emit(str(self.filepath), text)
        except Exception as e:
            logging.error(f"OCR failed for {self.filepath}: {e}")


class ReindexWorker(QThread):
    """Background thread: OCR all unindexed images in a directory tree."""
    progress = pyqtSignal(int, int)   # done, total
    finished = pyqtSignal(int)        # total indexed

    def __init__(self, save_dir: Path, index: OcrIndex):
        super().__init__()
        self.save_dir = save_dir
        self.index = index

    def run(self):
        if not OCR_AVAILABLE:
            self.finished.emit(0)
            return
        images = list(self.save_dir.rglob("*.png"))
        total = len(images)
        done = 0
        for img_path in images:
            if not self.index.is_indexed(img_path):
                try:
                    img = Image.open(str(img_path))
                    text = pytesseract.image_to_string(img, lang='eng')
                    self.index.index_file(img_path, text)
                except Exception as e:
                    logging.error(f"Reindex OCR failed for {img_path}: {e}")
            done += 1
            self.progress.emit(done, total)
        self.finished.emit(done)


# ============================================================================
# THUMBNAILS (disk cache + background loader)
# ============================================================================

def _thumb_cache_base(filepath: Path) -> Optional[Path]:
    """Cache file stem for one screenshot; changes whenever the file is edited or moved."""
    try:
        st = filepath.stat()
    except OSError:
        return None
    digest = hashlib.sha1(f"{filepath}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8")).hexdigest()
    return THUMB_CACHE_DIR / digest[:2] / digest


def load_thumbnail_master(filepath: Path) -> QImage:
    """A copy of the screenshot no larger than THUMB_MASTER_W x THUMB_MASTER_H.

    Read from the disk cache when it exists, otherwise made once from the full file and
    written to the cache. QImage only, so it is safe to call from a worker thread.
    """
    base = _thumb_cache_base(filepath)
    if base is not None:
        for ext in (".jpg", ".png"):
            cached = base.with_suffix(ext)
            if cached.exists():
                img = QImage(str(cached))
                if not img.isNull():
                    return img

    img = QImage(str(filepath))
    if img.isNull():
        return QImage()
    if img.width() > THUMB_MASTER_W or img.height() > THUMB_MASTER_H:
        img = img.scaled(THUMB_MASTER_W, THUMB_MASTER_H,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

    if base is not None:
        try:
            base.parent.mkdir(parents=True, exist_ok=True)
            # Screenshots have no transparency, so JPEG keeps the cache small; imports with alpha stay PNG.
            ext, fmt, quality = (".png", "PNG", -1) if img.hasAlphaChannel() else (".jpg", "JPG", 92)
            tmp = base.parent / f"{base.name}.{threading.get_ident()}.tmp"
            if img.save(str(tmp), fmt, quality):
                os.replace(str(tmp), str(base.with_suffix(ext)))
        except Exception as e:
            logging.error(f"Thumbnail cache write failed for {filepath}: {e}")
    return img


def master_was_downscaled(img: QImage) -> bool:
    """True when the cached master is smaller than the original screenshot."""
    return img.width() >= THUMB_MASTER_W or img.height() >= THUMB_MASTER_H


def grab_to_pixmap(sct, monitor) -> QPixmap:
    """mss grab straight into a QPixmap (BGRA bytes are Qt's RGB32 layout; no PIL round trip)."""
    shot = sct.grab(monitor)
    image = QImage(shot.bgra, shot.width, shot.height, shot.width * 4, QImage.Format.Format_RGB32)
    return QPixmap.fromImage(image.copy())  # copy: the mss buffer is freed when the grab goes away


class ThumbnailLoader(QThread):
    """Makes gallery thumbnails in the background so the window never waits on disk.

    request() replaces the queue with the newest list (in gallery order, so the
    thumbnails at the top of the window arrive first).
    """
    loaded = pyqtSignal(str, str, QImage)   # filepath, gallery cache key, master image (null = unreadable)

    def __init__(self):
        super().__init__()
        self._cond = threading.Condition()
        self._pending = deque()
        self._stopping = False

    def request(self, items: List[Tuple[str, str]]):
        with self._cond:
            self._pending = deque(items)
            self._cond.notify()

    def extend(self, items: List[Tuple[str, str]]):
        with self._cond:
            self._pending.extend(items)
            self._cond.notify()

    def stop(self):
        with self._cond:
            self._stopping = True
            self._pending.clear()
            self._cond.notify()
        self.wait(5000)

    def run(self):
        while True:
            with self._cond:
                while not self._pending and not self._stopping:
                    self._cond.wait()
                if self._stopping:
                    return
                path, key = self._pending.popleft()
            try:
                img = load_thumbnail_master(Path(path))
            except Exception as e:
                logging.error(f"Thumbnail load failed for {path}: {e}")
                img = QImage()
            self.loaded.emit(path, key, img)


# ============================================================================
# STYLESHEETS
# ============================================================================

def generate_stylesheet() -> str:
    """Generate main stylesheet based on active theme"""
    t = THEMES[_active_theme]
    return f"""
QWidget {{
    font-family: 'Segoe UI';
    font-size: 10pt;
}}

QMainWindow {{
    background: {t['BG_GALLERY']};
}}

/* Sidebar */
#sidebar {{
    background: {t['BG_SIDEBAR']};
    border-right: 1px solid {t['BORDER']};
}}

#sidebar QLabel {{
    color: {t['TEXT_SIDEBAR']};
    background: transparent;
}}

#sidebar QPushButton {{
    background: {t['BUTTON_BG']};
    color: {t['BUTTON_TEXT']};
    border: none;
    border-radius: 6px;
    padding: 10px 16px;
    text-align: left;
    font-size: 10pt;
}}

#sidebar QPushButton:hover {{
    background: {t['BUTTON_HOVER']};
}}

#sidebar QPushButton:pressed {{
    background: {t['ACCENT']};
}}

/* Gallery area */
#gallery {{
    background: {t['BG_GALLERY']};
}}

#gallery QScrollArea {{
    background: {t['BG_GALLERY']};
    border: none;
}}

/* Folder bar */
#folderBar {{
    background: {t['BG_GALLERY']};
    border-bottom: 1px solid {t['BORDER']};
}}

/* Title bar */
#titleBar {{
    background: {t['BG_TITLEBAR']};
    border-bottom: 1px solid {t['BORDER']};
}}

/* Status bar */
#statusBar {{
    background: {t['BG_SIDEBAR']};
    color: {t['TEXT_MUTED']};
    padding: 5px 10px;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {t['BG_DARK']};
    width: 14px;
    margin: 0;
    border-radius: 7px;
    border: 1px solid {t['BORDER']};
}}

QScrollBar::handle:vertical {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['BUTTON_HOVER']},
        stop:0.45 {t['TEXT_MUTED']},
        stop:1 {t['BORDER']}
    );
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
    border: 1px solid {t['BG_DARK']};
}}

QScrollBar::handle:vertical:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {t['ACCENT']},
        stop:0.5 {t['BUTTON_HOVER']},
        stop:1 {t['TEXT_MUTED']}
    );
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {t['BG_DARK']};
    height: 14px;
    margin: 0;
    border-radius: 7px;
    border: 1px solid {t['BORDER']};
}}

QScrollBar::handle:horizontal {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {t['BUTTON_HOVER']},
        stop:0.45 {t['TEXT_MUTED']},
        stop:1 {t['BORDER']}
    );
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
    border: 1px solid {t['BG_DARK']};
}}

QScrollBar::handle:horizontal:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {t['ACCENT']},
        stop:0.5 {t['BUTTON_HOVER']},
        stop:1 {t['TEXT_MUTED']}
    );
}}

QSplitter::handle {{
    background: {t['BORDER']};
}}

QSplitter::handle:hover {{
    background: {t['ACCENT']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* Combo box */
QComboBox {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    border-radius: 4px;
    padding: 5px 10px;
    color: {t['TEXT_DARK']};
}}

QComboBox:hover {{
    border-color: {t['ACCENT']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    selection-background-color: {t['ACCENT']};
    selection-color: white;
}}

/* Checkbox */
QCheckBox {{
    color: {t['TEXT_DARK']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 2px solid {t['TEXT_MUTED']};
    background: {t['BG_LIGHT']};
}}

QCheckBox::indicator:checked {{
    background: {t['ACCENT']};
    border-color: {t['ACCENT']};
}}

/* Slider */
QSlider::groove:horizontal {{
    height: 6px;
    background: {t['BORDER']};
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background: {t['ACCENT']};
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {t['SUCCESS']};
}}

/* Line edit */
QLineEdit {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    border-radius: 4px;
    padding: 6px 10px;
    color: {t['TEXT_DARK']};
}}

QLineEdit:focus {{
    border-color: {t['ACCENT']};
}}

/* List widget */
QListWidget {{
    background: {t['BG_LIGHT']};
    border: 1px solid {t['BORDER']};
    border-radius: 4px;
}}

QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {t['BG_CONTENT']};
}}

QListWidget::item:selected {{
    background: {t['ACCENT']};
    color: white;
}}

QListWidget::item:hover {{
    background: {t['BG_CONTENT']};
}}
"""


# ============================================================================
# CUSTOM TITLE BAR
# ============================================================================

# ============================================================================
# FLOATING CAPTURE BAR
# ============================================================================

class FloatingBar(QWidget):
    """
    Slim always-on-top widget pinned to all virtual desktops.
    Shows Region / Window / Screen capture buttons.
    Delegates captures to MainWindow so all save/send/OCR logic is shared.
    """

    def __init__(self, main_window):
        super().__init__(None,
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint)
        self.main_window = main_window
        self._drag_pos = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.92)

        self._build_ui()
        self._restore_position()

        # Pin to all desktops after the widget has a real HWND
        QTimer.singleShot(300, self._pin_to_all_desktops)

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Card frame
        card = QFrame()
        card.setObjectName("floatingCard")
        card.setStyleSheet("""
            #floatingCard {
                background: #002B36;
                border: 1px solid #2AA198;
                border-radius: 10px;
            }
        """)
        outer.addWidget(card)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Drag grip
        grip = QLabel("⠿")
        grip.setStyleSheet("color: #586E75; font-size: 14px; padding: 0 2px;")
        grip.setCursor(Qt.CursorShape.SizeAllCursor)
        layout.addWidget(grip)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #2AA198; margin: 4px 2px;")
        layout.addWidget(sep)

        btn_style = """
            QPushButton {
                background: transparent;
                color: #93A1A1;
                border: none;
                border-radius: 5px;
                font-size: 11px;
                padding: 4px 8px;
                min-width: 30px;
            }
            QPushButton:hover {
                background: #073642;
                color: #2AA198;
            }
            QPushButton:pressed {
                background: #2AA198;
                color: white;
            }
        """

        region_btn = QPushButton("⬚\nRegion")
        region_btn.setStyleSheet(btn_style)
        region_btn.setToolTip("Capture Region  (Ctrl+Shift+R)")
        region_btn.clicked.connect(self._capture_region)
        layout.addWidget(region_btn)

        window_btn = QPushButton("🗗\nWindow")
        window_btn.setStyleSheet(btn_style)
        window_btn.setToolTip("Capture Window  (Ctrl+Shift+W)")
        window_btn.clicked.connect(self._capture_window)
        layout.addWidget(window_btn)

        screen_btn = QPushButton("🖥\nScreen")
        screen_btn.setStyleSheet(btn_style)
        screen_btn.setToolTip("Capture Full Screen  (Ctrl+Shift+S)")
        screen_btn.clicked.connect(self._capture_screen)
        layout.addWidget(screen_btn)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #2AA198; margin: 4px 2px;")
        layout.addWidget(sep2)

        # Show main window button
        show_btn = QPushButton("◎")
        show_btn.setToolTip("Open Otterly Screenshots")
        show_btn.setStyleSheet(btn_style + """
            QPushButton { font-size: 14px; min-width: 20px; padding: 4px 4px; }
        """)
        show_btn.clicked.connect(self._show_main)
        layout.addWidget(show_btn)

        self.setFixedHeight(52)

    # ------------------------------------------------------------------
    def _capture_region(self):
        self.main_window._inject_desktop_target()
        QTimer.singleShot(100, self.main_window._start_region_capture)

    def _capture_window(self):
        self.main_window._inject_desktop_target()
        QTimer.singleShot(100, self.main_window._start_window_capture)

    def _capture_screen(self):
        self.main_window._inject_desktop_target()
        QTimer.singleShot(100, self.main_window._capture_fullscreen)

    def _show_main(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        # Re-register hotkeys if they were cleared on hide
        try:
            self.main_window._register_hotkeys_nonblocking()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _pin_to_all_desktops(self):
        if not PYVDA_AVAILABLE:
            return
        try:
            AppView(int(self.winId())).pin()
        except Exception as e:
            logging.error(f"FloatingBar pin failed: {e}")

    # ------------------------------------------------------------------
    def _restore_position(self):
        cfg = self.main_window.config
        pos = cfg.get('floating_bar_pos')
        screen = QApplication.primaryScreen().geometry()
        self.adjustSize()

        if pos:
            x, y = pos[0], pos[1]
            # If saved position is off-screen (monitor/layout changed), recover to visible area.
            if (
                x < screen.left() or y < screen.top() or
                x > screen.right() - self.width() or
                y > screen.bottom() - self.height()
            ):
                x = screen.center().x() - self.width() // 2
                y = 20
            self.move(x, y)
        else:
            # Default: top-centre of primary screen
            self.move(screen.center().x() - self.width() // 2, 20)

    def _save_position(self):
        self.main_window.config['floating_bar_pos'] = [self.x(), self.y()]
        self.main_window._save_config()

    # ------------------------------------------------------------------
    # Drag to move
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = None
            self._save_position()

    def closeEvent(self, event):
        self._save_position()
        event.accept()


# ============================================================================
# SEARCH PREVIEW DIALOG
# ============================================================================

class SearchPreviewDialog(QDialog):
    """Shows a screenshot with OCR search terms highlighted."""

    def __init__(self, filepath: Path, query: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.query = query.strip().lower()
        self.setWindowTitle(f"Preview — {filepath.name}")
        self.setMinimumSize(800, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet(f"background: {Theme.BG_DARKER}; padding: 4px 8px;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)

        self.info_label = QLabel("Loading highlights…")
        self.info_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 11px;")
        tb_layout.addWidget(self.info_label)
        tb_layout.addStretch()

        open_btn = QPushButton("Open in viewer")
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_DARK}; color: white;
                border: none; border-radius: 4px; padding: 3px 10px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {Theme.ACCENT}; }}
        """)
        open_btn.clicked.connect(lambda: os.startfile(str(filepath)))
        tb_layout.addWidget(open_btn)

        close_btn = QPushButton("✕ Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: #c0392b; color: white;
                border: none; border-radius: 4px; padding: 3px 10px; font-size: 11px;
            }}
            QPushButton:hover {{ background: #a93226; }}
        """)
        close_btn.clicked.connect(self.close)
        tb_layout.addWidget(close_btn)

        layout.addWidget(toolbar)

        # Scroll area with the image label
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)   # fixed size = native pixels, easy to scroll
        self._scroll.setStyleSheet("background: #111;")
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.image_label.setStyleSheet("background: #111;")
        self._scroll.setWidget(self.image_label)
        layout.addWidget(self._scroll)

        # Load image and run OCR highlight in background
        self._pixmap = QPixmap(str(filepath))
        if self._pixmap.isNull():
            self.info_label.setText("Could not load image.")
            return

        self.image_label.setPixmap(self._pixmap)
        self.image_label.setFixedSize(self._pixmap.size())

        # Show plain image immediately, then run OCR highlights
        QTimer.singleShot(50, self._build_highlights)

    def _build_highlights(self):
        """Run OCR word-box detection and paint highlights onto a copy of the pixmap."""
        if not OCR_AVAILABLE or not self.query:
            self.info_label.setText("No search query.")
            return

        words = [w for w in self.query.split() if w]

        try:
            img = Image.open(str(self.filepath))
            data = pytesseract.image_to_data(
                img, lang='eng', output_type=pytesseract.Output.DICT)
        except Exception as e:
            self.info_label.setText(f"OCR error: {e}")
            return

        # Find matching boxes
        matches = []
        n = len(data['text'])
        for i in range(n):
            word = data['text'][i].strip().lower()
            if not word:
                continue
            conf = int(data['conf'][i]) if str(data['conf'][i]).lstrip('-').isdigit() else 0
            if conf < 30:
                continue
            for q in words:
                if q in word:
                    matches.append({
                        'x': data['left'][i],
                        'y': data['top'][i],
                        'w': data['width'][i],
                        'h': data['height'][i],
                        'word': data['text'][i],
                    })
                    break

        if not matches:
            self.info_label.setText(f'No matches found for "{self.query}"')
            self.image_label.setPixmap(self._pixmap)
            return

        first = matches[0]

        # Paint highlights onto a copy
        result = self._pixmap.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        highlight_color = QColor(255, 220, 0, 140)   # yellow, semi-transparent
        border_color = QColor(255, 160, 0, 200)

        for m in matches:
            painter.setBrush(QBrush(highlight_color))
            painter.setPen(QPen(border_color, 1))
            painter.drawRoundedRect(
                m['x'] - 2, m['y'] - 2, m['w'] + 4, m['h'] + 4, 3, 3)

        painter.end()

        self.image_label.setPixmap(result)
        count = len(matches)
        self.info_label.setText(
            f'Found {count} match{"es" if count != 1 else ""} for "{self.query}"')

        # Scroll so the first match is visible and centred vertically
        QTimer.singleShot(30, lambda: self._scroll_to(first['x'], first['y'], first['h']))

    def _scroll_to(self, x: int, y: int, h: int):
        """Scroll the view so the match at (x, y) is centred in the viewport."""
        vbar = self._scroll.verticalScrollBar()
        hbar = self._scroll.horizontalScrollBar()
        viewport_h = self._scroll.viewport().height()
        viewport_w = self._scroll.viewport().width()
        # Centre the match vertically and horizontally
        target_y = max(0, y + h // 2 - viewport_h // 2)
        target_x = max(0, x - viewport_w // 2)
        vbar.setValue(target_y)
        hbar.setValue(target_x)


class CustomTitleBar(QWidget):
    """Custom title bar for frameless window with drag support"""

    def __init__(self, parent, title: str = APP_NAME, show_logo: bool = True, show_window_controls: bool = True):
        super().__init__(parent)
        self.parent_window = parent
        self.show_window_controls = show_window_controls
        self.dragging = False
        self.drag_position = QPoint()

        self.setObjectName("titleBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(10)

        # Logo (optional)
        if show_logo:
            self.logo_label = QLabel()
            logo_path = Path(__file__).parent / "logo.png"
            if logo_path.exists():
                logo_pixmap = QPixmap(str(logo_path))
                scaled = logo_pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                self.logo_label.setPixmap(scaled)
            self.logo_label.setStyleSheet("background: transparent;")
            layout.addWidget(self.logo_label)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.title_label.setStyleSheet(f"color: {Theme.TEXT_TITLEBAR}; background: transparent;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Search box — single QLineEdit with × action inside
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍  Text Search")
        self.search_edit.setFixedWidth(220)
        self.search_edit.setFixedHeight(24)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {Theme.BG_LIGHT};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 1px 24px 1px 8px;
                font-size: 11px;
            }}
            QLineEdit::placeholder {{
                color: {Theme.TEXT_MUTED};
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT};
            }}
            QLineEdit:selected {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)

        # Build a small × icon to use as a trailing action
        clear_icon_pixmap = QPixmap(16, 16)
        clear_icon_pixmap.fill(Qt.GlobalColor.transparent)
        _p = QPainter(clear_icon_pixmap)
        _p.setRenderHint(QPainter.RenderHint.Antialiasing)
        _p.setPen(QPen(QColor(Theme.TEXT_MUTED), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        _p.drawLine(4, 4, 12, 12)
        _p.drawLine(12, 4, 4, 12)
        _p.end()

        self._clear_action = self.search_edit.addAction(
            QIcon(clear_icon_pixmap), QLineEdit.ActionPosition.TrailingPosition)
        self._clear_action.triggered.connect(self.search_edit.clear)

        layout.addWidget(self.search_edit)
        layout.addSpacing(8)

        if self.show_window_controls:
            # Window control buttons (only needed in frameless mode).
            btn_style = f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {Theme.TEXT_TITLEBAR};
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 40px;
                    max-width: 40px;
                    min-height: 35px;
                    max-height: 35px;
                }}
                QPushButton:hover {{
                    background: {Theme.BUTTON_BG};
                    color: {Theme.TEXT_LIGHT};
                }}
            """

            close_style = f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: {Theme.TEXT_TITLEBAR};
                    font-size: 16px;
                    font-weight: bold;
                    min-width: 40px;
                    max-width: 40px;
                    min-height: 35px;
                    max-height: 35px;
                }}
                QPushButton:hover {{
                    background: {Theme.ERROR};
                    color: white;
                }}
            """

            # Minimize button
            self.btn_minimize = QPushButton("−")
            self.btn_minimize.setStyleSheet(btn_style)
            self.btn_minimize.clicked.connect(parent.showMinimized)
            layout.addWidget(self.btn_minimize)

            # Maximize button
            self.btn_maximize = QPushButton("□")
            self.btn_maximize.setStyleSheet(btn_style)
            self.btn_maximize.clicked.connect(self._toggle_maximize)
            layout.addWidget(self.btn_maximize)

            # Close button
            self.btn_close = QPushButton("×")
            self.btn_close.setStyleSheet(close_style)
            self.btn_close.clicked.connect(parent.close)
            layout.addWidget(self.btn_close)

    def _toggle_maximize(self):
        if not self.show_window_controls:
            return
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
            self.btn_maximize.setText("□")
        else:
            self.parent_window.showMaximized()
            self.btn_maximize.setText("❐")

    def mousePressEvent(self, event: QMouseEvent):
        if not self.show_window_controls:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.show_window_controls:
            return
        if self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self.show_window_controls:
            return
        self.dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if not self.show_window_controls:
            return
        self._toggle_maximize()


class SimpleTitleBar(QWidget):
    """Stable top bar used with native window frame."""

    def __init__(self, parent, title: str = APP_NAME):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {Theme.TEXT_TITLEBAR}; background: transparent;")
        layout.addWidget(title_label)
        layout.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Text Search")
        self.search_edit.setFixedWidth(240)
        self.search_edit.setFixedHeight(24)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {Theme.BG_LIGHT};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 11px;
            }}
            QLineEdit::placeholder {{
                color: {Theme.TEXT_MUTED};
            }}
            QLineEdit:focus {{
                border-color: {Theme.ACCENT};
            }}
        """)
        layout.addWidget(self.search_edit)


class HoverScrollArea(QScrollArea):
    """Scroll area that reveals vertical scrollbar on hover and hides it when not hovered."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovering_area = False
        self._hovering_bar = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(120)
        self._hide_timer.timeout.connect(self._apply_hidden_if_idle)

        vbar = self.verticalScrollBar()
        vbar.installEventFilter(self)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def enterEvent(self, event):
        self._hovering_area = True
        self._hide_timer.stop()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovering_area = False
        self._hide_timer.start()
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.verticalScrollBar():
            if event.type() == event.Type.Enter:
                self._hovering_bar = True
                self._hide_timer.stop()
                self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            elif event.type() == event.Type.Leave:
                self._hovering_bar = False
                self._hide_timer.start()
        return super().eventFilter(obj, event)

    def _apply_hidden_if_idle(self):
        if not self._hovering_area and not self._hovering_bar:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


# ============================================================================
# DELAY COUNTDOWN WINDOW
# ============================================================================

class DelayCountdown(QWidget):
    """Floating countdown window before capture"""

    countdown_complete = pyqtSignal()
    countdown_cancelled = pyqtSignal()

    def __init__(self, seconds: int):
        super().__init__()
        self.seconds_left = seconds

        # Frameless, always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        self.setFixedSize(150, 100)
        self.setStyleSheet(f"background: {Theme.BG_DARKER}; border-radius: 10px;")

        # Position top-right
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 170, 20)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Countdown number
        self.count_label = QLabel(str(seconds))
        self.count_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.count_label.setStyleSheet("color: white; background: transparent;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # Info text
        info_label = QLabel("Set up your screen...")
        info_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt; background: transparent;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BUTTON_BG};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background: {Theme.BUTTON_HOVER};
            }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(cancel_btn)

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self):
        self.seconds_left -= 1

        if self.seconds_left <= 0:
            self.timer.stop()
            self.close()
            self.countdown_complete.emit()
            return

        self.count_label.setText(str(self.seconds_left))

        # Color change
        if self.seconds_left <= 2:
            self.count_label.setStyleSheet("color: #ff5555; background: transparent;")
        elif self.seconds_left <= 3:
            self.count_label.setStyleSheet("color: #ffaa00; background: transparent;")

    def _cancel(self):
        self.timer.stop()
        self.close()
        self.countdown_cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()


# ============================================================================
# REGION SELECTOR
# ============================================================================

class RegionSelector(QWidget):
    """Fullscreen overlay for selecting a region to capture"""

    region_selected = pyqtSignal(QRect, QPixmap)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Capture screen using mss (reliable at all DPI scales)
        with mss.mss() as sct:
            self.full_capture = grab_to_pixmap(sct, sct.monitors[1])  # Primary monitor

        # Get screen geometry and actual display scale
        screen = QApplication.primaryScreen()
        screen_geom = screen.geometry()
        self.scale_factor = get_display_scale()

        # Scale capture to match logical screen size for display
        self.display_pixmap = self.full_capture.scaled(
            screen_geom.width(), screen_geom.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Fullscreen frameless overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setGeometry(screen_geom)

        self.start_point = None
        self.current_rect = QRect()
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw scaled display image (matches logical screen)
        painter.drawPixmap(0, 0, self.display_pixmap)

        # Dark overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        # If selecting, show clear region
        if not self.current_rect.isNull() and self.current_rect.width() > 0 and self.current_rect.height() > 0:
            # Draw the selected region without overlay (clear it)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawPixmap(self.current_rect, self.display_pixmap, self.current_rect)

            # Selection border
            painter.setPen(QPen(QColor(Theme.ACCENT), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.current_rect)

            # Show actual output dimensions (physical pixels)
            actual_w = int(self.current_rect.width() * self.scale_factor)
            actual_h = int(self.current_rect.height() * self.scale_factor)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 10))
            text = f"{actual_w} × {actual_h}"
            text_pos = self.current_rect.bottomRight() + QPoint(5, 15)

            # Background for text
            fm = QFontMetrics(painter.font())
            text_rect = fm.boundingRect(text)
            bg_rect = QRect(text_pos.x() - 2, text_pos.y() - text_rect.height(),
                           text_rect.width() + 4, text_rect.height() + 4)
            painter.fillRect(bg_rect, QColor(0, 0, 0, 150))
            painter.drawText(text_pos, text)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_point = event.pos()
            self.current_rect = QRect()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.start_point:
            self.current_rect = QRect(self.start_point, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.current_rect.width() > 10 and self.current_rect.height() > 10:
            # Scale coordinates to physical resolution for cropping
            physical_rect = QRect(
                int(self.current_rect.x() * self.scale_factor),
                int(self.current_rect.y() * self.scale_factor),
                int(self.current_rect.width() * self.scale_factor),
                int(self.current_rect.height() * self.scale_factor)
            )
            cropped = self.full_capture.copy(physical_rect)
            self.region_selected.emit(physical_rect, cropped)
        else:
            self.cancelled.emit()
        self.close()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()


# ============================================================================
# WINDOW SELECTOR
# ============================================================================

class WindowSelector(QWidget):
    """Overlay for selecting a window to capture - click-through with visual feedback"""

    window_selected = pyqtSignal(int)  # HWND
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Get Qt logical screen geometry (correct for DPI-aware processes)
        screen = QApplication.primaryScreen()
        screen_geom = screen.geometry()
        self.scale_factor = get_display_scale()

        # Store our own hwnd to exclude from detection
        self.my_hwnd = None
        self.info_hwnd = None
        self.highlighted_hwnd = None
        self.highlight_rect = None

        # Translucent overlay
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(screen_geom)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        # Info window
        self.info_window = QLabel("Click on a window to capture it\nPress ESC to cancel")
        self.info_window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.info_window.setStyleSheet(f"""
            background: {Theme.BG_DARKER};
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            font-size: 11pt;
        """)
        self.info_window.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_window.adjustSize()
        self.info_window.move(
            screen_geom.width() // 2 - self.info_window.width() // 2,
            50
        )
        self.info_window.show()

        # Get our window handles after showing
        QTimer.singleShot(10, self._store_handles)

    def _store_handles(self):
        """Store our window handles to exclude from detection"""
        self.my_hwnd = int(self.winId())
        self.info_hwnd = int(self.info_window.winId())

    def _get_window_at_point(self, x: int, y: int) -> int:
        """Get the window handle at point, excluding our overlays.
        x, y are Qt logical coordinates - must convert to physical for Win32 APIs."""
        # Convert logical coords to physical for Win32 APIs (DPI-aware process)
        phys_x = int(x * self.scale_factor)
        phys_y = int(y * self.scale_factor)
        hwnd = win32gui.WindowFromPoint((phys_x, phys_y))

        # If we got our own window, enumerate to find the one beneath
        if hwnd in (self.my_hwnd, self.info_hwnd):
            # Find window beneath us
            def callback(h, results):
                if h in (self.my_hwnd, self.info_hwnd):
                    return True
                if not win32gui.IsWindowVisible(h):
                    return True
                try:
                    rect = win32gui.GetWindowRect(h)  # Physical coords
                    if rect[0] <= phys_x <= rect[2] and rect[1] <= phys_y <= rect[3]:
                        results.append(h)
                except:
                    pass
                return True

            results = []
            win32gui.EnumWindows(callback, results)
            if results:
                hwnd = results[0]

        return win32gui.GetAncestor(hwnd, win32con.GA_ROOT) if hwnd else 0

    def paintEvent(self, event):
        painter = QPainter(self)
        # Light overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))

        # Highlight the window under cursor
        if self.highlight_rect:
            painter.setPen(QPen(QColor(Theme.ACCENT), 3))
            painter.setBrush(QColor(0, 120, 215, 50))
            painter.drawRect(self.highlight_rect)

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.globalPosition().toPoint()
        hwnd = self._get_window_at_point(pos.x(), pos.y())

        if hwnd and hwnd != self.highlighted_hwnd:
            self.highlighted_hwnd = hwnd
            try:
                rect = win32gui.GetWindowRect(hwnd)  # Physical coords from Win32
                # Convert physical coords to Qt logical coords for display
                s = self.scale_factor
                self.highlight_rect = QRect(
                    int(rect[0] / s), int(rect[1] / s),
                    int((rect[2] - rect[0]) / s), int((rect[3] - rect[1]) / s)
                )
            except:
                self.highlight_rect = None
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.globalPosition().toPoint()
            hwnd = self._get_window_at_point(pos.x(), pos.y())

            self.info_window.close()
            self.close()

            if hwnd:
                self.window_selected.emit(hwnd)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.info_window.close()
            self.close()
            self.cancelled.emit()


# ============================================================================
# TOAST NOTIFICATION
# ============================================================================

class ToastNotification(QWidget):
    """Fade in/out notification at bottom-right"""

    def __init__(self, pixmap: QPixmap, filename: str):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Container with styling
        container = QFrame(self)
        container.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_DARKER};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Thumbnail
        thumb = pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        thumb_label = QLabel()
        thumb_label.setPixmap(thumb)
        thumb_label.setStyleSheet("background: transparent;")
        layout.addWidget(thumb_label)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        saved_label = QLabel("✓ Saved!")
        saved_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: bold; font-size: 11pt; background: transparent;")
        text_layout.addWidget(saved_label)

        file_label = QLabel(filename)
        file_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt; background: transparent;")
        text_layout.addWidget(file_label)

        layout.addLayout(text_layout)

        # Size and position
        container.adjustSize()
        self.setFixedSize(container.size())

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20,
                  screen.height() - self.height() - 60)

        # Fade in animation
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)

        # Fade out animation
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(300)
        self.fade_out.setStartValue(1.0)
        self.fade_out.setEndValue(0.0)
        self.fade_out.finished.connect(self.close)

        # Start
        self.show()
        self.fade_in.start()
        QTimer.singleShot(2000, self.fade_out.start)


# ============================================================================
# THUMBNAIL WIDGET
# ============================================================================

class ThumbnailWidget(QFrame):
    """Clickable thumbnail with drag-drop support"""

    clicked = pyqtSignal(Path)
    double_clicked = pyqtSignal(Path)
    context_menu_requested = pyqtSignal(Path, QPoint)

    def __init__(self, filepath: Path, size: QSize, ocr_indexed: bool = False,
                 thumbnail_pixmap: Optional[QPixmap] = None):
        super().__init__()
        self.filepath = filepath
        self._drag_start_pos = None

        self.setFixedSize(size.width() + 10, size.height() + 10)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BUTTON_BG};
                border: 1px solid {Theme.BUTTON_HOVER};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border: 2px solid {Theme.ACCENT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # The picture arrives from the background ThumbnailLoader; never decode the full file here.
        self.cache_key: Optional[str] = None
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.thumb_label)
        if thumbnail_pixmap is not None and not thumbnail_pixmap.isNull():
            self.thumb_label.setPixmap(thumbnail_pixmap)

        self.ocr_badge: Optional[QLabel] = None
        self.set_ocr_indexed(ocr_indexed)

    def set_thumbnail(self, pixmap: QPixmap, cache_key: Optional[str]):
        self.thumb_label.setPixmap(pixmap)
        self.cache_key = cache_key

    def set_ocr_indexed(self, indexed: bool):
        """OCR badge — top-right overlay."""
        if not indexed:
            if self.ocr_badge is not None:
                self.ocr_badge.hide()
            return
        if self.ocr_badge is None:
            self.ocr_badge = QLabel("OCR", self)
            self.ocr_badge.setStyleSheet("""
                background: #2AA198;
                color: white;
                font-size: 8px;
                font-weight: bold;
                border-radius: 3px;
                padding: 1px 3px;
            """)
            self.ocr_badge.setFixedSize(26, 14)
            self.ocr_badge.move(self.width() - 30, 4)
        self.ocr_badge.show()
        self.ocr_badge.raise_()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self.filepath, event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start_pos and event.buttons() & Qt.MouseButton.LeftButton:
            if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
                # Start drag
                drag = QDrag(self)
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(str(self.filepath))])
                drag.setMimeData(mime)
                drag.setPixmap(self.grab().scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio))
                drag.exec(Qt.DropAction.MoveAction)
                self._drag_start_pos = None

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_pos:
            self.clicked.emit(self.filepath)
        self._drag_start_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.double_clicked.emit(self.filepath)


class FolderHoverPreview(QFrame):
    """Tooltip-like popup that shows larger previews for a folder on hover."""

    def __init__(self, image_paths: List[Path], base_thumb_size: int = 48):
        super().__init__(None, Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Theme.BG_LIGHT};
                border: 1px solid {Theme.ACCENT};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        zoom_width = max(96, base_thumb_size * 3)
        zoom_height = zoom_width * 2
        shown = 0
        for img_path in image_paths[:3]:
            preview = self._preview_pixmap(img_path, zoom_width, zoom_height)
            if preview.isNull():
                continue
            lbl = QLabel()
            lbl.setFixedSize(zoom_width, zoom_height)
            lbl.setPixmap(preview)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            shown += 1

        if shown == 0:
            empty = QLabel("No previews")
            empty.setStyleSheet(f"color: {Theme.TEXT_MUTED}; padding: 6px;")
            layout.addWidget(empty)

    _preview_cache: "OrderedDict[tuple, QPixmap]" = OrderedDict()

    @classmethod
    def _preview_pixmap(cls, img_path: Path, target_w: int, target_h: int) -> QPixmap:
        """Zoomed crop for the hover popup, made once per image and size (hovering used to decode 3 full files)."""
        base = _thumb_cache_base(img_path)
        key = (str(base or img_path), target_w, target_h)
        if key in cls._preview_cache:
            cls._preview_cache.move_to_end(key)
            return cls._preview_cache[key]

        source = load_thumbnail_master(img_path)
        if source.isNull():
            return QPixmap()
        # The popup zooms in; go back to the full file only when the small copy would be blown up.
        if (max(target_w / source.width(), target_h / source.height()) > 1.0
                and master_was_downscaled(source)):
            full = QImage(str(img_path))
            if not full.isNull():
                source = full
        preview = cls._scaled_cropped(QPixmap.fromImage(source), target_w, target_h)

        cls._preview_cache[key] = preview
        if len(cls._preview_cache) > 60:
            cls._preview_cache.popitem(last=False)
        return preview

    @staticmethod
    def _scaled_cropped(pixmap: QPixmap, target_w: int, target_h: int) -> QPixmap:
        scaled = pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - target_w) // 2)
        y = max(0, (scaled.height() - target_h) // 2)
        return scaled.copy(x, y, target_w, target_h)


# ============================================================================
# FOLDER BUTTON
# ============================================================================

class FolderPreviewWidget(QWidget):
    """Painted folder thumbnail where the folder graphic is the whole list item."""

    def __init__(self, images: List[Path], preview_width: int, preview_height: int,
                 folder_label: str, selected: bool = False):
        super().__init__()
        self.images = images
        self.folder_label = folder_label
        self.selected = selected
        self.preview_thumb_width = max(18, int(preview_width))
        self.preview_thumb_height = max(24, int(preview_height))
        self._source_pixmaps: List[QPixmap] = []
        self._slot_cache: Dict[tuple, QPixmap] = {}

        # Keep up to three most-recent screenshots for miniature strip rendering
        # (small cached copies, not full-size files held in memory).
        for img_path in self.images[:3]:
            master = load_thumbnail_master(img_path)
            if not master.isNull():
                self._source_pixmaps.append(QPixmap.fromImage(master))

        # Fill the full folder-card preview area instead of a small centered icon.
        self.setMinimumWidth(max(110, self.preview_thumb_width * 3 + 12))
        self.setFixedHeight(max(112, self.preview_thumb_height + 34))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Classic folder silhouette: back body + front pocket with angled left edge.
        outline = QColor(28, 70, 112) if self.selected else QColor(32, 79, 126)
        back_fill = QColor(238, 201, 142)
        front_fill = QColor(232, 201, 146)

        pad = 3.0
        body = QRectF(pad + 5, pad + 8, self.width() - (pad * 2) - 8, self.height() - (pad * 2) - 12)
        tab = QRectF(body.left() + 3, body.top() - 9, body.width() * 0.33, 13)

        painter.setPen(QPen(outline, 2))
        painter.setBrush(QBrush(back_fill))
        painter.drawRoundedRect(body, 10, 10)
        painter.drawRoundedRect(tab, 7, 7)

        painter.setPen(QColor(25, 56, 90))
        tab_font = painter.font()
        tab_font.setPointSize(8)
        tab_font.setBold(True)
        painter.setFont(tab_font)
        painter.drawText(tab.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, self.folder_label)

        front = QPainterPath()
        fx = pad
        fy = body.top() + 6
        fw = self.width() - (pad * 2) - 2
        fh = self.height() - fy - pad - 2
        front.moveTo(fx + 16, fy)
        front.lineTo(fx + fw - 12, fy)
        front.quadTo(fx + fw, fy, fx + fw - 2, fy + 10)
        front.lineTo(fx + fw - 8, fy + fh - 2)
        front.quadTo(fx + fw - 10, fy + fh + 2, fx + fw - 16, fy + fh + 2)
        front.lineTo(fx + 12, fy + fh + 2)
        front.quadTo(fx + 1, fy + fh + 2, fx + 1, fy + fh - 8)
        front.lineTo(fx + 6, fy + 14)
        front.quadTo(fx + 7, fy + 5, fx + 16, fy)
        front.closeSubpath()

        painter.setPen(QPen(outline, 2))
        painter.setBrush(QBrush(front_fill))
        painter.drawPath(front)

        # The preview image should read as part of the folder surface, not as
        # a separate inner "thumbnail widget".
        image_rect = QRectF(fx + 13, fy + 7, fw - 26, fh - 12)

        if self._source_pixmaps:
            slot_count = 3
            # Overlapping mini-previews for a stacked-paper look.
            step_factor = 0.58
            slot_w = max(1.0, image_rect.width() / (1 + (slot_count - 1) * step_factor))
            slot_step = slot_w * step_factor
            slot_h = max(1.0, image_rect.height() - 4.0)
            y_offsets = (0.0, 2.0, 4.0)

            # Most recent image is first in self.images, so render left-to-right.
            for i in range(slot_count):
                slot_rect = QRectF(
                    image_rect.left() + (i * slot_step),
                    image_rect.top() + y_offsets[i],
                    slot_w,
                    slot_h,
                )
                if i < len(self._source_pixmaps):
                    slot_key = (i, max(1, int(slot_rect.width())), max(1, int(slot_rect.height())))
                    preview = self._slot_cache.get(slot_key)
                    if preview is None:
                        preview = FolderButton._scaled_cropped(self._source_pixmaps[i], slot_key[1], slot_key[2])
                        self._slot_cache[slot_key] = preview
                    clip = QPainterPath()
                    clip.addRoundedRect(QRectF(slot_rect.adjusted(0.5, 0.5, -0.5, -0.5)), 4, 4)
                    painter.save()
                    painter.setClipPath(clip)
                    painter.drawPixmap(slot_rect.toRect(), preview)
                    painter.restore()
                    painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRoundedRect(slot_rect.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
                else:
                    painter.setPen(QPen(QColor(196, 168, 121), 1))
                    painter.setBrush(QBrush(QColor(227, 195, 140)))
                    painter.drawRoundedRect(slot_rect, 4, 4)

            # Subtle tint so minis still read as part of a folder surface.
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(232, 201, 146, 32)))
            painter.drawRoundedRect(image_rect, 6, 6)
        else:
            painter.setPen(QColor(Theme.TEXT_MUTED))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "No preview")


class FolderButton(QFrame):
    """Folder button with folder-style preview cards"""

    clicked = pyqtSignal(object)  # folder name or None
    context_menu_requested = pyqtSignal(object, QPoint)
    file_dropped = pyqtSignal(object, Path)  # folder, source file

    def __init__(self, folder_name: Optional[str], base_dir: Path, selected: bool = False,
                 preview_width: int = 48):
        super().__init__()
        self.folder_name = folder_name
        self.base_dir = base_dir
        self.selected = selected
        self.preview_thumb_width = max(18, int(preview_width))
        # Make folder cards visibly taller so miniature screenshot strips have room.
        self.preview_thumb_height = max(68, int(self.preview_thumb_width * 2.1))
        self._preview_images: List[Path] = []
        self._hover_preview: Optional[FolderHoverPreview] = None

        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)

        self._update_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Build recent image list for preview + hover panel
        folder_path = base_dir / folder_name if folder_name else base_dir
        if folder_path.exists():
            # scandir carries the dates on Windows: one disk call per folder, not two per file.
            dated = []
            try:
                with os.scandir(folder_path) as it:
                    for entry in it:
                        if entry.name.lower().endswith(".png"):
                            try:
                                if entry.is_file():
                                    dated.append((entry.stat().st_mtime, folder_path / entry.name))
                            except OSError:
                                continue
            except OSError:
                pass
            dated.sort(key=lambda e: e[0], reverse=True)
            self._preview_images = [p for _, p in dated[:3]]

        self.preview_widget = FolderPreviewWidget(
            self._preview_images,
            self.preview_thumb_width,
            self.preview_thumb_height,
            folder_name or "Main",
            selected=self.selected,
        )
        layout.addWidget(self.preview_widget)

    def _update_style(self):
        # No outer card framing: the folder artwork itself is the full item.
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        if hasattr(self, 'preview_widget'):
            self.preview_widget.set_selected(self.selected)

    def set_selected(self, selected: bool):
        self.selected = selected
        self._update_style()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.folder_name)
        elif event.button() == Qt.MouseButton.RightButton:
            if self.folder_name:  # Don't show context menu for "Main"
                self.context_menu_requested.emit(self.folder_name, event.globalPosition().toPoint())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def enterEvent(self, event):
        if self._preview_images:
            self._hover_preview = FolderHoverPreview(self._preview_images, self.preview_thumb_width)
            self._hover_preview.adjustSize()
            pos = self.mapToGlobal(QPoint(-self._hover_preview.width() - 10, 0))
            self._hover_preview.move(pos)
            self._hover_preview.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._hover_preview:
            self._hover_preview.close()
            self._hover_preview = None
        super().leaveEvent(event)

    def dragLeaveEvent(self, event):
        self._update_style()

    def dropEvent(self, event):
        self._update_style()
        urls = event.mimeData().urls()
        for url in urls:
            source = Path(url.toLocalFile())
            if source.suffix.lower() == '.png':
                self.file_dropped.emit(self.folder_name, source)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    @staticmethod
    def _scaled_cropped(pixmap: QPixmap, target_w: int, target_h: int) -> QPixmap:
        scaled = pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - target_w) // 2)
        y = max(0, (scaled.height() - target_h) // 2)
        return scaled.copy(x, y, target_w, target_h)


# ============================================================================
# STYLED DIALOG  — replaces all QMessageBox calls app-wide
# ============================================================================

class StyledDialog(QDialog):
    """
    Themed replacement for QMessageBox.
    Usage:
        dlg = StyledDialog(parent, title, message, buttons)
        # buttons = list of (label, role)  role: 'primary' | 'danger' | 'secondary'
        result = dlg.exec()   # returns label of clicked button, or None
    """

    _clicked: str = None

    def __init__(self, parent, title: str, message: str,
                 sub: str = "",
                 buttons: list = None):
        super().__init__(parent)
        if buttons is None:
            buttons = [("OK", "primary")]

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(420)

        # ── outer card ──────────────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background: #1C2936;
                border: 1px solid #2AA198;
                border-radius: 12px;
            }
        """)
        outer.addWidget(card)

        vl = QVBoxLayout(card)
        vl.setContentsMargins(28, 22, 28, 20)
        vl.setSpacing(12)

        # title bar row
        title_row = QHBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #2AA198; font-size: 13pt; font-weight: bold; background: transparent;")
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        vl.addLayout(title_row)

        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2AA19840;")
        vl.addWidget(sep)

        # message
        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            "color: #EEE8D5; font-size: 11pt; background: transparent;")
        vl.addWidget(msg_lbl)

        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setWordWrap(True)
            sub_lbl.setStyleSheet(
                "color: #93A1A1; font-size: 9pt; background: transparent;")
            vl.addWidget(sub_lbl)

        vl.addSpacing(6)

        # buttons row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.setSpacing(10)

        _role_styles = {
            'primary': (
                "QPushButton{background:#2AA198;color:#fff;border:none;"
                "border-radius:6px;padding:8px 22px;font-size:10pt;font-weight:bold;}"
                "QPushButton:hover{background:#33c4bb;}"
                "QPushButton:pressed{background:#1d8a82;}"
            ),
            'danger': (
                "QPushButton{background:#DC322F;color:#fff;border:none;"
                "border-radius:6px;padding:8px 22px;font-size:10pt;font-weight:bold;}"
                "QPushButton:hover{background:#e85552;}"
                "QPushButton:pressed{background:#b52724;}"
            ),
            'secondary': (
                "QPushButton{background:#073642;color:#93A1A1;border:1px solid #2AA19860;"
                "border-radius:6px;padding:8px 22px;font-size:10pt;}"
                "QPushButton:hover{background:#0d4a5c;color:#EEE8D5;}"
                "QPushButton:pressed{background:#002B36;}"
            ),
        }

        self._result = None
        for label, role in buttons:
            btn = QPushButton(label)
            btn.setStyleSheet(_role_styles.get(role, _role_styles['secondary']))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, l=label: self._finish(l))
            btn_row.addWidget(btn)

        vl.addLayout(btn_row)

    def _finish(self, label: str):
        self._result = label
        self.accept()

    def exec(self) -> str:   # type: ignore[override]
        super().exec()
        return self._result

    # ── convenience class-methods mirroring QMessageBox API ─────────────────

    @classmethod
    def question(cls, parent, title: str, message: str,
                 yes_text="Yes", no_text="No") -> bool:
        dlg = cls(parent, title, message, buttons=[
            (yes_text, 'danger'), (no_text, 'secondary')])
        return dlg.exec() == yes_text

    @classmethod
    def warning(cls, parent, title: str, message: str):
        dlg = cls(parent, title, message, buttons=[("OK", "primary")])
        dlg.exec()

    @classmethod
    def info(cls, parent, title: str, message: str):
        dlg = cls(parent, title, message, buttons=[("OK", "primary")])
        dlg.exec()


# ============================================================================
# VOICE NOTE — speak or type a note; speech is turned into text on this PC
# ============================================================================

# Offline Whisper (faster-whisper). The model is downloaded once into WHISPER_DIR and
# loaded on first use; nothing is sent anywhere.
WHISPER_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "OtterlyScreenshots" / "whisper"
WHISPER_MODEL = "base"
WHISPER_RATE = 16000            # Whisper listens at 16 kHz mono


class _Whisper:
    """The speech model, loaded once and kept for the life of the app."""
    _model = None
    _lock = threading.Lock()

    @classmethod
    def ready(cls) -> bool:
        return cls._model is not None

    @classmethod
    def model(cls):
        with cls._lock:
            if cls._model is None:
                from faster_whisper import WhisperModel
                WHISPER_DIR.mkdir(parents=True, exist_ok=True)
                cls._model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8",
                                          download_root=str(WHISPER_DIR))
            return cls._model

    @classmethod
    def transcribe(cls, audio) -> str:
        """float32 mono 16 kHz samples -> text. The voice filter drops silence, so a quiet
        recording gives "" rather than an invented sentence."""
        model = cls.model()
        with cls._lock:
            segments, _info = model.transcribe(audio, vad_filter=True, beam_size=5)
            return " ".join(s.text.strip() for s in segments).strip()


_LIVE_WORKERS = set()      # keep running workers alive until they finish


class _SpeechWorker(QThread):
    """Loads the model (audio=None) or turns one recording into text, off the UI thread."""
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, audio=None):
        super().__init__()
        self.audio = audio
        _LIVE_WORKERS.add(self)
        self.finished.connect(lambda: _LIVE_WORKERS.discard(self))

    def run(self):
        try:
            if self.audio is None:
                _Whisper.model()
                self.done.emit("")
            else:
                self.done.emit(_Whisper.transcribe(self.audio))
        except Exception as e:
            logging.error(f"Voice note speech engine failed: {e}")
            self.failed.emit(str(e))


class _MicRecorder:
    """Records the default microphone with Qt Multimedia; stop() returns 16 kHz mono float32."""

    def __init__(self, on_chunk=None):
        self._src = None
        self._io = None
        self._buf = bytearray()
        self.level = 0.0            # loudness of the latest chunk, 0..1
        # Live voice typing hands each piece of sound on as it arrives, (float32 samples, rate),
        # instead of keeping the whole recording.
        self._on_chunk = on_chunk
        self._rest = b""

    def start(self):
        """Start listening; returns None, or why it could not."""
        try:
            from PyQt6.QtMultimedia import QAudioSource, QMediaDevices, QAudioFormat
        except Exception as e:
            return f"Qt Multimedia is not available ({e})"
        dev = QMediaDevices.defaultAudioInput()
        if dev.isNull():
            return "No microphone found"
        fmt = QAudioFormat()
        fmt.setSampleRate(WHISPER_RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not dev.isFormatSupported(fmt):
            fmt = dev.preferredFormat()
        self._fmt = fmt
        self._buf = bytearray()
        self.level = 0.0
        self._src = QAudioSource(dev, fmt)
        self._io = self._src.start()
        if self._io is None:
            self._src = None
            return "The microphone could not be opened"
        self._io.readyRead.connect(self._read)
        return None

    @property
    def active(self) -> bool:
        return self._src is not None

    def _samples(self, data: bytes):
        import numpy as np
        from PyQt6.QtMultimedia import QAudioFormat
        SF = QAudioFormat.SampleFormat
        sf = self._fmt.sampleFormat()
        if sf == SF.Int16:
            a = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        elif sf == SF.Int32:
            a = np.frombuffer(data, dtype="<i4").astype(np.float32) / 2147483648.0
        elif sf == SF.Float:
            a = np.frombuffer(data, dtype="<f4").astype(np.float32)
        else:   # UInt8
            a = (np.frombuffer(data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        ch = max(1, self._fmt.channelCount())
        if ch > 1:
            a = a[: len(a) - len(a) % ch].reshape(-1, ch).mean(axis=1)
        return a

    def _read(self):
        if self._io is None:
            return
        data = self._io.readAll().data()
        if not data:
            return
        if self._on_chunk is not None:
            frame = max(1, self._fmt.bytesPerFrame())
            data = self._rest + data
            cut = len(data) - len(data) % frame
            self._rest = data[cut:]
            data = data[:cut]
            if not data:
                return
            try:
                a = self._samples(data)
                if len(a):
                    import numpy as np
                    self.level = float(min(1.0, np.sqrt(np.mean(a * a)) * 6))
                    self._on_chunk(a, self._fmt.sampleRate())
            except Exception as e:
                logging.error(f"Live voice typing: microphone chunk failed: {e}")
            return
        self._buf += data
        try:
            import numpy as np
            frame = max(1, self._fmt.bytesPerFrame())
            a = self._samples(bytes(data[: len(data) - len(data) % frame]))
            if len(a):
                self.level = float(min(1.0, np.sqrt(np.mean(a * a)) * 6))
        except Exception:
            pass

    def seconds(self) -> float:
        if not self._buf:
            return 0.0
        return len(self._buf) / max(1, self._fmt.bytesPerFrame()) / max(1, self._fmt.sampleRate())

    def stop(self):
        """Stop listening; returns the recording as 16 kHz mono float32 (empty if nothing)."""
        import numpy as np
        if self._src is not None:
            self._read()
            self._src.stop()
        self._src = None
        self._io = None
        frame = max(1, self._fmt.bytesPerFrame())
        data = bytes(self._buf[: len(self._buf) - len(self._buf) % frame])
        self._buf = bytearray()
        if not data:
            return np.zeros(0, dtype=np.float32)
        a = self._samples(data)
        rate = self._fmt.sampleRate()
        if rate != WHISPER_RATE and len(a) > 1:
            n = int(len(a) * WHISPER_RATE / rate)
            a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32)
        return a


class VoiceNoteDialog(QDialog):
    """Speak or type a note. It starts listening when it opens; Stop turns the speech into
    text with offline Whisper and adds it to the box, where it can be corrected."""

    DEFAULT_SIZE = 12
    MAX_SECONDS = 300            # a recording stops by itself after five minutes

    def __init__(self, parent=None, size: int = DEFAULT_SIZE, auto_record: bool = True):
        from PyQt6.QtWidgets import QPlainTextEdit, QProgressBar
        super().__init__(parent)
        self.setWindowTitle("Otterly — Voice note")
        self.setStyleSheet("""
            QDialog, QWidget { background:#f0f0f0; color:#222222; }
            QPlainTextEdit { background:white; border:1px solid #bbbbbb; border-radius:6px;
                             padding:6px; font-size:12pt; }
            QPushButton { background:#e8e8e8; border:1px solid #bbbbbb; border-radius:6px;
                          padding:6px 14px; font-size:10pt; }
            QPushButton:hover { background:#d0d0d0; border-color:#888888; }
            QPushButton:disabled { color:#999999; }
            QSpinBox { background:white; border:1px solid #bbbbbb; border-radius:4px; padding:2px 4px; }
            QProgressBar { background:#dddddd; border:none; border-radius:3px; }
            QProgressBar::chunk { background:#2AA198; border-radius:3px; }
        """)
        self._auto_record = auto_record
        self._opened = False
        self._rec = _MicRecorder()
        self._busy = False            # a recording is being turned into text
        self._accept_after = False    # Add was pressed while listening
        self._engine_error = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.status_lbl = QLabel("Speak or type your note.")
        self.status_lbl.setStyleSheet("color:#555; font-size:9pt; background:transparent;")
        top.addWidget(self.status_lbl, 1)
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedSize(120, 8)
        self.level_bar.setToolTip("Microphone level")
        top.addWidget(self.level_bar)
        lay.addLayout(top)

        self.edit = QPlainTextEdit()
        self.edit.setMinimumSize(600, 220)      # 255+ characters show without scrolling
        self.edit.setPlaceholderText("Your note…")
        self.edit.textChanged.connect(self._count)
        lay.addWidget(self.edit)

        row = QHBoxLayout()
        self._mic_icon = QIcon(ScreenshotEditor._make_icon_mic())
        self.mic_btn = QPushButton()
        self.mic_btn.setIconSize(QSize(20, 20))
        self.mic_btn.clicked.connect(self._toggle)
        row.addWidget(self.mic_btn)
        size_lbl = QLabel("Size")
        size_lbl.setStyleSheet("background:transparent; margin-left:10px;")
        row.addWidget(size_lbl)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 72)
        self.size_spin.setValue(size)
        row.addWidget(self.size_spin)
        self.count_lbl = QLabel("0 characters")
        self.count_lbl.setStyleSheet("color:#777; background:transparent; margin-left:10px;")
        row.addWidget(self.count_lbl)
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self.add_btn = QPushButton("Add to picture")
        self.add_btn.setStyleSheet("QPushButton{background:#2AA198;color:white;border:none;}"
                                   "QPushButton:hover{background:#33c4bb;}")
        self.add_btn.setToolTip("Add the note to the picture  [Ctrl+Enter]")
        self.add_btn.clicked.connect(self._add)
        row.addWidget(self.add_btn)
        lay.addLayout(row)
        # Enter makes a new line in the note; Ctrl+Enter adds it
        from PyQt6.QtGui import QShortcut, QKeySequence
        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self, activated=self._add)

        self._tick = QTimer(self)
        self._tick.setInterval(150)
        self._tick.timeout.connect(self._on_tick)
        self._show_button()

    # ── state ────────────────────────────────────────────────────────────────

    def _show_button(self):
        if self._rec.active:
            self.mic_btn.setIcon(QIcon())
            self.mic_btn.setText("■  Stop")
            self.mic_btn.setStyleSheet("QPushButton{background:#DC322F;color:white;border:none;}"
                                       "QPushButton:hover{background:#e85552;}")
            self.mic_btn.setToolTip("Stop listening and write down what you said")
        else:
            self.mic_btn.setIcon(self._mic_icon)
            self.mic_btn.setText(" Speak" if not self.edit.toPlainText().strip() else " Speak more")
            self.mic_btn.setStyleSheet("")
            self.mic_btn.setToolTip("Start listening to the microphone")
        self.mic_btn.setEnabled(not self._busy)

    def _status(self, text: str, color: str = "#555"):
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color:{color}; font-size:9pt; background:transparent;")

    def _count(self):
        n = len(self.edit.toPlainText())
        self.count_lbl.setText(f"{n} character" + ("" if n == 1 else "s"))
        if not self._rec.active:
            self._show_button()

    def showEvent(self, event):
        super().showEvent(event)
        self.edit.setFocus()
        if self._opened:
            return
        self._opened = True
        if not _Whisper.ready():
            w = _SpeechWorker(None)            # get the model loaded while you talk
            w.failed.connect(self._engine_failed)
            w.start()
        if self._auto_record:
            QTimer.singleShot(0, self._start)

    def _engine_failed(self, err: str):
        self._engine_error = err
        if not self._rec.active and not self._busy:
            self._status("Voice typing is not available — you can still type.  "
                         f"({err[:90]})", "#DC322F")

    # ── listening ────────────────────────────────────────────────────────────

    def _toggle(self):
        if self._rec.active:
            self._stop()
        else:
            self._start()

    def _start(self):
        if self._rec.active or self._busy:
            return
        err = self._rec.start()
        if err:
            self._status(f"{err} — you can still type.", "#DC322F")
            self._show_button()
            return
        self._tick.start()
        self._on_tick()
        self._show_button()

    def _on_tick(self):
        if not self._rec.active:
            return
        secs = self._rec.seconds()
        self.level_bar.setValue(int(self._rec.level * 100))
        self._status(f"● Listening…  {int(secs) // 60}:{int(secs) % 60:02d}   — press Stop when you are done",
                     "#DC322F")
        if secs >= self.MAX_SECONDS:
            self._stop()

    def _stop(self):
        if not self._rec.active:
            return
        self._tick.stop()
        audio = self._rec.stop()
        self.level_bar.setValue(0)
        if len(audio) < WHISPER_RATE * 0.3:
            self._status("Nothing was recorded — press Speak to try again.", "#555")
            self._show_button()
            self._finish_pending_add()
            return
        self._busy = True
        self._status("Writing down what you said…" if _Whisper.ready()
                     else "Getting the speech engine ready, then writing it down…", "#2AA198")
        self._show_button()
        w = _SpeechWorker(audio)
        w.done.connect(self._heard)
        w.failed.connect(self._heard_failed)
        w.start()

    def _heard(self, text: str):
        self._busy = False
        if text:
            cur = self.edit.toPlainText()
            sep = "" if not cur or cur[-1].isspace() else " "
            from PyQt6.QtGui import QTextCursor
            self.edit.moveCursor(QTextCursor.MoveOperation.End)
            self.edit.insertPlainText(sep + text)
            self._status("Done — correct it if you need to, Speak more, or Add to picture.", "#555")
        else:
            self._status("No speech was heard — press Speak to try again.", "#555")
        self._show_button()
        self._finish_pending_add()

    def _heard_failed(self, err: str):
        self._busy = False
        self._status(f"Could not turn the speech into text ({err[:90]}) — you can still type.", "#DC322F")
        self._show_button()
        self._accept_after = False

    # ── closing ──────────────────────────────────────────────────────────────

    def _add(self):
        if self._rec.active or self._busy:
            # finish writing down what was said first, then add the note
            self._accept_after = True
            self._stop()
            return
        self.accept()

    def _finish_pending_add(self):
        if self._accept_after:
            self._accept_after = False
            self.accept()

    def done(self, r):
        self._tick.stop()
        if self._rec.active:
            self._rec.stop()           # Cancel / Esc while listening: drop the recording
        super().done(r)

    def text(self) -> str:
        return self.edit.toPlainText()

    def size_value(self) -> int:
        return self.size_spin.value()


# ============================================================================
# LIVE VOICE TYPING — speak into any text box; the words show while you talk
# ============================================================================
# Ctrl+Shift+Space anywhere starts listening, and again stops it. A streaming speech engine
# (sherpa-onnx running NVIDIA's FastConformer, 480 ms steps) shows the words in a strip by the cursor
# as you speak. When you pause, a larger model (NVIDIA Parakeet TDT 0.6B v2) listens to that whole
# phrase again and its text, with capitals and punctuation, is typed into the text box that has the
# cursor. A small punctuation model joins the phrases into sentences. All on this PC.

LIVE_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "OtterlyScreenshots" / "sherpa"
# 480 ms steps, not 80: the 80 ms model needs 51-64% of a real-time second on this PC and falls
# behind when the PC is busy; this one needs about 20%, and the words show half a second apart.
LIVE_ASR = "sherpa-onnx-nemo-streaming-fast-conformer-transducer-en-480ms-int8"
LIVE_PUNCT = "sherpa-onnx-online-punct-en-2024-08-06"
# The second listen. Paul's own voice test (2026-11-04): it heard him best of the live model,
# Parakeet v2, Parakeet v3 and Whisper. About 0.6 s a phrase here, more when the PC is busy.
LIVE_RECHECK = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
_SHERPA_RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
LIVE_URLS = {
    LIVE_ASR: f"{_SHERPA_RELEASES}/asr-models/{LIVE_ASR}.tar.bz2",
    LIVE_PUNCT: f"{_SHERPA_RELEASES}/punctuation-models/{LIVE_PUNCT}.tar.bz2",
    LIVE_RECHECK: f"{_SHERPA_RELEASES}/asr-models/{LIVE_RECHECK}.tar.bz2",
}
LIVE_FILES = {
    LIVE_ASR: ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"),
    LIVE_PUNCT: ("model.int8.onnx", "bpe.vocab"),
    LIVE_RECHECK: ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"),
}
_LIVE_LABELS = {LIVE_ASR: "live speech model", LIVE_PUNCT: "punctuation model",
                LIVE_RECHECK: "accurate speech model"}
LIVE_HOTKEY = "ctrl+shift+space"
LIVE_HOTKEY_LABEL = "Ctrl+Shift+Space"
LIVE_QUIET_STOP = 30        # seconds without a word heard: stop listening by itself
LIVE_PAUSE = 0.8            # seconds of quiet after speech that end a phrase (it is typed then)
LIVE_CONTEXT_WORDS = 30     # earlier words the punctuation model sees, so a phrase reads on from them
LIVE_FREE_AFTER = 15 * 60   # seconds of no voice typing before the models are let go (~0.9 GB)
_LIVE_MARKS = ".?!,;:"


class _LiveModels:
    """The three models: downloaded once (about 620 MB), loaded on first use, let go when idle."""
    _asr = None
    _punct = None
    _recheck = None
    _lock = threading.Lock()
    _recheck_lock = threading.Lock()
    punct_lock = threading.Lock()      # the punctuation model is used from two threads

    @classmethod
    def on_disk(cls) -> bool:
        return all((LIVE_DIR / name / f).is_file() for name, files in LIVE_FILES.items() for f in files)

    @classmethod
    def ready(cls) -> bool:
        return cls._asr is not None and cls._punct is not None

    @classmethod
    def unload(cls):
        with cls._lock, cls._recheck_lock:
            cls._asr = cls._punct = cls._recheck = None

    @classmethod
    def _download(cls, name: str, progress=None):
        import urllib.request
        import tarfile
        LIVE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = LIVE_DIR / f"_download_{name}"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        archive = tmp / f"{name}.tar.bz2"
        try:
            with urllib.request.urlopen(LIVE_URLS[name], timeout=60) as r, open(archive, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    block = r.read(1 << 20)
                    if not block:
                        break
                    f.write(block)
                    done += len(block)
                    if progress:
                        progress(done, total)
            with tarfile.open(archive) as t:
                # realpath: under a packaged parent (Claude's desktop app) AppData is redirected,
                # and the safety check compares the members' real paths with this one.
                t.extractall(os.path.realpath(tmp), filter="data")
            src = tmp / name
            if not src.is_dir():
                raise RuntimeError(f"the download of {name} did not hold the model")
            dst = LIVE_DIR / name
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.move(str(src), str(dst))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @classmethod
    def _ensure(cls, name: str, status=None):
        if all((LIVE_DIR / name / f).is_file() for f in LIVE_FILES[name]):
            return
        label = _LIVE_LABELS[name]

        def _p(done, total):
            if status:
                status(f"Downloading the {label} (once): {done / 1e6:.0f} of {total / 1e6:.0f} MB"
                       if total else f"Downloading the {label}: {done / 1e6:.0f} MB")
        _p(0, 0)
        cls._download(name, _p)

    @classmethod
    def load(cls, status=None):
        """(live recognizer, punctuation) — downloads what is missing first. status(text) says what it is doing."""
        with cls._lock:
            if cls.ready():
                return cls._asr, cls._punct
            cls._ensure(LIVE_ASR, status)
            cls._ensure(LIVE_PUNCT, status)
            if status:
                status("Getting ready…")
            import sherpa_onnx
            a = LIVE_DIR / LIVE_ASR
            asr = sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=str(a / "tokens.txt"), encoder=str(a / "encoder.int8.onnx"),
                decoder=str(a / "decoder.int8.onnx"), joiner=str(a / "joiner.int8.onnx"),
                num_threads=2, sample_rate=WHISPER_RATE, feature_dim=80, decoding_method="greedy_search",
                enable_endpoint_detection=True, rule1_min_trailing_silence=2.4,
                rule2_min_trailing_silence=LIVE_PAUSE, rule3_min_utterance_length=20)
            p = LIVE_DIR / LIVE_PUNCT
            punct = sherpa_onnx.OnlinePunctuation(sherpa_onnx.OnlinePunctuationConfig(
                model_config=sherpa_onnx.OnlinePunctuationModelConfig(
                    cnn_bilstm=str(p / "model.int8.onnx"), bpe_vocab=str(p / "bpe.vocab"), num_threads=1)))
            cls._asr, cls._punct = asr, punct
            return asr, punct

    @classmethod
    def load_recheck(cls, status=None):
        """The accurate model that listens to each finished phrase again."""
        with cls._recheck_lock:
            if cls._recheck is None:
                cls._ensure(LIVE_RECHECK, status)
                import sherpa_onnx
                d = LIVE_DIR / LIVE_RECHECK
                cls._recheck = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=str(d / "encoder.int8.onnx"), decoder=str(d / "decoder.int8.onnx"),
                    joiner=str(d / "joiner.int8.onnx"), tokens=str(d / "tokens.txt"),
                    # 6 threads: here the slowest tenth of phrases took 1.2 s against 2.3 s with 4.
                    num_threads=6, model_type="nemo_transducer", decoding_method="greedy_search")
            return cls._recheck

    @classmethod
    def recheck(cls, pieces) -> str:
        """The phrase's sound, [(samples, rate), ...], heard again in one go."""
        rec = cls.load_recheck()
        st = rec.create_stream()
        for samples, rate in pieces:
            st.accept_waveform(rate, samples)
        rec.decode_stream(st)
        return st.result.text.strip()


def _tidy_heard(text: str) -> str:
    """Small fixes to the accurate model's text: it glues a currency sign to the word before
    ("at$2.15")."""
    import re
    return re.sub(r"(?<=[A-Za-z])(?=[$€£]\d)", " ", text).strip()


def _ends_sentence(mark: str) -> bool:
    return mark[:1] in (".", "?", "!")      # not `in ".?!"`: "" is in every string


def _plain_word(tok: str) -> str:
    return tok.strip(_LIVE_MARKS + "\"'()").lower()


class _LivePhrases:
    """Turns each finished phrase into the text that is typed, read on from what was already typed.
    A pause can fall in the middle of a sentence, so a phrase is punctuated together with the words
    before it, and only the mark the earlier word gains (a full stop, a comma) is typed ahead of the
    new words; nothing already typed is ever changed. For the same reason a phrase's own last mark is
    held back: the next phrase, or Stop, decides it (every lone phrase gets one: "Can you send me the
    report?" + "by Tuesday?")."""

    def __init__(self, punct):
        self.punct = punct
        self.words: list = []        # every word typed so far, plain
        self.last_typed = ""         # the last word as it was typed
        self.held = ""               # the accurate model's own mark at the end of the last phrase

    def _punctuate(self, words: list) -> list:
        with _LiveModels.punct_lock:
            return self.punct.add_punctuation_with_case(" ".join(words)).split()

    def render(self, raw: str):
        """(mark for the word before, the new words) for one phrase, without taking it."""
        new = raw.split()
        if not new:
            return "", ""
        ctx = self.words[-LIVE_CONTEXT_WORDS:]
        out = self._punctuate(ctx + new)
        if len(out) != len(ctx) + len(new):          # never happens in practice; keep it safe
            return "", " ".join(self._punctuate(new)).rstrip(_LIVE_MARKS)
        mark = ""
        if ctx:
            before = out[len(ctx) - 1]
            tail = before[len(before.rstrip(_LIVE_MARKS)):]
            if tail and not self.last_typed.endswith(tail):
                mark = tail
        toks = out[len(ctx):]
        toks[-1] = toks[-1].rstrip(_LIVE_MARKS)
        if not toks[-1]:
            toks.pop()
        return mark, " ".join(toks)

    def take(self, raw: str) -> str:
        """The text to type for a phrase, from the live model's plain words."""
        mark, text = self.render(raw)
        if not text:
            return ""
        typed = (mark + " " + text) if self.words else text
        self.words += raw.split()
        self.last_typed = text.split()[-1]
        self.held = ""
        return typed

    def take_heard(self, heard: str) -> str:
        """The text to type for a phrase, from the accurate model's own words and punctuation. The
        punctuation model, which sees the phrases before, decides only where a sentence ends
        between phrases, and so whether this phrase starts with a capital."""
        toks = [t for t in _tidy_heard(heard).split() if _plain_word(t)]
        if not toks:
            return ""
        plain = [_plain_word(t) for t in toks]
        mark, ptext = self.render(" ".join(plain))
        if self.words and _ends_sentence(mark) and _ends_sentence(self.held):
            mark = self.held                   # its question mark: it heard the voice go up
        ptoks = ptext.split()
        first = toks[0]
        if self.words and ptoks and _plain_word(ptoks[0]) == plain[0]:
            starts = ptoks[0][:1].isupper()
            if starts and first[:1].islower():
                first = first[:1].upper() + first[1:]
            elif not starts and first[:1].isupper() and first[1:2].islower():
                first = first[:1].lower() + first[1:]     # "By Tuesday" after "...the report"
        toks[0] = first
        last = toks[-1]
        self.held = last[len(last.rstrip(_LIVE_MARKS)):]
        toks[-1] = last.rstrip(_LIVE_MARKS)
        typed = (mark + " " if self.words else "") + " ".join(toks)
        self.words += plain
        self.last_typed = toks[-1]
        return typed

    def ending(self) -> str:
        """The full stop or question mark the last sentence needs when you stop."""
        if not self.words or (self.last_typed[-1:] and self.last_typed[-1:] in _LIVE_MARKS):
            return ""
        if _ends_sentence(self.held):
            return self.held[:1]
        ctx = self.words[-LIVE_CONTEXT_WORDS:]
        # A word after it lets the model see that the sentence is over.
        out = self._punctuate(ctx + ["thank", "you"])
        if len(out) != len(ctx) + 2:
            return ""
        tail = out[len(ctx) - 1][len(out[len(ctx) - 1].rstrip(_LIVE_MARKS)):]
        return tail if _ends_sentence(tail) else ""


class _LiveWorker(QThread):
    """Feeds the microphone into the live engine, off the UI thread. Each finished phrase goes to a
    second thread, where the accurate model listens to it again; the live words keep flowing
    meanwhile, and the phrases are typed in the order they were said."""
    partial = pyqtSignal(str, str)      # (mark for the word before, words heard so far in this phrase)
    pending = pyqtSignal(str)           # a finished phrase, as the live model heard it, being checked
    final = pyqtSignal(str, bool)       # text to type now; True for a phrase, False for the closing mark
    status = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, recheck: bool = True):
        super().__init__()
        import queue
        self._q = queue.Queue()
        self._rq = queue.Queue()
        self._recheck_on = recheck
        self._abort = False
        _LIVE_WORKERS.add(self)
        self.finished.connect(lambda: _LIVE_WORKERS.discard(self))

    def feed(self, samples, rate: int):
        self._q.put((samples, rate))

    def finish(self):
        self._q.put(None)

    def abort(self):
        """The app is quitting: no more listening again, no more typing."""
        self._abort = True
        self._q.put(None)

    def _recheck_loop(self, phrases):
        recheck_ok = self._recheck_on
        if recheck_ok:
            try:
                _LiveModels.load_recheck(self.status.emit)
            except Exception as e:
                logging.error(f"Live voice typing: the accurate model could not load, using the live one: {e}")
                recheck_ok = False
        while True:
            item = self._rq.get()
            if item is None or self._abort:
                if not self._abort:
                    end = phrases.ending()
                    if end:
                        self.final.emit(end, False)
                return
            pieces, raw = item
            text = None
            if recheck_ok:
                try:
                    text = phrases.take_heard(_LiveModels.recheck(pieces)) or None
                    if text is None:
                        logging.error(f"Live voice typing: the accurate model heard nothing in {raw!r}; "
                                      "typing the live words")
                except Exception as e:
                    logging.error(f"Live voice typing: listening again failed, typing the live words: {e}")
            if text is None:                   # never lose words the live model heard
                text = phrases.take(raw)
            if text and not self._abort:
                self.final.emit(text, True)

    def run(self):
        import numpy as np
        import queue
        try:
            asr, punct = _LiveModels.load(self.status.emit)
        except Exception as e:
            logging.error(f"Live voice typing: the engine could not start: {e}")
            self.failed.emit(str(e))
            return
        self.status.emit("")
        phrases = _LivePhrases(punct)
        second = threading.Thread(target=self._recheck_loop, args=(phrases,), daemon=True,
                                  name="otterly-voice-recheck")
        second.start()
        stream = asr.create_stream()
        shown = ""
        pieces = []                      # the sound of the phrase being spoken
        try:
            while True:
                # Take everything waiting at once: when the PC is busy and the engine falls behind,
                # it catches up in one go instead of redrawing every piece.
                items = [self._q.get()]
                while True:
                    try:
                        items.append(self._q.get_nowait())
                    except queue.Empty:
                        break
                stopping = False
                for it in items:
                    if it is None:          # Stop: what came before it is still taken
                        stopping = True
                        break
                    stream.accept_waveform(it[1], it[0])
                    pieces.append(it)
                if stopping:
                    if not self._abort:
                        # The last words: some quiet lets the engine finish them.
                        stream.accept_waveform(WHISPER_RATE, np.zeros(int(WHISPER_RATE * 1.0), dtype=np.float32))
                        stream.input_finished()
                        while asr.is_ready(stream):
                            asr.decode_stream(stream)
                        raw = asr.get_result(stream).strip()
                        if raw:
                            self.pending.emit(phrases.render(raw)[1])
                            self._rq.put((pieces, raw))
                    self._rq.put(None)
                    second.join(None if not self._abort else 3.0)
                    return
                while asr.is_ready(stream):
                    asr.decode_stream(stream)
                raw = asr.get_result(stream).strip()
                if asr.is_endpoint(stream):
                    if raw:
                        self.pending.emit(phrases.render(raw)[1])
                        self._rq.put((pieces, raw))
                    pieces = []
                    asr.reset(stream)
                    shown = ""
                    self.partial.emit("", "")
                elif raw != shown:
                    shown = raw
                    mark, text = phrases.render(raw)
                    self.partial.emit(mark, text)
        except Exception as e:
            logging.error(f"Live voice typing: the engine stopped: {e}")
            self.failed.emit(str(e))
            self._rq.put(None)


# ── typing into whatever window has the cursor ──────────────────────────────

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_MODIFIER_KEYS = (0x10, 0x11, 0x12, 0x5B, 0x5C)     # Shift, Ctrl, Alt, both Windows keys


def _unicode_inputs(text: str):
    """Key presses that type `text` as characters, whatever the keyboard layout."""
    units = text.encode("utf-16-le")
    codes = [int.from_bytes(units[i:i + 2], "little") for i in range(0, len(units), 2)]
    arr = (_INPUT * (2 * len(codes)))()
    for i, c in enumerate(codes):
        for j, flags in enumerate((_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP)):
            arr[2 * i + j].type = 1     # INPUT_KEYBOARD
            arr[2 * i + j].u.ki = _KEYBDINPUT(0, c, flags, 0, 0)
    return arr


def _modifiers_down() -> bool:
    try:
        return any(ctypes.windll.user32.GetAsyncKeyState(k) & 0x8000 for k in _MODIFIER_KEYS)
    except Exception:
        return False


def _send_text(text: str) -> bool:
    """Type the text into the window that has the keyboard."""
    if not text:
        return True
    arr = _unicode_inputs(text)
    sent = ctypes.windll.user32.SendInput(len(arr), arr, ctypes.sizeof(_INPUT))
    return sent == len(arr)


def _text_cursor_point():
    """Where the text cursor is on screen (Qt coordinates), or the mouse if the window keeps it to
    itself, as browsers do."""
    try:
        class _RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class _GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                        ("hwndActive", ctypes.c_void_p), ("hwndFocus", ctypes.c_void_p),
                        ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
                        ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p),
                        ("rcCaret", _RECT)]

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        tid = u.GetWindowThreadProcessId(u.GetForegroundWindow(), None)
        gti = _GUITHREADINFO()
        gti.cbSize = ctypes.sizeof(_GUITHREADINFO)
        if tid and u.GetGUIThreadInfo(tid, ctypes.byref(gti)) and gti.hwndCaret:
            pt = _POINT(gti.rcCaret.left, gti.rcCaret.bottom)
            if u.ClientToScreen(gti.hwndCaret, ctypes.byref(pt)) and (pt.x or pt.y):
                scr = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
                g, dpr = scr.geometry(), scr.devicePixelRatio() or 1.0
                return QPoint(int(g.x() + (pt.x - g.x()) / dpr), int(g.y() + (pt.y - g.y()) / dpr))
    except Exception:
        pass
    return QCursor.pos()


class LiveTypingStrip(QWidget):
    """The small bar that shows what is heard. It never takes the keyboard, so the words go to
    the text box you were typing in."""
    stop_clicked = pyqtSignal()
    TAIL_CHARS = 90

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Voice typing")
        self.setFixedWidth(560)
        self._typed = ""
        self._checking: list = []        # finished phrases being listened to again
        self._live = ""
        self._level = 0.0

        box = QFrame(self)
        box.setObjectName("liveBox")
        box.setStyleSheet(
            "#liveBox { background: rgba(24,26,32,235); border: 1px solid #3a3f4b; border-radius: 10px; }"
            "QLabel { color: #e8eaf0; background: transparent; }"
            "QPushButton { color: #e8eaf0; background: #3a3f4b; border: none; border-radius: 6px;"
            " padding: 3px 10px; font-size: 9pt; } QPushButton:hover { background: #c0392b; }")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 8, 8, 8)
        lay.setSpacing(10)
        self.dot = QLabel()
        self.dot.setFixedSize(14, 14)
        lay.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.text_lbl = QLabel()
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.text_lbl.setStyleSheet("font-size: 11pt;")
        self.text_lbl.setMinimumHeight(22)
        col.addWidget(self.text_lbl)
        self.hint = QLabel(f"Listening — pause and it types  ·  {LIVE_HOTKEY_LABEL} stops")
        self.hint.setStyleSheet("color: #8a90a0; font-size: 8pt;")
        col.addWidget(self.hint)
        lay.addLayout(col, 1)
        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        lay.addWidget(self.stop_btn, 0, Qt.AlignmentFlag.AlignTop)
        self.set_level(0.0)
        self.set_status("Listening…")

    def set_level(self, v: float):
        self._level = v
        a = int(110 + 145 * min(1.0, v * 1.5))
        self.dot.setStyleSheet(f"background: rgba(231,76,60,{a}); border-radius: 7px;")

    def set_status(self, text: str):
        """A grey line in place of the words (getting ready, downloading, finishing)."""
        import html
        self.text_lbl.setText(f"<span style='color:#8a90a0'>{html.escape(text)}</span>")
        self.adjustSize()

    def _show(self, live=None):
        import html
        if live is not None:
            self._live = live
        live = self._live
        tail = self._typed[-self.TAIL_CHARS:]
        if len(self._typed) > self.TAIL_CHARS:
            tail = "…" + tail[tail.find(" ") + 1:] if " " in tail else "…" + tail
        parts = []
        if tail:
            parts.append(f"<span style='color:#9aa3b5'>{html.escape(tail)}</span>")
        for c in self._checking:
            gap = " " if parts else ""
            parts.append(f"<span style='color:#c8ccd6'><i>{html.escape(gap + c)}</i></span>")
        if live:
            if self._checking and not live.startswith(" "):
                live = " " + live
            parts.append(f"<span style='color:#ffffff'>{html.escape(live)}</span>")
        self.text_lbl.setText("".join(parts) if parts else
                              "<span style='color:#8a90a0'>Listening…</span>")
        self.adjustSize()

    def set_partial(self, mark: str, words: str):
        lead = mark + (" " if self._typed and words else "")
        self._show(lead + words if words else "")

    def add_checking(self, text: str):
        """A finished phrase, as heard live, while the accurate model listens to it again."""
        if text:
            self._checking.append(text)
            self._show("")

    def add_typed(self, text: str, phrase: bool = True):
        self._typed += text
        if phrase and self._checking:
            self._checking.pop(0)
        self._show()

    def place_near(self, pt: QPoint):
        """Just under the text cursor; above it where there is no room below."""
        scr = QApplication.screenAt(pt) or QApplication.primaryScreen()
        g = scr.availableGeometry()
        self.adjustSize()
        w, h = self.width(), max(self.height(), 56)
        x = min(max(g.left() + 8, pt.x() - 40), g.right() - w - 8)
        y = pt.y() + 18
        if y + h > g.bottom() - 8:
            y = pt.y() - h - 30
        self.move(x, max(g.top() + 8, y))


class LiveVoiceTyping(QObject):
    """Ctrl+Shift+Space: listen, show the words live, type each phrase where the cursor is."""
    stopped = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.strip = None
        self.worker = None
        self.rec = None
        self._pending: list = []         # text waiting for Shift/Ctrl/Alt to be let go
        self._waited = 0.0
        self._last_heard = 0.0
        self._stopping = False
        self._failed = False
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(40)
        self._type_timer.timeout.connect(self._flush)
        # The models take about 0.9 GB: let them go after a while without voice typing.
        self._free_timer = QTimer(self)
        self._free_timer.setSingleShot(True)
        self._free_timer.timeout.connect(self._free_models)

    @property
    def active(self) -> bool:
        return self.worker is not None

    def toggle(self):
        if self.active:
            self.stop()
        else:
            self.start()

    def start(self):
        if self.active:
            return
        self._stopping = False
        self._failed = False
        self._pending = []
        self._free_timer.stop()
        if self.strip is not None:          # the last session's strip, still fading out
            self.strip.close()
            self.strip.deleteLater()
        self.strip = LiveTypingStrip()
        self.strip.stop_clicked.connect(self.stop)
        self.strip.place_near(_text_cursor_point())
        self.worker = _LiveWorker()
        self.worker.partial.connect(self._on_partial)
        self.worker.pending.connect(self._on_checking)
        self.worker.final.connect(self._on_final)
        self.worker.status.connect(self._on_status)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_done)
        self.rec = _MicRecorder(on_chunk=self.worker.feed)
        err = self.rec.start()
        if err:
            self.rec = None
            self.worker = None
            self.strip.set_status(f"Voice typing: {err}")
            self.strip.hint.setText("")
            self.strip.show()
            QTimer.singleShot(4000, self._close_strip)
            return
        self.worker.start()
        if not _LiveModels.ready():
            self.strip.set_status("Getting ready…")
        self.strip.show()
        self._last_heard = time.monotonic()
        self._timer.start()

    def stop(self):
        if not self.active or self._stopping:
            return
        self._stopping = True
        self._timer.stop()
        if self.rec is not None:
            self.rec.stop()
            self.rec = None
        if self.strip:
            self.strip.hint.setText("Finishing the last words…")
            self.strip.set_level(0.0)
        self.worker.finish()

    def _tick(self):
        if self.rec is not None and self.strip:
            self.strip.set_level(self.rec.level)
        if time.monotonic() - self._last_heard > LIVE_QUIET_STOP:
            self.stop()

    def _on_status(self, text: str):
        self._last_heard = time.monotonic()     # getting ready or downloading is not silence
        if self.strip:
            if text:
                self.strip.set_status(text)
            else:
                self.strip.set_partial("", "")

    def _on_partial(self, mark: str, words: str):
        if words:
            self._last_heard = time.monotonic()
        if self.strip:
            self.strip.set_partial(mark, words)

    def _on_checking(self, text: str):
        self._last_heard = time.monotonic()
        if self.strip:
            self.strip.add_checking(text)

    def _on_final(self, text: str, phrase: bool = True):
        self._last_heard = time.monotonic()
        self._pending.append(text)
        if self.strip:
            self.strip.add_typed(text, phrase)
        self._flush()

    def _flush(self):
        """Type what is waiting, once no Shift/Ctrl/Alt/Windows key is held (they would turn
        letters into shortcuts). Held for over 3 s: type anyway."""
        if not self._pending:
            self._type_timer.stop()
            return
        if _modifiers_down() and self._waited < 3.0:
            self._waited += 0.04
            if not self._type_timer.isActive():
                self._type_timer.start()
            return
        self._waited = 0.0
        self._type_timer.stop()
        text, self._pending = "".join(self._pending), []
        try:
            if not _send_text(text):
                logging.error("Live voice typing: Windows did not take all the typed text")
        except Exception as e:
            logging.error(f"Live voice typing: typing failed: {e}")

    def _on_failed(self, msg: str):
        if self.strip:
            self.strip.set_status(f"Voice typing could not start: {msg[:120]}")
        if self.rec is not None:
            self.rec.stop()
            self.rec = None
        self._timer.stop()
        self._stopping = True
        self._failed = True

    def _on_worker_done(self):
        self._flush()
        self.worker = None
        self._timer.stop()
        QTimer.singleShot(6000 if self._failed else (1200 if not self._pending else 3200), self._close_strip)
        self._free_timer.start(int(LIVE_FREE_AFTER * 1000))
        self.stopped.emit()

    def _free_models(self):
        if not self.active:
            _LiveModels.unload()

    def shutdown(self):
        """The app is quitting: stop listening, type nothing more, let the engine thread end."""
        self._timer.stop()
        self._type_timer.stop()
        self._pending = []
        if self.rec is not None:
            self.rec.stop()
            self.rec = None
        self._free_timer.stop()
        w = self.worker
        if w is not None:
            try:
                w.final.disconnect()
            except Exception:
                pass
            w.abort()
            w.wait(3000)
        self._close_strip_now()

    def _close_strip_now(self):
        if self.strip:
            self.strip.close()
            self.strip.deleteLater()
            self.strip = None

    def _close_strip(self):
        if self.worker is not None:      # a new session already started with this strip gone
            return
        if self.strip:
            self.strip.close()
            self.strip.deleteLater()
            self.strip = None


# ============================================================================
# SCREENSHOT EDITOR
# ============================================================================

class ScreenshotEditor(QMainWindow):
    """Screenshot annotation editor — highlight, pen, arrow, circle, rect, blur, text, undo"""

    editing_complete = pyqtSignal(QPixmap)
    editing_cancelled = pyqtSignal()

    COLORS = {
        'yellow': QColor(255, 220, 0, 160),
        'green':  QColor(0, 210, 80, 160),
        'blue':   QColor(30, 144, 255, 200),
        'red':    QColor(220, 40, 40, 200),
        'white':  QColor(255, 255, 255, 230),
    }

    # How a voice note is laid out: wrapped at word breaks, never clipped
    NOTE_FLAGS = (Qt.TextFlag.TextWordWrap.value | Qt.TextFlag.TextDontClip.value |
                  Qt.AlignmentFlag.AlignLeft.value | Qt.AlignmentFlag.AlignTop.value)
    NOTE_LINE_CHARS = 64     # a note's box is this many characters wide: 255 fit in 4 lines
    NOTE_PAD = 8             # plate margin round a note's text
    NOTE_PLATE = QColor(20, 20, 20, 200)   # the measurement labels' dark plate

    def __init__(self, pixmap: QPixmap):
        super().__init__()

        self.original_pixmap = pixmap
        self.current_color = self.COLORS['yellow']
        self.color_name = 'yellow'
        self.brush_size = 20
        # modes: highlight, pen, arrow, circle, rect, blur, text
        self.draw_mode = 'highlight'
        self.drawing = False
        self.start_point = None   # fixed anchor for shapes / straight line
        self.last_point = None

        # Committed annotations live here
        self.overlay_pixmap = QPixmap(pixmap.size())
        self.overlay_pixmap.fill(Qt.GlobalColor.transparent)

        # Live-preview layer (cleared on every mouse-move for shape tools)
        self.preview_pixmap = QPixmap(pixmap.size())
        self.preview_pixmap.fill(Qt.GlobalColor.transparent)

        # Per-stroke highlight layer — redrawn from scratch each move,
        # merged to overlay on mouseup.  Prevents alpha stacking mid-stroke.
        self.stroke_pixmap = QPixmap(pixmap.size())
        self.stroke_pixmap.fill(Qt.GlobalColor.transparent)
        self._stroke_points: list = []   # accumulated points for current highlight stroke
        self._pen_points: list = []      # points of the current pen stroke
        self._straight_marker = False     # lock highlight to horizontal

        # Every annotation is kept as an object (a dict) so it can be picked up and
        # moved later; overlay_pixmap is rendered from this list, oldest first.
        self._objects: list = []
        self._selected = None            # the object picked by the move tool / Ctrl+drag
        self._drag = None                # state while an object is being dragged
        self._above_pixmap = None        # objects stacked above the dragged one
        self._mode_cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._hover_grab = False

        # Undo stack — list of object-list snapshots
        self._undo_stack: list = []

        self._setup_ui()

    def _setup_ui(self):
        # Override the app-level QSS cascade so :hover colours work correctly
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f0f0f0; color: #222222; }
        """)

        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Otterly — Edit Screenshot")
        img_size = self.original_pixmap.size()
        screen = QApplication.primaryScreen().geometry()
        toolbar_h = 100
        max_w = screen.width() - 80
        max_h = screen.height() - 120
        scale = min(1.0, max_w / img_size.width(), (max_h - toolbar_h) / img_size.height())
        self.display_size = QSize(int(img_size.width() * scale), int(img_size.height() * scale))
        self.scale_factor = scale

        window_w = min(max(900, self.display_size.width() + 20), max_w)
        window_h = min(max(200, self.display_size.height() + toolbar_h), max_h)
        self.setFixedSize(window_w, window_h)
        self.move((screen.width() - window_w) // 2, (screen.height() - window_h) // 2)

        container = QWidget()
        # Editor always uses a fixed light theme — independent of app theme
        container.setStyleSheet("background: #f0f0f0;")
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setStyleSheet("background: #e0e0e0; border-radius: 6px;")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 6, 8, 6)
        tb.setSpacing(6)

        # Color swatches
        # ── colour picker dropdown ────────────────────────────────────────────
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(44, 44)
        self._color_btn.setToolTip("Colour  (click to pick)")
        self._color_btn.setStyleSheet(
            "QPushButton{border:2px solid #888;border-radius:6px;background:#ffdc00;}"
            "QPushButton:hover{border-color:#2AA198;}")
        self._color_btn.clicked.connect(self._show_color_menu)
        tb.addWidget(self._color_btn)

        tb.addWidget(self._vsep())

        # ── tool icon buttons ─────────────────────────────────────────────────
        SZ = 44   # icon button size
        icon_style = """
            QPushButton {
                background: #e8e8e8; border: 1px solid #bbbbbb;
                border-radius: 6px; padding: 0px;
            }
            QPushButton:hover  { background: #d0d0d0; border-color: #888888; }
            QPushButton:checked {
                background: #2AA198; border: 2px solid #1d8a82;
            }
            QPushButton:checked:hover { background: #1d8a82; }
        """

        def _icon_btn(icon_pixmap, tooltip, mode=None, checkable=True):
            b = QPushButton()
            b.setFixedSize(SZ, SZ)
            b.setCheckable(checkable)
            b.setIcon(QIcon(icon_pixmap))
            b.setIconSize(QSize(SZ - 10, SZ - 10))
            b.setToolTip(tooltip)
            b.setStyleSheet(icon_style)
            return b

        tools_def = [
            ('move',         self._make_icon_move(),          '✥ Move  [V]  — drag anything you drew; Del removes it.  '
                                                              'Ctrl+drag moves in any tool'),
            ('highlight',    self._make_icon_highlight(),     '🖌 Marker  [H]'),
            ('pen',          self._make_icon_pen(),           '✏ Pen  [P]'),
            ('line',         self._make_icon_line(),          '╱ Straight line  [L]'),
            ('arrow',        self._make_icon_arrow(),         '➜ Arrow  [A]'),
            ('rect',         self._make_icon_rect(),          '▭ Rectangle  [R]'),
            ('circle',       self._make_icon_circle(),        '◯ Circle  [C]'),
            ('blur',         self._make_icon_blur(),          '⬛ Blur / redact  [B]'),
            ('text',         self._make_icon_text(),          'T Text  [T]'),
            ('measure_line', self._make_icon_measure_line(),  '📏 Measure line  [M]'),
            ('measure_rect', self._make_icon_measure_rect(),  '📐 Measure rect  [shift+M]'),
        ]
        self._tool_btns = {}
        for mode, icon_px, tip in tools_def:
            btn = _icon_btn(icon_px, tip)
            btn.clicked.connect(lambda chk, m=mode: self._set_mode(m))
            tb.addWidget(btn)
            self._tool_btns[mode] = btn
            if mode == 'text':
                # Voice note: an action, not a tool — opens a box to speak or type into
                self._mic_btn = _icon_btn(self._make_icon_mic(),
                                          '🎤 Voice note — speak or type a note, then drag it into place',
                                          checkable=False)
                self._mic_btn.clicked.connect(self._voice_note)
                tb.addWidget(self._mic_btn)
        self._tool_btns['highlight'].setChecked(True)

        # Aspect ratio lock for measure_rect (right-click the button for menu)
        self._measure_aspect = 'free'   # 'free' or 'W:H' string e.g. '16:9'
        self._aspect_ratios = [
            ('Free',  'free'),
            ('16:9',  '16:9'),
            ('4:3',   '4:3'),
            ('1:1',   '1:1'),
            ('3:2',   '3:2'),
            ('21:9',  '21:9'),
            ('9:16',  '9:16'),
            ('2:3',   '2:3'),
        ]
        mr_btn = self._tool_btns['measure_rect']
        mr_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        mr_btn.customContextMenuRequested.connect(self._show_aspect_menu)
        # Also left-click cycles through presets
        mr_btn.clicked.connect(self._show_aspect_menu_on_click)

        # Straight-line lock (also Shift key)
        self._straight_btn = _icon_btn(
            self._make_icon_straight(),
            '⇔ Straight marker  [Shift while dragging]')
        self._straight_btn.toggled.connect(lambda v: setattr(self, '_straight_marker', v))
        tb.addWidget(self._straight_btn)

        # Measure stamp toggle — when ON, measurements are committed to the image
        self._measure_stamp = False
        self._stamp_btn = _icon_btn(
            self._make_icon_stamp(),
            '📌 Stamp measurements onto image  (when off, measurements vanish on release)')
        self._stamp_btn.toggled.connect(lambda v: setattr(self, '_measure_stamp', v))
        tb.addWidget(self._stamp_btn)

        tb.addWidget(self._vsep())

        # ── size slider (bigger) ──────────────────────────────────────────────
        size_lbl = QLabel("Size")
        size_lbl.setStyleSheet("color:#444; background:transparent; font-size:9pt;")
        tb.addWidget(size_lbl)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(2, 60)
        self.size_slider.setValue(20)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setFixedHeight(22)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        tb.addWidget(self.size_slider)
        self.size_value = QLabel("20")
        self.size_value.setFixedWidth(28)
        self.size_value.setStyleSheet("color:#222; background:transparent; font-size:10pt;")
        tb.addWidget(self.size_value)

        tb.addWidget(self._vsep())

        # ── undo / cancel / save icon buttons ────────────────────────────────
        undo_btn = _icon_btn(self._make_icon_undo(), '↩ Undo  [Ctrl+Z]', checkable=False)
        undo_btn.clicked.connect(self._undo)
        tb.addWidget(undo_btn)

        tb.addStretch()

        cancel_btn = _icon_btn(self._make_icon_cancel(), '✕ Cancel  [Esc]', checkable=False)
        cancel_btn.setStyleSheet(
            "QPushButton{background:#DC322F;border:none;border-radius:6px;padding:0px;}"
            "QPushButton:hover{background:#e85552;}"
            "QPushButton:pressed{background:#b52724;}")
        cancel_btn.clicked.connect(self._cancel)
        tb.addWidget(cancel_btn)

        save_btn = _icon_btn(self._make_icon_save(), '✔ Save  [Enter]', checkable=False)
        save_btn.setStyleSheet(
            "QPushButton{background:#2AA198;border:none;border-radius:6px;padding:0px;}"
            "QPushButton:hover{background:#33c4bb;}"
            "QPushButton:pressed{background:#1d8a82;}")
        save_btn.clicked.connect(self._save)
        tb.addWidget(save_btn)

        layout.addWidget(toolbar)

        # ── Canvas ───────────────────────────────────────────────────────────
        self.canvas = QLabel()
        self.canvas.setFixedSize(self.display_size)
        self.canvas.setStyleSheet(f"background:white; border:1px solid {Theme.BORDER};")
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.canvas.setMouseTracking(True)
        self.canvas.installEventFilter(self)
        layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)

        self._update_canvas()
        self._set_color(self.COLORS['yellow'], 'yellow')

    # ── helpers ──────────────────────────────────────────────────────────────

    def _vsep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet(f"color:{Theme.BORDER}; margin:4px 2px;")
        return f

    def _swatch_style(self, name: str, selected: bool) -> str:
        c = self.COLORS[name]
        opaque = QColor(c.red(), c.green(), c.blue()).name()
        border = Theme.ACCENT if selected else Theme.TEXT_DARK
        width = '3px' if selected else '2px'
        return (f"QPushButton{{background:{opaque};border:{width} solid {border};"
                f"border-radius:4px;}} QPushButton:hover{{border-width:3px;}}")

    def _show_color_menu(self):
        """Pop up a small colour-picker panel near the colour button."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#f0f0f0; border:1px solid #aaa; padding:6px; }
            QMenu::item { padding:0px; margin:2px; background:transparent; }
            QMenu::item:selected { background:transparent; }
        """)
        row = QWidgetAction(menu)
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(4, 4, 4, 4)
        hl.setSpacing(6)
        for name, color in self.COLORS.items():
            opaque = QColor(color.red(), color.green(), color.blue())
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setToolTip(name.capitalize())
            btn.setStyleSheet(
                f"QPushButton{{background:{opaque.name()};border:2px solid #888;"
                f"border-radius:5px;}}"
                f"QPushButton:hover{{border-color:#2AA198;border-width:3px;}}")
            btn.clicked.connect(lambda chk, c=color, n=name: (
                self._set_color(c, n), menu.close()))
            hl.addWidget(btn)
        row.setDefaultWidget(w)
        menu.addAction(row)
        menu.exec(self._color_btn.mapToGlobal(
            self._color_btn.rect().bottomLeft()))

    def _set_color(self, color: QColor, name: str):
        self.current_color = color
        self.color_name = name
        # Update the colour swatch button
        opaque = QColor(color.red(), color.green(), color.blue())
        self._color_btn.setStyleSheet(
            f"QPushButton{{background:{opaque.name()};border:2px solid #2AA198;"
            f"border-radius:6px;}}"
            f"QPushButton:hover{{border-color:#33c4bb;}}")

    # ── icon drawing helpers ─────────────────────────────────────────────────

    @staticmethod
    def _blank_icon(size=34) -> tuple:
        """Return (QPixmap, QPainter) ready to draw on. Caller must call p.end()."""
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        return px, p

    @staticmethod
    def _make_icon_mic():
        px, p = ScreenshotEditor._blank_icon()
        col = QColor(40, 40, 40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(12, 2, 10, 18), 5, 5)            # capsule
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(QRectF(7.5, 7, 19, 17), 180 * 16, 180 * 16)     # cradle
        p.drawLine(QPoint(17, 24), QPoint(17, 30))
        p.drawLine(QPoint(11, 31), QPoint(23, 31))
        p.end(); return px

    def _make_icon_move(self):
        px, p = self._blank_icon()
        col = QColor(40, 40, 40)
        p.setPen(QPen(col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPoint(17, 5), QPoint(17, 29))
        p.drawLine(QPoint(5, 17), QPoint(29, 17))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        for tip, a, b in (((17, 2), (12, 8), (22, 8)), ((17, 32), (12, 26), (22, 26)),
                          ((2, 17), (8, 12), (8, 22)), ((32, 17), (26, 12), (26, 22))):
            p.drawPolygon(QPolygon([QPoint(*tip), QPoint(*a), QPoint(*b)]))
        p.end(); return px

    def _make_icon_highlight(self):
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'highlight_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        # Fallback
        px, p = self._blank_icon()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 220, 0, 160))
        p.drawRoundedRect(2, 12, 30, 10, 4, 4)
        p.setBrush(QColor(60, 60, 60))
        p.drawPolygon(QPolygon([QPoint(4, 10), QPoint(10, 10),
                                QPoint(10, 14), QPoint(4, 14)]))
        p.end(); return px

    def _make_icon_pen(self):
        # Use our custom pen SVG asset
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'pen_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        # Fallback to drawn icon
        px, p = self._blank_icon()
        pen = QPen(QColor(40, 40, 40), 2.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(6, 28), QPoint(26, 6))
        p.setBrush(QColor(40, 40, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygon([QPoint(4, 30), QPoint(8, 26), QPoint(10, 30)]))
        p.end(); return px

    def _make_icon_line(self):
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'line_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        # Fallback
        px, p = self._blank_icon()
        pen = QPen(QColor(40, 40, 40), 2.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(4, 28), QPoint(30, 6))
        p.end(); return px

    def _make_icon_arrow(self):
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'arrow_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        # Fallback
        import math
        px, p = self._blank_icon()
        pen = QPen(QColor(40, 40, 40), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(5, 28), QPoint(27, 6))
        p.setBrush(QColor(40, 40, 40))
        p.setPen(Qt.PenStyle.NoPen)
        angle = math.atan2(6 - 28, 27 - 5)
        hd = 9; sp = math.pi / 6
        pts = [QPoint(27, 6),
               QPoint(int(27 - hd * math.cos(angle - sp)), int(6 - hd * math.sin(angle - sp))),
               QPoint(int(27 - hd * math.cos(angle + sp)), int(6 - hd * math.sin(angle + sp)))]
        p.drawPolygon(QPolygon(pts))
        p.end(); return px

    def _make_icon_rect(self):
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'rect_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        px, p = self._blank_icon()
        p.setPen(QPen(QColor(40, 40, 40), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(4, 6, 26, 22, 2, 2)
        p.end(); return px

    def _make_icon_circle(self):
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'circle_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        px, p = self._blank_icon()
        p.setPen(QPen(QColor(40, 40, 40), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPoint(17, 17), 12, 11)
        p.end(); return px

    def _make_icon_blur(self):
        import os
        png_path = os.path.join(os.path.dirname(__file__), 'assets', 'blur_tool_32.png')
        if os.path.exists(png_path):
            return QPixmap(png_path)
        # Fallback
        px, p = self._blank_icon()
        cols = [(80,80,80),(160,160,160),(100,100,100),
                (200,200,200),(120,120,120),(180,180,180),
                (90,90,90),(150,150,150),(110,110,110)]
        p.setPen(Qt.PenStyle.NoPen)
        for i, (r, g, b) in enumerate(cols):
            row, col = divmod(i, 3)
            p.setBrush(QColor(r, g, b))
            p.drawRect(5 + col*8, 5 + row*8, 7, 7)
        p.end(); return px

    def _make_icon_text(self):
        px, p = self._blank_icon()
        p.setPen(QColor(230, 126, 34))   # orange #e67e22
        font = QFont("Georgia", 20, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRect(0, 0, 34, 34),
                   Qt.AlignmentFlag.AlignCenter, "T")
        p.end(); return px

    def _make_icon_straight(self):
        px, p = self._blank_icon()
        # Double-headed arrow (horizontal)
        pen = QPen(QColor(40, 40, 40), 2.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(4, 17), QPoint(30, 17))
        p.setBrush(QColor(40, 40, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygon([QPoint(4, 17), QPoint(10, 13), QPoint(10, 21)]))
        p.drawPolygon(QPolygon([QPoint(30, 17), QPoint(24, 13), QPoint(24, 21)]))
        p.end(); return px

    def _make_icon_measure_line(self):
        px, p = self._blank_icon()
        # Orange diagonal line with tick marks at each end
        pen = QPen(QColor(230, 126, 34), 2.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(6, 28), QPoint(28, 6))
        # end ticks
        p.drawLine(QPoint(4, 26), QPoint(9, 31))
        p.drawLine(QPoint(26, 4), QPoint(31, 9))
        p.end(); return px

    def _make_icon_measure_rect(self):
        px, p = self._blank_icon()
        # Orange dashed rectangle
        pen = QPen(QColor(230, 126, 34), 2.0, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(4, 8, 26, 18)
        # small arrows on width/height
        p.setPen(QPen(QColor(230, 126, 34), 1.5))
        p.drawLine(QPoint(17, 26), QPoint(17, 30))  # height arrow down
        p.drawLine(QPoint(30, 17), QPoint(34, 17))  # width arrow right
        p.end(); return px

    def _make_icon_stamp(self):
        px, p = self._blank_icon()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Pin head circle (orange)
        p.setBrush(QColor(230, 126, 34))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(17, 10), 7, 7)
        # Pin needle
        pen = QPen(QColor(180, 80, 10), 2.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(17, 17), QPoint(17, 28))
        # Small shadow dot at tip
        p.setBrush(QColor(100, 50, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(17, 29), 2, 2)
        p.end(); return px

    def _make_icon_undo(self):
        import os
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF
        svg_path = os.path.join(os.path.dirname(__file__), 'assets', 'undo_icon.svg')
        if os.path.exists(svg_path):
            px = QPixmap(32, 32)
            px.fill(Qt.GlobalColor.transparent)
            p2 = QPainter(px)
            p2.setRenderHint(QPainter.RenderHint.Antialiasing)
            QSvgRenderer(svg_path).render(p2, QRectF(0, 0, 32, 32))
            p2.end()
            return px
        # Fallback
        px, p = self._blank_icon()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.end(); return px

    def _make_icon_cancel(self):
        px, p = self._blank_icon()
        pen = QPen(QColor(255, 255, 255), 3, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPoint(9, 9), QPoint(25, 25))
        p.drawLine(QPoint(25, 9), QPoint(9, 25))
        p.end(); return px

    def _make_icon_save(self):
        px, p = self._blank_icon()
        # Checkmark
        pen = QPen(QColor(255, 255, 255), 3.5, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(QPolygon([QPoint(6, 17), QPoint(14, 25), QPoint(28, 9)]))
        p.end(); return px

    def _set_mode(self, mode: str):
        self.draw_mode = mode
        for m, btn in self._tool_btns.items():
            btn.setChecked(m == mode)
        # Update cursor
        if mode == 'highlight':
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'highlight_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 24, 28))
            else:
                self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'pen':
            # Use custom pen cursor if available
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'pen_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 24, 28))  # hotspot at nib tip
            else:
                self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'arrow':
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'arrow_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 24, 28))
            else:
                self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'line':
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'line_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 4, 14))
            else:
                self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'rect':
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'rect_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 5, 7))
            else:
                self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'circle':
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'circle_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 16, 5))
            else:
                self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == 'blur':
            import os
            cur_path = os.path.join(os.path.dirname(__file__), 'assets', 'blur_cursor.cur')
            if os.path.exists(cur_path):
                pm = QPixmap(cur_path)
                self.canvas.setCursor(QCursor(pm, 16, 16))
            else:
                self.canvas.setCursor(Qt.CursorShape.SizeAllCursor)
        elif mode == 'text':
            self.canvas.setCursor(Qt.CursorShape.IBeamCursor)
        elif mode == 'move':
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode in ('measure_line', 'measure_rect'):
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self._mode_cursor = self.canvas.cursor()
        self._hover_grab = False
        if mode != 'move' and self._selected is not None:
            self._selected = None
            self._update_canvas()

    def _on_size_changed(self, v: int):
        self.brush_size = v
        self.size_value.setText(str(v))

    def _push_undo(self, snap=None):
        """Snapshot the object list onto the undo stack (max 30 levels)."""
        self._undo_stack.append(snap if snap is not None
                                else [dict(o) for o in self._objects])
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def _undo(self):
        if self.drawing or self._drag:
            return
        if self._undo_stack:
            self._objects = self._undo_stack.pop()
            self._selected = None
            self.preview_pixmap.fill(Qt.GlobalColor.transparent)
            self.stroke_pixmap.fill(Qt.GlobalColor.transparent)
            self._render_overlay()
            self._update_canvas()

    def _update_canvas(self):
        result = QPixmap(self.original_pixmap.size())
        result.fill(Qt.GlobalColor.white)   # start opaque white, not undefined
        p = QPainter(result)
        p.drawPixmap(0, 0, self.original_pixmap)
        p.drawPixmap(0, 0, self.overlay_pixmap)
        p.drawPixmap(0, 0, self.stroke_pixmap)
        p.drawPixmap(0, 0, self.preview_pixmap)
        if self._above_pixmap is not None:
            p.drawPixmap(0, 0, self._above_pixmap)
        p.end()
        scaled = result.scaled(self.display_size,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        if self._selected is not None and not self.drawing:
            # Selection box: drawn at screen scale so it stays a crisp line; never saved.
            box = self._obj_bbox(self._selected)
            s = self.scale_factor
            r = QRectF(box.x() * s, box.y() * s,
                       box.width() * s, box.height() * s).adjusted(-3, -3, 3, 3)
            sp = QPainter(scaled)
            sp.setBrush(Qt.BrushStyle.NoBrush)
            sp.setPen(QPen(QColor(255, 255, 255, 230), 1.5))
            sp.drawRect(r)
            sp.setPen(QPen(QColor(42, 161, 152), 1.5, Qt.PenStyle.DashLine))
            sp.drawRect(r)
            sp.end()
        self.canvas.setPixmap(scaled)

    def _canvas_to_image_pos(self, pos: QPoint) -> QPoint:
        return QPoint(int(pos.x() / self.scale_factor),
                      int(pos.y() / self.scale_factor))

    # ── annotation objects ───────────────────────────────────────────────────

    def _render_objects(self, objs) -> QPixmap:
        px = QPixmap(self.original_pixmap.size())
        px.fill(Qt.GlobalColor.transparent)
        if objs:
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            for o in objs:
                self._paint_object(p, o)
            p.end()
        return px

    def _render_overlay(self):
        self.overlay_pixmap = self._render_objects(self._objects)

    def _text_font(self, size: int) -> QFont:
        font = QFont("Segoe UI", size)
        font.setBold(True)
        return font

    def _make_note(self, text: str, size: int) -> dict:
        """A voice note: text wrapped in a box NOTE_LINE_CHARS wide, centred on the picture."""
        c = self.current_color
        img = self.original_pixmap.size()
        p = QPainter(self.overlay_pixmap)
        p.setFont(self._text_font(size))
        fm = p.fontMetrics()
        width = max(120, min(fm.averageCharWidth() * self.NOTE_LINE_CHARS, img.width() - 40))
        box = fm.boundingRect(QRect(0, 0, width, 1_000_000), self.NOTE_FLAGS, text)
        p.end()
        pad = self.NOTE_PAD
        w, h = box.width() + 2 * pad, box.height() + 2 * pad
        plate = QRect(max(0, (img.width() - w) // 2), max(0, (img.height() - h) // 2), w, h)
        return {'kind': 'text', 'pos': plate.topLeft() + QPoint(pad, pad), 'text': text,
                'size': size, 'width': width, 'color': QColor(c.red(), c.green(), c.blue()),
                'bbox': plate}

    def _voice_note(self):
        """Open the voice note box; the note lands in the middle of the picture,
        selected, with the Move tool on, ready to be dragged into place."""
        if self.drawing or self._drag:
            return
        dlg = VoiceNoteDialog(self, size=VoiceNoteDialog.DEFAULT_SIZE)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        text = dlg.text().strip()
        if not text:
            return
        obj = self._make_note(text, dlg.size_value())
        self._add_object(obj)
        self._render_overlay()
        self._set_mode('move')
        self._selected = obj
        self._update_canvas()

    def _paint_object(self, p: QPainter, o: dict):
        """Paint one annotation at its current place (its stored geometry + dx/dy)."""
        k = o['kind']
        dx, dy = o.get('dx', 0), o.get('dy', 0)
        if k == 'blur':
            # A moved redaction box covers whatever is under it now.
            self._paint_mosaic(p, o['rect'].translated(dx, dy), o['tile'])
            return
        p.save()
        p.translate(dx, dy)
        if k == 'highlight':
            # Own layer, painted with Source so overlapping dabs keep one flat alpha.
            box = o['bbox']
            layer = QPixmap(box.size())
            layer.fill(Qt.GlobalColor.transparent)
            lp = QPainter(layer)
            lp.setRenderHint(QPainter.RenderHint.Antialiasing)
            lp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            lp.setPen(Qt.PenStyle.NoPen)
            lp.setBrush(o['color'])
            lp.translate(-box.left(), -box.top())
            r = o['r']
            for (x, y) in o['points']:
                lp.drawEllipse(QPoint(x, y), r, r)
            lp.end()
            p.drawPixmap(box.topLeft(), layer)
        elif k == 'pen':
            p.setPen(QPen(o['color'], o['width'], Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(QPolygon(o['points']))
        elif k == 'line':
            p.setPen(QPen(o['color'], o['width'], Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(o['a'], o['b'])
        elif k == 'arrow':
            self._draw_arrow(p, o['a'], o['b'], o['width'], o['color'])
        elif k in ('rect', 'circle'):
            p.setPen(QPen(o['color'], o['width']))
            p.setBrush(Qt.BrushStyle.NoBrush)
            if k == 'rect':
                p.drawRect(o['rect'])
            else:
                p.drawEllipse(o['rect'])
        elif k == 'text':
            p.setPen(o['color'])
            p.setFont(self._text_font(o['size']))
            if o.get('width'):      # a voice note: wrapped on a dark plate, pos = text top-left
                p.save()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self.NOTE_PLATE)
                p.drawRoundedRect(o['bbox'], 6, 6)
                p.restore()
                p.drawText(QRect(o['pos'], QSize(o['width'], o['bbox'].height())),
                           self.NOTE_FLAGS, o['text'])
            else:
                p.drawText(o['pos'], o['text'])
        elif k == 'measure_line':
            self._draw_measure_line_preview(p, o['a'], o['b'])
        elif k == 'measure_rect':
            self._draw_measure_rect_preview(p, o['a'], o['b'], o['aspect'])
        p.restore()

    def _shape_object(self, mode: str, a: QPoint, b: QPoint, modifiers):
        """The object a shape tool makes from a drag from a to b (None if nothing)."""
        pen_w = max(2, self.brush_size // 4)
        c = self.current_color
        opaque = QColor(c.red(), c.green(), c.blue())
        if mode in ('line', 'arrow'):
            if abs(b.x() - a.x()) + abs(b.y() - a.y()) < 2:
                return None
            return {'kind': mode, 'a': QPoint(a), 'b': QPoint(b),
                    'color': opaque, 'width': pen_w}
        if mode in ('rect', 'circle'):
            r = QRect(a, b).normalized()
            if r.width() < 3 and r.height() < 3:
                return None
            return {'kind': mode, 'rect': r, 'color': QColor(c), 'width': pen_w}
        if mode == 'blur':
            r = QRect(a, b).normalized()
            if r.width() <= 4 or r.height() <= 4:
                return None
            return {'kind': 'blur', 'rect': r, 'tile': max(4, self.brush_size // 3)}
        if mode == 'measure_line':
            return {'kind': 'measure_line', 'a': QPoint(a), 'b': QPoint(b)}
        if mode == 'measure_rect':
            shift = modifiers & Qt.KeyboardModifier.ShiftModifier
            end = self._snap_aspect(a, b) if (self._measure_aspect != 'free' or shift) else b
            return {'kind': 'measure_rect', 'a': QPoint(a), 'b': QPoint(end),
                    'aspect': self._measure_aspect}
        return None

    def _add_object(self, obj: dict):
        self._push_undo()
        obj.setdefault('dx', 0)
        obj.setdefault('dy', 0)
        self._objects.append(obj)

    def _obj_bbox(self, o: dict) -> QRect:
        """Bounding box of an object where it sits now."""
        k = o['kind']
        if k in ('highlight', 'text'):
            box = QRect(o['bbox'])
        elif k == 'pen':
            w = o['width']
            box = QPolygon(o['points']).boundingRect().adjusted(-w, -w, w, w)
        elif k in ('line', 'arrow'):
            m = max(12, o['width'] * 4) if k == 'arrow' else o['width']
            box = QRect(o['a'], o['b']).normalized().adjusted(-m, -m, m, m)
        elif k in ('rect', 'circle'):
            w = o['width']
            box = o['rect'].adjusted(-w, -w, w, w)
        elif k == 'blur':
            box = QRect(o['rect'])
        elif k == 'measure_line':
            a, b = o['a'], o['b']
            mx, my = (a.x() + b.x()) // 2, (a.y() + b.y()) // 2
            box = QRect(a, b).normalized().adjusted(-8, -8, 8, 8).united(
                QRect(mx - 45, my - 28, 90, 28))
        else:   # measure_rect
            r = QRect(o['a'], o['b']).normalized()
            box = r.adjusted(-8, -28, 8, 28).united(
                QRect(r.center().x() - 90, r.top() - 28, 180, 1))
        return box.translated(o.get('dx', 0), o.get('dy', 0))

    @staticmethod
    def _seg_dist(px, py, ax, ay, bx, by) -> float:
        import math
        vx, vy = bx - ax, by - ay
        ll = vx * vx + vy * vy
        t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / ll))
        return math.hypot(px - (ax + t * vx), py - (ay + t * vy))

    def _hits_stroke(self, o: dict, x: int, y: int, tol: float) -> bool:
        """True if (x, y), in the object's own unmoved coordinates, is on its drawn line."""
        import math
        k = o['kind']
        if k == 'highlight':
            lim = (o['r'] + tol) ** 2
            return any((x - px) ** 2 + (y - py) ** 2 <= lim for (px, py) in o['points'])
        if k == 'pen':
            pts = o['points']
            lim = o['width'] / 2 + tol
            return any(self._seg_dist(x, y, a.x(), a.y(), b.x(), b.y()) <= lim
                       for a, b in zip(pts, pts[1:]))
        if k in ('line', 'arrow', 'measure_line'):
            a, b = o['a'], o['b']
            w = o.get('width', 2)
            if self._seg_dist(x, y, a.x(), a.y(), b.x(), b.y()) <= w / 2 + tol:
                return True
            # the arrowhead is wider than the shaft
            return k == 'arrow' and math.hypot(x - b.x(), y - b.y()) <= max(12, w * 4) + tol
        if k in ('rect', 'measure_rect'):
            r = o['rect'] if k == 'rect' else QRect(o['a'], o['b']).normalized()
            lim = o.get('width', 2) / 2 + tol
            near_x = r.left() - lim <= x <= r.right() + lim
            near_y = r.top() - lim <= y <= r.bottom() + lim
            return ((near_y and (abs(x - r.left()) <= lim or abs(x - r.right()) <= lim)) or
                    (near_x and (abs(y - r.top()) <= lim or abs(y - r.bottom()) <= lim)))
        if k == 'circle':
            r = o['rect']
            rx, ry = max(r.width() / 2, 1), max(r.height() / 2, 1)
            cx, cy = r.left() + r.width() / 2, r.top() + r.height() / 2
            d = math.hypot((x - cx) / rx, (y - cy) / ry)
            return abs(d - 1) * min(rx, ry) <= o['width'] / 2 + tol
        return False

    def _hits_area(self, o: dict, x: int, y: int) -> bool:
        """True if (x, y) is inside a filled area or a closed shape."""
        k = o['kind']
        if k in ('rect', 'blur'):
            return o['rect'].contains(x, y)
        if k == 'measure_rect':
            return QRect(o['a'], o['b']).normalized().contains(x, y)
        if k == 'text':
            return o['bbox'].adjusted(-4, -4, 4, 4).contains(x, y)
        if k == 'circle':
            r = o['rect']
            rx, ry = max(r.width() / 2, 1), max(r.height() / 2, 1)
            cx, cy = r.left() + r.width() / 2, r.top() + r.height() / 2
            return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
        return False

    def _hit_object(self, pos: QPoint):
        """The object under pos, top-most first. A line beats the inside of a shape,
        so an arrow drawn inside a rectangle can still be picked."""
        tol = max(3.0, 6 / self.scale_factor)
        for o in reversed(self._objects):
            x, y = pos.x() - o.get('dx', 0), pos.y() - o.get('dy', 0)
            if (self._obj_bbox(o).translated(-o.get('dx', 0), -o.get('dy', 0))
                    .adjusted(-int(tol), -int(tol), int(tol), int(tol)).contains(x, y)
                    and self._hits_stroke(o, x, y, tol)):
                return o
        for o in reversed(self._objects):
            if self._hits_area(o, pos.x() - o.get('dx', 0), pos.y() - o.get('dy', 0)):
                return o
        return None

    def _index_of(self, obj) -> int:
        return next(i for i, o in enumerate(self._objects) if o is obj)

    def _begin_drag(self, obj: dict, pos: QPoint):
        i = self._index_of(obj)
        self._drag = {'obj': obj, 'start': pos, 'dx': obj.get('dx', 0), 'dy': obj.get('dy', 0),
                      'snap': [dict(o) for o in self._objects], 'moved': False}
        # Render what sits below and above the dragged object once; each mouse move
        # then only repaints the object itself, in its own place in the stack.
        self.overlay_pixmap = self._render_objects(self._objects[:i])
        above = self._objects[i + 1:]
        self._above_pixmap = self._render_objects(above) if above else None
        self._render_dragged()
        self.canvas.setCursor(Qt.CursorShape.SizeAllCursor)

    def _render_dragged(self):
        self.preview_pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.preview_pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_object(p, self._drag['obj'])
        p.end()

    def _end_drag(self):
        d = self._drag
        self._drag = None
        if d['moved']:
            self._push_undo(d['snap'])
        self._above_pixmap = None
        self.preview_pixmap.fill(Qt.GlobalColor.transparent)
        self._render_overlay()
        self._update_canvas()

    def _delete_selected(self):
        if self._selected is None or self._drag or self.drawing:
            return
        self._push_undo()
        i = self._index_of(self._selected)
        del self._objects[i]
        self._selected = None
        self._hover_grab = False
        self.canvas.setCursor(self._mode_cursor)
        self._render_overlay()
        self._update_canvas()

    def _hover(self, pos: QPoint, ctrl: bool):
        """Show the move cursor over an object when it can be picked up."""
        grab = (self.draw_mode == 'move' or ctrl) and self._hit_object(pos) is not None
        if grab != self._hover_grab:
            self._hover_grab = grab
            self.canvas.setCursor(Qt.CursorShape.SizeAllCursor if grab else self._mode_cursor)

    # ── event filter ─────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj == self.canvas:
            t = event.type()
            if t == event.Type.MouseButtonPress:
                self._on_press(event); return True
            elif t == event.Type.MouseMove:
                self._on_move(event); return True
            elif t == event.Type.MouseButtonRelease:
                self._on_release(event); return True
        return super().eventFilter(obj, event)

    # ── drawing ──────────────────────────────────────────────────────────────

    def _on_press(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton or self._drag or self.drawing:
            return
        pos = self._canvas_to_image_pos(event.pos())
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # Move tool, or Ctrl held in any tool: pick up the object under the cursor.
        if self.draw_mode == 'move' or ctrl:
            hit = self._hit_object(pos)
            self._selected = hit
            if hit is not None:
                self._begin_drag(hit, pos)
            self._update_canvas()
            return

        if self._selected is not None:
            self._selected = None
            self._update_canvas()

        if self.draw_mode == 'text':
            text, ok = QInputDialog.getText(self, "Add Text", "Enter text:")
            if ok and text:
                c = self.current_color
                opaque = QColor(c.red(), c.green(), c.blue())
                font = self._text_font(self.brush_size)
                p = QPainter(self.overlay_pixmap)
                p.setFont(font)
                fm = p.fontMetrics()
                bbox = QRect(pos.x(), pos.y() - fm.ascent(),
                             fm.horizontalAdvance(text), fm.ascent() + fm.descent())
                p.end()
                self._add_object({'kind': 'text', 'pos': QPoint(pos), 'text': text,
                                  'color': opaque, 'size': self.brush_size, 'bbox': bbox})
                self._render_overlay()
                self._update_canvas()
            return

        self.drawing = True
        self.start_point = pos
        self.last_point = pos
        self._stroke_points = []   # reset point accumulator for new stroke
        self._pen_points = [QPoint(pos)]

    def _on_move(self, event: QMouseEvent):
        pos = self._canvas_to_image_pos(event.pos())
        if self._drag:
            # Keep the grab point on the picture so the object can always be picked up again.
            img = self.original_pixmap.size()
            pos = QPoint(min(max(pos.x(), 0), img.width() - 1),
                         min(max(pos.y(), 0), img.height() - 1))
            d = self._drag
            o = d['obj']
            nx = d['dx'] + pos.x() - d['start'].x()
            ny = d['dy'] + pos.y() - d['start'].y()
            if (nx, ny) != (o['dx'], o['dy']):
                o['dx'], o['dy'] = nx, ny
                d['moved'] = True
                self._render_dragged()
                self._update_canvas()
            return
        if not self.drawing:
            self._hover(pos, bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            return
        mode = self.draw_mode

        # ── freehand modes ──
        if mode in ('highlight', 'pen'):
            if mode == 'highlight':
                # Snap to horizontal if Straight is toggled or Shift held
                shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                if self._straight_marker or shift:
                    pos = QPoint(pos.x(), self.start_point.y())

                # Append new segment points to the stroke list
                x0, y0 = self.last_point.x(), self.last_point.y()
                x1, y1 = pos.x(), pos.y()
                steps = max(abs(x1-x0), abs(y1-y0), 1)
                for i in range(steps + 1):
                    t = i / steps
                    self._stroke_points.append((
                        int(x0 + (x1-x0)*t),
                        int(y0 + (y1-y0)*t)
                    ))

                # Redraw stroke_pixmap from scratch.
                # Use CompositionMode_Source so overlapping ellipses SET pixels
                # rather than blending — the whole stroke stays one flat alpha.
                self.stroke_pixmap.fill(Qt.GlobalColor.transparent)
                p = QPainter(self.stroke_pixmap)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setCompositionMode(
                    QPainter.CompositionMode.CompositionMode_Source)
                p.setPen(Qt.PenStyle.NoPen)
                hi = QColor(self.current_color.red(),
                            self.current_color.green(),
                            self.current_color.blue(), 130)
                p.setBrush(hi)
                r = self.brush_size // 2
                for (x, y) in self._stroke_points:
                    p.drawEllipse(QPoint(x, y), r, r)
                p.end()
            else:
                # pen — thin opaque line direct to overlay; the stroke becomes an
                # object on release
                p = QPainter(self.overlay_pixmap)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                opaque = QColor(self.current_color.red(),
                                self.current_color.green(),
                                self.current_color.blue())
                pen = QPen(opaque, max(1, self.brush_size // 4),
                           Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap,
                           Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.drawLine(self.last_point, pos)
                p.end()
                self._pen_points.append(QPoint(pos))
            self.last_point = pos
            self._update_canvas()
            return

        # ── shape preview modes: paint the object the release would make ──
        self.preview_pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.preview_pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        obj = self._shape_object(mode, self.start_point, pos, event.modifiers())
        if obj is not None:
            self._paint_object(p, obj)
        if mode == 'blur':
            # visible double border (black + white dashes) round the live mosaic
            r = QRect(self.start_point, pos).normalized()
            pen1 = QPen(QColor(0, 0, 0, 200), 2, Qt.PenStyle.SolidLine)
            pen2 = QPen(QColor(255, 255, 255, 230), 2, Qt.PenStyle.DashLine)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(pen1); p.drawRect(r)
            p.setPen(pen2); p.drawRect(r)
        p.end()
        self._update_canvas()

    def _on_release(self, event: QMouseEvent):
        if self._drag:
            self._end_drag()
            return
        if not self.drawing:
            return
        pos = self._canvas_to_image_pos(event.pos())
        mode = self.draw_mode
        obj = None

        if mode == 'highlight':
            pts = self._stroke_points
            if pts:
                r = self.brush_size // 2
                xs = [x for x, _ in pts]
                ys = [y for _, y in pts]
                c = self.current_color
                obj = {'kind': 'highlight', 'points': list(pts), 'r': r,
                       'color': QColor(c.red(), c.green(), c.blue(), 130),
                       'bbox': QRect(QPoint(min(xs) - r - 2, min(ys) - r - 2),
                                     QPoint(max(xs) + r + 2, max(ys) + r + 2))}
            self.stroke_pixmap.fill(Qt.GlobalColor.transparent)
            self._stroke_points = []
        elif mode == 'pen':
            if len(self._pen_points) >= 2:
                c = self.current_color
                obj = {'kind': 'pen', 'points': list(self._pen_points),
                       'color': QColor(c.red(), c.green(), c.blue()),
                       'width': max(1, self.brush_size // 4)}
            self._pen_points = []
        else:
            obj = self._shape_object(mode, self.start_point, pos, event.modifiers())
            if mode in ('measure_line', 'measure_rect') and not self._measure_stamp:
                obj = None   # measurements vanish on release unless stamped
            self.preview_pixmap.fill(Qt.GlobalColor.transparent)

        if obj is not None:
            self._add_object(obj)
        self.drawing = False
        self.start_point = None
        self.last_point = None
        self._render_overlay()
        self._update_canvas()

    # ── arrow helper ─────────────────────────────────────────────────────────

    def _draw_arrow(self, painter: QPainter, src: QPoint, dst: QPoint, pen_w: int,
                    color: QColor = None):
        import math
        c = color if color is not None else self.current_color
        opaque = QColor(c.red(), c.green(), c.blue())
        pen = QPen(opaque, pen_w, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(opaque))

        dx = dst.x() - src.x()
        dy = dst.y() - src.y()
        length = math.hypot(dx, dy)
        if length < 4:
            return

        # Shaft
        painter.drawLine(src, dst)

        # Arrowhead — equilateral triangle at dst
        head = max(12, pen_w * 4)
        angle = math.atan2(dy, dx)
        spread = math.pi / 6   # 30°
        ax1 = dst.x() - head * math.cos(angle - spread)
        ay1 = dst.y() - head * math.sin(angle - spread)
        ax2 = dst.x() - head * math.cos(angle + spread)
        ay2 = dst.y() - head * math.sin(angle + spread)

        tri = QPolygon([dst,
                        QPoint(int(ax1), int(ay1)),
                        QPoint(int(ax2), int(ay2))])
        painter.drawPolygon(tri)

    # ── blur helper ──────────────────────────────────────────────────────────

    def _paint_mosaic(self, painter: QPainter, rect: QRect, tile: int):
        """Paint a pixelated mosaic of the screenshot under rect into an open painter."""
        rect = rect.intersected(self.original_pixmap.rect())
        if rect.width() < 1 or rect.height() < 1:
            return
        region = self.original_pixmap.copy(rect)
        small = region.scaled(
            max(1, rect.width() // tile), max(1, rect.height() // tile),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation)
        mosaic = small.scaled(
            rect.width(), rect.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation)
        painter.drawPixmap(rect.topLeft(), mosaic)

    # ── measure helpers ──────────────────────────────────────────────────────

    # Common aspect ratios for Shift-snap (width:height)
    _ASPECT_RATIOS = [(16,9),(4,3),(1,1),(3,2),(21,9),(9,16),(2,3)]

    def _show_aspect_menu(self, pos=None):
        """Show aspect ratio dropdown on the measure_rect button."""
        from PyQt6.QtWidgets import QMenu
        btn = self._tool_btns['measure_rect']
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:#f0f0f0; border:1px solid #bbb; }
            QMenu::item { padding:5px 22px; color:#222; }
            QMenu::item:selected { background:#e67e22; color:white; }
            QMenu::item:checked { font-weight:bold; }
        """)
        for label, key in self._aspect_ratios:
            act = menu.addAction(('✓ ' if self._measure_aspect == key else '   ') + label)
            act.setData(key)
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen:
            self._measure_aspect = chosen.data()
            # Update tooltip to show current lock
            label = next(l for l, k in self._aspect_ratios if k == self._measure_aspect)
            self._tool_btns['measure_rect'].setToolTip(
                f'📐 Measure rect  [shift+M]  —  {label}')
        self._set_mode('measure_rect')

    def _show_aspect_menu_on_click(self):
        """Left-clicking measure_rect always shows the aspect menu too."""
        self._show_aspect_menu()

    def _snap_aspect(self, start: QPoint, end: QPoint) -> QPoint:
        """Snap end point to the locked aspect ratio (or nearest if free)."""
        w = abs(end.x() - start.x())
        h = abs(end.y() - start.y())
        if w < 4 or h < 4:
            return end

        # Determine target ratio
        if self._measure_aspect == 'free':
            # Snap to nearest common ratio
            current_ratio = w / h
            best = min(self._ASPECT_RATIOS, key=lambda r: abs(r[0]/r[1] - current_ratio))
            ar = best[0] / best[1]
        else:
            parts = self._measure_aspect.split(':')
            ar = int(parts[0]) / int(parts[1])

        # Constrain to fit within dragged area
        if w / ar >= h:
            new_h = int(w / ar)
            new_w = w
        else:
            new_w = int(h * ar)
            new_h = h
        dx = new_w if end.x() >= start.x() else -new_w
        dy = new_h if end.y() >= start.y() else -new_h
        return QPoint(start.x() + dx, start.y() + dy)

    def _measure_label_style(self, p: QPainter):
        """Set up painter for measurement text labels."""
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))

    def _draw_label_box(self, p: QPainter, text: str, cx: int, cy: int):
        """Draw a dark pill label with white text centred at cx,cy."""
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        pad_x, pad_y = 6, 3
        box = QRect(cx - tw//2 - pad_x, cy - th//2 - pad_y,
                    tw + pad_x*2, th + pad_y*2)
        # Dark semi-transparent background
        p.setBrush(QColor(20, 20, 20, 210))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(box, 4, 4)
        # White text
        p.setPen(QColor(255, 255, 255))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_measure_line_preview(self, p: QPainter, a: QPoint, b: QPoint):
        """Draw a measurement line with pixel length label."""
        # Orange line
        pen = QPen(QColor(230, 126, 34), 2, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(a, b)
        # End ticks (perpendicular to line)
        import math
        dx = b.x() - a.x(); dy = b.y() - a.y()
        length = math.hypot(dx, dy)
        if length < 2:
            return
        nx, ny = -dy/length, dx/length   # normal vector
        tick = 6
        for pt in (a, b):
            p.drawLine(
                QPoint(int(pt.x() + nx*tick), int(pt.y() + ny*tick)),
                QPoint(int(pt.x() - nx*tick), int(pt.y() - ny*tick)))
        # Pixel length label at midpoint
        px_len = int(length)
        self._measure_label_style(p)
        mx, my = (a.x()+b.x())//2, (a.y()+b.y())//2
        self._draw_label_box(p, f"{px_len} px", mx, my - 14)

    def _draw_measure_rect_preview(self, p: QPainter, a: QPoint, b: QPoint, aspect: str = None):
        """Draw a measurement rectangle with W×H, aspect ratio, and MP labels."""
        aspect = self._measure_aspect if aspect is None else aspect
        r = QRect(a, b).normalized()
        if r.width() < 2 or r.height() < 2:
            return
        w, h = r.width(), r.height()
        # Dashed orange border
        pen = QPen(QColor(230, 126, 34), 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)
        # Corner crosshairs
        p.setPen(QPen(QColor(230, 126, 34), 1.5))
        for cx, cy in [(r.left(), r.top()), (r.right(), r.top()),
                       (r.left(), r.bottom()), (r.right(), r.bottom())]:
            p.drawLine(cx-6, cy, cx+6, cy)
            p.drawLine(cx, cy-6, cx, cy+6)
        # Compute aspect ratio string
        import math
        g = math.gcd(w, h)
        ratio_w, ratio_h = w//g, h//g
        # If a ratio is locked, show that name; otherwise resolve from actual dimensions
        if aspect != 'free':
            ratio_str = '🔒 ' + aspect
        else:
            named = {(16,9):'16:9',(4,3):'4:3',(1,1):'1:1',(3,2):'3:2',
                     (21,9):'21:9',(9,16):'9:16',(2,3):'2:3'}
            ratio_str = named.get((ratio_w, ratio_h), f'{ratio_w}:{ratio_h}')
        mp = w * h / 1_000_000
        self._measure_label_style(p)
        # W×H label above top edge
        self._draw_label_box(p, f"{w} × {h} px", r.center().x(), r.top() - 14)
        # Aspect + MP label below bottom edge
        mp_str = f"{mp:.2f} MP" if mp >= 0.1 else f"{w*h} px²"
        self._draw_label_box(p, f"{ratio_str}  ·  {mp_str}",
                             r.center().x(), r.bottom() + 14)

    # ── save / cancel ────────────────────────────────────────────────────────

    # An editor opened before a capture is saved (Settings: edit before save) holds a capture that
    # is not on disk yet: closing it loses the screenshot itself, so it always asks.
    capture_unsaved = False

    def has_unsaved_changes(self) -> bool:
        """Anything a close would lose: something drawn (every drawing is an object; one undone
        away is not), a stroke half drawn, or the capture itself when it is not saved yet."""
        return bool(self._objects) or bool(self.drawing) or bool(self._drag) or self.capture_unsaved

    def _ask_before_closing(self) -> str:
        """'save', 'discard' or 'keep' (keep editing). Paul: Esc, Cancel or the window's X must
        not just make an edit disappear."""
        if not self.has_unsaved_changes():
            return "discard"
        if self.capture_unsaved and not self._objects:
            msg = "This screenshot hasn't been saved yet."
            sub = "Discard throws the screenshot away."
        else:
            n = len(self._objects)
            what = "a drawing" if n <= 1 else f"{n} drawings"
            verb = "isn't" if n <= 1 else "aren't"
            msg = f"This screenshot has {what} that {verb} saved."
            sub = ("Discard throws the screenshot away too: it is not saved yet."
                   if self.capture_unsaved else
                   f"Discard keeps the screenshot as it was, without {'it' if n <= 1 else 'them'}.")
        self.raise_()
        self.activateWindow()
        answer = StyledDialog(self, "Unsaved changes", msg, sub=sub, buttons=[
            ("Save", "primary"), ("Discard", "danger"), ("Keep editing", "secondary")]).exec()
        return {"Save": "save", "Discard": "discard"}.get(answer, "keep")   # Esc in the box: keep

    def _result_pixmap(self) -> QPixmap:
        if self._drag:      # mid-drag: drop the object where it is
            self._drag = None
            self._above_pixmap = None
            self._render_overlay()
        result = QPixmap(self.original_pixmap.size())
        p = QPainter(result)
        p.drawPixmap(0, 0, self.original_pixmap)
        p.drawPixmap(0, 0, self.overlay_pixmap)
        p.end()
        return result

    def _save(self):
        result = self._result_pixmap()
        self._finished = True
        self.editing_complete.emit(result)
        self.close()

    def _cancel(self):
        """Esc and the Cancel button: asks first when something would be lost."""
        choice = self._ask_before_closing()
        if choice == "keep":
            return
        if choice == "save":
            self._save()
            return
        self._finished = True
        self.editing_cancelled.emit()
        self.close()

    def closeEvent(self, event):
        # The window's own X (or Alt+F4, or the taskbar) is a cancel too, and asks first the same
        # way; a caller waiting on the editor always hears back.
        if not getattr(self, '_finished', False):
            choice = self._ask_before_closing()
            if choice == "keep":
                event.ignore()
                return
            self._finished = True
            if choice == "save":
                self.editing_complete.emit(self._result_pixmap())
            else:
                self.editing_cancelled.emit()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._save()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and \
             event.key() == Qt.Key.Key_Z:
            self._undo()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected()
        # Keyboard shortcuts for tools
        shortcuts = {
            Qt.Key.Key_V: 'move',
            Qt.Key.Key_H: 'highlight', Qt.Key.Key_P: 'pen',
            Qt.Key.Key_L: 'line',      Qt.Key.Key_A: 'arrow',
            Qt.Key.Key_R: 'rect',      Qt.Key.Key_C: 'circle',
            Qt.Key.Key_B: 'blur',      Qt.Key.Key_T: 'text',
            Qt.Key.Key_M: 'measure_rect' if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 'measure_line',
        }
        if event.key() in shortcuts:
            self._set_mode(shortcuts[event.key()])


# ============================================================================
# SETTINGS DIALOG
# ============================================================================

class SettingsDialog(QDialog):
    """Settings configuration dialog"""

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.config = config.copy()

        self.setWindowTitle("Settings")
        self.setFixedSize(420, 600)
        self.setStyleSheet(f"background: {Theme.BG_LIGHT};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(title)

        # Theme selector
        theme_frame = QFrame()
        theme_layout = QHBoxLayout(theme_frame)
        theme_layout.setContentsMargins(0, 0, 0, 0)

        theme_label = QLabel("Theme:")
        theme_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        theme_layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        for key, name in get_theme_names():
            self.theme_combo.addItem(name, key)
        # Set current theme
        current_theme = config.get('theme', 'solarized_dark')
        for i in range(self.theme_combo.count()):
            if self.theme_combo.itemData(i) == current_theme:
                self.theme_combo.setCurrentIndex(i)
                break
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        layout.addWidget(theme_frame)

        layout.addSpacing(10)

        # Capture delay
        delay_frame = QFrame()
        delay_layout = QHBoxLayout(delay_frame)
        delay_layout.setContentsMargins(0, 0, 0, 0)

        delay_label = QLabel("Capture delay:")
        delay_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        delay_layout.addWidget(delay_label)

        self.delay_combo = QComboBox()
        self.delay_combo.addItems(["0 sec", "3 sec", "5 sec", "10 sec"])
        delay_val = config.get('delay', 0)
        delay_map = {0: 0, 3: 1, 5: 2, 10: 3}
        self.delay_combo.setCurrentIndex(delay_map.get(delay_val, 0))
        delay_layout.addWidget(self.delay_combo)
        delay_layout.addStretch()

        layout.addWidget(delay_frame)

        # Edit before save
        self.edit_check = QCheckBox("Edit before save")
        self.edit_check.setChecked(config.get('edit_before_save', True))
        self.edit_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.edit_check)

        # Edit after save: the capture is saved first, so closing the editor never loses it
        self.edit_after_check = QCheckBox("Open editor after save (saving the edit copies it to the clipboard)")
        self.edit_after_check.setChecked(config.get('edit_after_save', True))
        self.edit_after_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.edit_after_check)

        # Silent capture
        self.silent_check = QCheckBox("Silent capture (don't show window)")
        self.silent_check.setChecked(config.get('silent_capture', False))
        self.silent_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.silent_check)

        # Pin to all desktops
        self.pin_check = QCheckBox("Pin to all virtual desktops")
        self.pin_check.setChecked(config.get('pin_to_all_desktops', False))
        self.pin_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        self.pin_check.setEnabled(PYVDA_AVAILABLE)
        if not PYVDA_AVAILABLE:
            self.pin_check.setToolTip("Install pyvda package for this feature")
        layout.addWidget(self.pin_check)

        # Floating bar toggle
        self.floating_bar_check = QCheckBox("Show floating capture bar (all desktops)")
        self.floating_bar_check.setChecked(config.get('floating_bar_visible', True))
        self.floating_bar_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.floating_bar_check)

        # Thumbnail size
        thumb_frame = QFrame()
        thumb_layout = QHBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(0, 0, 0, 0)

        thumb_label = QLabel("Thumbnail size:")
        thumb_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        thumb_layout.addWidget(thumb_label)

        self.thumb_slider = QSlider(Qt.Orientation.Horizontal)
        self.thumb_slider.setRange(1, 10)
        self.thumb_slider.setValue(config.get('thumbnail_scale', 5))
        self.thumb_slider.setFixedWidth(150)
        thumb_layout.addWidget(self.thumb_slider)

        self.thumb_value = QLabel(str(config.get('thumbnail_scale', 5)))
        self.thumb_value.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        self.thumb_slider.valueChanged.connect(lambda v: self.thumb_value.setText(str(v)))
        thumb_layout.addWidget(self.thumb_value)
        thumb_layout.addStretch()

        layout.addWidget(thumb_frame)

        # Folder preview thumbnail size
        folder_thumb_frame = QFrame()
        folder_thumb_layout = QHBoxLayout(folder_thumb_frame)
        folder_thumb_layout.setContentsMargins(0, 0, 0, 0)

        folder_thumb_label = QLabel("Folder thumb size:")
        folder_thumb_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        folder_thumb_layout.addWidget(folder_thumb_label)

        self.folder_thumb_slider = QSlider(Qt.Orientation.Horizontal)
        self.folder_thumb_slider.setRange(1, 10)
        self.folder_thumb_slider.setValue(config.get('folder_thumbnail_scale', 5))
        self.folder_thumb_slider.setFixedWidth(150)
        folder_thumb_layout.addWidget(self.folder_thumb_slider)

        self.folder_thumb_value = QLabel(str(config.get('folder_thumbnail_scale', 5)))
        self.folder_thumb_value.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        self.folder_thumb_slider.valueChanged.connect(lambda v: self.folder_thumb_value.setText(str(v)))
        folder_thumb_layout.addWidget(self.folder_thumb_value)
        folder_thumb_layout.addStretch()

        layout.addWidget(folder_thumb_frame)

        # Auto-send section
        layout.addSpacing(10)
        autosend_label = QLabel("Send Targets")
        autosend_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        autosend_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(autosend_label)

        # Target list
        self.targets_list = QListWidget()
        self.targets_list.setFixedHeight(110)
        self.targets_list.setStyleSheet(f"""
            QListWidget {{
                background: {Theme.BG_CONTENT};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.TEXT_MUTED};
                border-radius: 4px;
                font-size: 12px;
            }}
            QListWidget::item:selected {{
                background: {Theme.BG_DARK};
                color: white;
            }}
        """)
        self._targets_data = list(config.get('push_targets', []))
        self._refresh_targets_list()
        layout.addWidget(self.targets_list)

        # Add / Remove buttons
        btn_row = QFrame()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(6)

        add_btn = QPushButton("+ Add from open windows...")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_DARK};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {Theme.BG_DARKER}; }}
        """)
        add_btn.clicked.connect(self._add_target_from_windows)
        btn_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: #c0392b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: #a93226; }}
        """)
        remove_btn.clicked.connect(self._remove_selected_target)
        btn_layout.addWidget(remove_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background: #7d6608;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: #9a7d0a; }}
        """)
        edit_btn.clicked.connect(self._edit_selected_target)
        btn_layout.addWidget(edit_btn)
        btn_layout.addStretch()

        layout.addWidget(btn_row)

        # Auto-send toggle
        layout.addSpacing(6)
        self.autosend_check = QCheckBox("Auto-send on capture to:")
        self.autosend_check.setChecked(config.get('auto_send_enabled', False))
        self.autosend_check.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(self.autosend_check)

        self.target_combo = QComboBox()
        self.target_combo.setStyleSheet(f"color: {Theme.TEXT_DARK}; background: {Theme.BG_CONTENT};")
        self._refresh_target_combo(config.get('auto_send_target', ''))
        layout.addWidget(self.target_combo)

        # Storage section
        layout.addSpacing(10)
        storage_label = QLabel("Storage")
        storage_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        storage_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(storage_label)

        # Disk limit
        limit_frame = QFrame()
        limit_layout = QHBoxLayout(limit_frame)
        limit_layout.setContentsMargins(0, 0, 0, 0)

        limit_label = QLabel("Disk limit (MB):")
        limit_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        limit_layout.addWidget(limit_label)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(100, 5000)
        self.limit_spin.setValue(config.get('disk_limit_mb', 500))
        self.limit_spin.setSingleStep(100)
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addStretch()

        layout.addWidget(limit_frame)

        # Archive days
        archive_frame = QFrame()
        archive_layout = QHBoxLayout(archive_frame)
        archive_layout.setContentsMargins(0, 0, 0, 0)

        archive_label = QLabel("Auto-cleanup after (days):")
        archive_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        archive_layout.addWidget(archive_label)

        self.archive_spin = QSpinBox()
        self.archive_spin.setRange(7, 365)
        self.archive_spin.setValue(config.get('archive_days', 30))
        archive_layout.addWidget(self.archive_spin)
        archive_layout.addStretch()

        layout.addWidget(archive_frame)

        # OCR / Search index section
        layout.addSpacing(10)
        ocr_label = QLabel("Text Search (OCR)")
        ocr_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        ocr_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(ocr_label)

        ocr_info = QLabel(
            "Index all existing screenshots so they can be found by text search.\n"
            "New captures are indexed automatically in the background."
        )
        ocr_info.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt;")
        ocr_info.setWordWrap(True)
        layout.addWidget(ocr_info)

        reindex_row = QFrame()
        reindex_layout = QHBoxLayout(reindex_row)
        reindex_layout.setContentsMargins(0, 0, 0, 0)

        self.reindex_btn = QPushButton("Re-index all screenshots")
        self.reindex_btn.setEnabled(OCR_AVAILABLE)
        self.reindex_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_DARK};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {Theme.BG_DARKER}; }}
            QPushButton:disabled {{ background: #555; color: #999; }}
        """)
        self.reindex_btn.clicked.connect(self._start_reindex)
        reindex_layout.addWidget(self.reindex_btn)

        self.reindex_status = QLabel("" if OCR_AVAILABLE else "Tesseract not found")
        self.reindex_status.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 10px;")
        reindex_layout.addWidget(self.reindex_status)
        reindex_layout.addStretch()

        layout.addWidget(reindex_row)
        layout.addSpacing(10)
        loc_label = QLabel("Save location")
        loc_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        loc_label.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        layout.addWidget(loc_label)

        self.path_label = QLabel(str(config.get('save_dir', SAVE_DIR)))
        self.path_label.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-size: 9pt;")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        path_btns = QHBoxLayout()
        change_btn = QPushButton("Change...")
        change_btn.clicked.connect(self._change_path)
        path_btns.addWidget(change_btn)

        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._open_folder)
        path_btns.addWidget(open_btn)
        path_btns.addStretch()

        layout.addLayout(path_btns)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BG_CONTENT};
                color: {Theme.TEXT_DARK};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background: {Theme.BORDER};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #2AA198;
            }}
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _change_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Save Folder", str(self.config.get('save_dir', SAVE_DIR)))
        if path:
            self.config['save_dir'] = path
            self.path_label.setText(path)

    def _open_folder(self):
        path = self.config.get('save_dir', SAVE_DIR)
        os.startfile(str(path))

    def _refresh_targets_list(self):
        """Repopulate the targets QListWidget from self._targets_data"""
        self.targets_list.clear()
        for t in self._targets_data:
            self.targets_list.addItem(f"{t.get('name', '?')}  —  {t.get('title_pattern', '')}")

    def _refresh_target_combo(self, current=''):
        """Repopulate the auto-send combo from self._targets_data"""
        self.target_combo.clear()
        for t in self._targets_data:
            self.target_combo.addItem(t.get('name', 'Unknown'))
        idx = self.target_combo.findText(current)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)

    def _add_target_from_windows(self):
        """Show a dialog listing all visible windows; let user pick one as a new send target"""
        # Collect all visible, titled windows
        windows = []
        def _enum(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title and len(title) > 2:
                    windows.append(title)
        win32gui.EnumWindows(_enum, None)
        windows = sorted(set(windows))

        if not windows:
            StyledDialog.info(self, "No windows", "No visible windows found.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Send Target")
        dlg.setMinimumWidth(420)
        vlay = QVBoxLayout(dlg)

        vlay.addWidget(QLabel("Select an open window:"))
        combo = QComboBox()
        combo.addItems(windows)
        vlay.addWidget(combo)

        vlay.addWidget(QLabel("Name for this target:"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g. Claude Browser")
        vlay.addWidget(name_edit)

        # Auto-fill name when window selection changes — strip app suffixes
        def _smart_name(title):
            """Extract the app name from a window title, stripping doc/url prefixes."""
            import re
            # Common patterns: "Doc name - App Name" or "App Name"
            # Strip trailing separators and known browser/editor suffixes
            suffixes = [
                r'\s*[-–|]\s*Google Chrome$', r'\s*[-–|]\s*Mozilla Firefox$',
                r'\s*[-–|]\s*Microsoft Edge$', r'\s*[-–|]\s*Opera$',
                r'\s*[-–|]\s*Visual Studio Code$', r'\s*[-–|]\s*Notepad\+\+$',
                r'\s*[-–|]\s*Notepad$', r'\s*[-–|]\s*Slack$',
                r'\s*[-–|]\s*Discord$', r'\s*[-–|]\s*WhatsApp$',
            ]
            result = title
            for pat in suffixes:
                result = re.sub(pat, '', result, flags=re.IGNORECASE).strip()
            # If stripping left nothing useful, fall back to last segment after " - "
            if not result:
                parts = re.split(r'\s*[-–|]\s*', title)
                result = parts[-1].strip() if parts else title
            # If still long, take the last " - " segment (usually the app name)
            if len(result) > 40:
                parts = re.split(r'\s*[-–|]\s*', result)
                result = parts[-1].strip() if len(parts) > 1 else result[:40]
            return result[:40]

        def _fill_name(text):
            # Always update to keep suggestion fresh; user can still edit
            name_edit.setText(_smart_name(text))
        combo.currentTextChanged.connect(_fill_name)
        _fill_name(combo.currentText())

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vlay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        window_title = combo.currentText()
        name = name_edit.text().strip() or window_title[:40]

        # Build a title_pattern from the window title (lower, first 40 chars)
        pattern = window_title.lower()[:60]

        # Avoid duplicates by name
        existing_names = {t.get('name', '').lower() for t in self._targets_data}
        if name.lower() in existing_names:
            StyledDialog.warning(self, "Duplicate", f"A target named '{name}' already exists.")
            return

        self._targets_data.append({'name': name, 'title_pattern': pattern, 'enabled': True})
        self._refresh_targets_list()
        current_auto = self.target_combo.currentText()
        self._refresh_target_combo(current_auto)

    def _edit_selected_target(self):
        """Edit name and title_pattern of the selected target"""
        row = self.targets_list.currentRow()
        if row < 0:
            StyledDialog.info(self, "Nothing selected", "Select a target to edit.")
            return

        target = self._targets_data[row]

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Send Target")
        dlg.setMinimumWidth(400)
        vlay = QVBoxLayout(dlg)

        vlay.addWidget(QLabel("Name:"))
        name_edit = QLineEdit(target.get('name', ''))
        vlay.addWidget(name_edit)

        vlay.addWidget(QLabel("Window title pattern (lowercase, partial match):"))
        pattern_edit = QLineEdit(target.get('title_pattern', ''))
        pattern_edit.setToolTip(
            "The app window must contain this text in its title.\n"
            "Use | to match multiple alternatives, e.g. 'claude|chatgpt'"
        )
        vlay.addWidget(pattern_edit)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vlay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_name = name_edit.text().strip()
        new_pattern = pattern_edit.text().strip().lower()

        if not new_name or not new_pattern:
            StyledDialog.warning(self, "Invalid", "Name and pattern cannot be empty.")
            return

        # Check for duplicate name (ignoring the current row)
        for i, t in enumerate(self._targets_data):
            if i != row and t.get('name', '').lower() == new_name.lower():
                StyledDialog.warning(self, "Duplicate", f"A target named '{new_name}' already exists.")
                return

        self._targets_data[row] = {**target, 'name': new_name, 'title_pattern': new_pattern}
        current_auto = self.target_combo.currentText()
        self._refresh_targets_list()
        self._refresh_target_combo(current_auto)
        self.targets_list.setCurrentRow(row)

    def _remove_selected_target(self):
        """Remove the currently selected target from the list"""
        row = self.targets_list.currentRow()
        if row < 0:
            StyledDialog.info(self, "Nothing selected", "Select a target to remove.")
            return
        name = self._targets_data[row].get('name', '')
        reply = StyledDialog.question(self, "Remove target", f"Remove '{name}' from send targets?")
        if reply:
            del self._targets_data[row]
            self._refresh_targets_list()
            current_auto = self.target_combo.currentText()
            self._refresh_target_combo(current_auto)

    def _start_reindex(self):
        """Launch ReindexWorker to OCR all existing screenshots."""
        self.reindex_btn.setEnabled(False)
        self.reindex_status.setText("Starting…")
        save_dir = Path(self.config.get('save_dir', SAVE_DIR))
        index = OcrIndex(save_dir / "ocr_index.db")
        self._reindex_worker = ReindexWorker(save_dir, index)
        self._reindex_worker.progress.connect(
            lambda done, total: self.reindex_status.setText(f"{done}/{total}"))
        self._reindex_worker.finished.connect(self._on_reindex_done)
        self._reindex_worker.start()

    def _on_reindex_done(self, count: int):
        self.reindex_status.setText(f"Done — {count} files processed")
        self.reindex_btn.setEnabled(OCR_AVAILABLE)

    def _save(self):
        # Update config
        self.config['theme'] = self.theme_combo.currentData()
        delay_text = self.delay_combo.currentText()
        self.config['delay'] = int(delay_text.split()[0])
        self.config['edit_before_save'] = self.edit_check.isChecked()
        self.config['edit_after_save'] = self.edit_after_check.isChecked()
        self.config['silent_capture'] = self.silent_check.isChecked()
        self.config['pin_to_all_desktops'] = self.pin_check.isChecked()
        self.config['floating_bar_visible'] = self.floating_bar_check.isChecked()
        self.config['thumbnail_scale'] = self.thumb_slider.value()
        self.config['folder_thumbnail_scale'] = self.folder_thumb_slider.value()
        self.config['auto_send_enabled'] = self.autosend_check.isChecked()
        self.config['auto_send_target'] = self.target_combo.currentText()
        self.config['push_targets'] = self._targets_data
        self.config['disk_limit_mb'] = self.limit_spin.value()
        self.config['archive_days'] = self.archive_spin.value()

        self.accept()

    def get_config(self) -> dict:
        return self.config


# ============================================================================
# MAIN WINDOW
# ============================================================================

class MainWindow(QMainWindow):
    """Main application window"""

    screenshot_written = pyqtSignal(str, bool)   # filepath, ok — from the background PNG writer
    edit_written = pyqtSignal(str, bool, int)    # filepath, ok, size change — an editor save written
    live_typing_requested = pyqtSignal()          # Ctrl+Shift+Space, from the keyboard hook's thread

    def __init__(self):
        super().__init__()
        _trace_startup("MainWindow.__init__ start")

        # State
        self.current_folder: Optional[str] = None
        self.capture_in_progress = False
        # Every open editor window. Each capture (or gallery edit) opens its own; the ones already
        # open stay as they are. A capture hides them while it runs and shows them again after.
        self._editors: list = []
        self._editors_hidden_for_capture: list = []
        self.session_count = 0
        self._main_was_visible_before_capture = False
        self._floating_bar_was_visible_before_capture = False
        self._cached_storage_bytes: Optional[int] = None
        self._thumb_pixmap_cache: OrderedDict[str, QPixmap] = OrderedDict()
        # Must exceed the number of screenshots in a folder: a smaller LRU walked in gallery
        # order never gets a hit (500 against 912 files re-decoded every image, ~27 s a refresh).
        self._thumb_cache_max_entries = 5000
        self._thumb_failed: set = set()              # cache keys of files that could not be read
        self._thumb_widgets: Dict[str, ThumbnailWidget] = {}   # filepath -> widget, reused across refreshes
        self._gallery_order: List[str] = []          # filepaths in the grid, in order
        self._gallery_context: Optional[tuple] = None  # (folder, thumb w, thumb h) the widgets were built for
        self._gallery_cols = 0
        self._gallery_build: Optional[dict] = None     # the refresh whose widgets are still being created
        self._gallery_build_gen = 0
        self._gallery_build_pending = False
        self._pending_save_paths: set = set()
        self._save_threads: Dict[str, threading.Thread] = {}   # filepath -> its latest background write
        self._last_gallery_images: List[Path] = []

        self._thumb_loader = ThumbnailLoader()
        self._thumb_loader.loaded.connect(self._on_thumbnail_loaded)
        self._thumb_loader.start()
        QApplication.instance().aboutToQuit.connect(self._thumb_loader.stop)
        self.screenshot_written.connect(self._on_screenshot_written)
        self.edit_written.connect(self._on_edit_written)
        # Voice typing into any text box (Ctrl+Shift+Space)
        self._live_typing = LiveVoiceTyping()
        self.live_typing_requested.connect(self._live_typing.toggle)
        QApplication.instance().aboutToQuit.connect(self._live_typing.shutdown)
        self._live_strip_hidden_for_capture = False

        # Coalesce bursts (window drag-resize, typing in search) into one gallery update.
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.setInterval(120)
        self._reflow_timer.timeout.connect(self._reflow_gallery)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._refresh_gallery)
        self._resize_margin = 8
        self._use_native_resize_hit_test = False  # stability-first: disable crash-prone hook
        # Qt6 + Python 3.14 has shown native crashes on first show() when frameless is enabled.
        # Keep startup stable by default; allow explicit opt-in for testing.
        force_frameless = os.environ.get("OTTERLY_FORCE_FRAMELESS", "").strip() == "1"
        self._use_frameless_main_window = force_frameless or (sys.version_info < (3, 14))
        self._use_minimal_styles = False

        # Load config
        self.config = self._load_config()
        self.save_dir = Path(self.config.get('save_dir', SAVE_DIR))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # OCR index
        self.ocr_index = OcrIndex(self.save_dir / "ocr_index.db")
        self._ocr_workers: List[OcrWorker] = []  # keep refs alive
        self._search_query: str = ""
        self._desktop_target_override: Optional[str] = None  # set by FloatingBar

        # Setup UI
        self._setup_ui()
        _trace_startup("MainWindow._setup_ui complete")

        # Delay hotkey registration until after the main window is visible to avoid early hook crashes.
        _trace_startup("MainWindow hotkey registration deferred")

        # Initial UI/data refresh
        if not self._use_minimal_styles:
            QTimer.singleShot(100, self._refresh_folder_bar)
            QTimer.singleShot(100, self._refresh_gallery)

        # Pin main window to all virtual desktops after window is shown
        if self.config.get('pin_to_all_desktops', False):
            QTimer.singleShot(500, self._pin_to_all_desktops)

        # Floating capture bar must be available independently of the main window.
        self.floating_bar = FloatingBar(self)
        if self.config.get('floating_bar_visible', True):
            QTimer.singleShot(400, self.floating_bar.show)
        _trace_startup("MainWindow.__init__ complete")

    def _ensure_floating_bar(self):
        """Create/show the floating capture bar after startup is fully visible."""
        if self.floating_bar is None:
            self.floating_bar = FloatingBar(self)
        if self.config.get('floating_bar_visible', True):
            self.floating_bar.show()
            print(f"[Otterly] Floating bar shown at ({self.floating_bar.x()}, {self.floating_bar.y()})", flush=True)

    def nativeEvent(self, eventType, message):
        """Native Windows hit-testing for reliable edge/corner resize in frameless mode."""
        if sys.platform != "win32" or not self._use_native_resize_hit_test:
            return False, 0

        try:
            WM_NCHITTEST = 0x0084
            HTLEFT = 10
            HTRIGHT = 11
            HTTOP = 12
            HTTOPLEFT = 13
            HTTOPRIGHT = 14
            HTBOTTOM = 15
            HTBOTTOMLEFT = 16
            HTBOTTOMRIGHT = 17

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", ctypes.c_void_p),
                    ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p),
                    ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_uint),
                    ("pt_x", ctypes.c_long),
                    ("pt_y", ctypes.c_long),
                ]

            msg = MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST and not self.isMaximized():
                lparam = int(msg.lParam)
                x = ctypes.c_short(lparam & 0xFFFF).value
                y = ctypes.c_short((lparam >> 16) & 0xFFFF).value

                fg = self.frameGeometry()
                m = self._resize_margin

                on_left = fg.left() <= x <= fg.left() + m
                on_right = fg.right() - m <= x <= fg.right()
                on_top = fg.top() <= y <= fg.top() + m
                on_bottom = fg.bottom() - m <= y <= fg.bottom()

                if on_top and on_left:
                    return True, HTTOPLEFT
                if on_top and on_right:
                    return True, HTTOPRIGHT
                if on_bottom and on_left:
                    return True, HTBOTTOMLEFT
                if on_bottom and on_right:
                    return True, HTBOTTOMRIGHT
                if on_left:
                    return True, HTLEFT
                if on_right:
                    return True, HTRIGHT
                if on_top:
                    return True, HTTOP
                if on_bottom:
                    return True, HTBOTTOM
        except Exception as e:
            logging.error(f"nativeEvent resize handling failed: {e}")

        return False, 0

    def _load_config(self) -> dict:
        """Load configuration from JSON file"""
        default_config = {
            'save_dir': str(SAVE_DIR),
            'theme': 'solarized_dark',
            'delay': 0,
            'edit_before_save': True,
            'edit_after_save': True,
            'silent_capture': False,
            'pin_to_all_desktops': False,
            'thumbnail_scale': 5,
            'folder_thumbnail_scale': 5,
            'auto_send_enabled': False,
            'auto_send_target': '',
            'disk_limit_mb': 500,
            'archive_days': 30,
            'push_targets': [
                {'name': 'VSCode Claude', 'title_pattern': 'claude code|visual studio code', 'enabled': True},
                {'name': 'WhatsApp', 'title_pattern': 'WhatsApp', 'enabled': True},
                {'name': 'Discord', 'title_pattern': 'Discord', 'enabled': True},
                {'name': 'Slack', 'title_pattern': 'Slack', 'enabled': True},
                {'name': 'Teams', 'title_pattern': 'Microsoft Teams', 'enabled': True},
            ]
        }

        if CONFIG_FILE.exists():
            try:
                # Use utf-8-sig so BOM-prefixed JSON files still load correctly.
                with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception as e:
                logging.error(f"Failed to load config: {e}")

        # Apply loaded theme
        set_active_theme(default_config.get('theme', 'solarized_dark'))

        return default_config

    def _save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def _setup_ui(self):
        """Setup the main UI"""
        # Use native window frame for startup stability (frameless can be force-enabled via env var).
        if self._use_frameless_main_window:
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 900, 650)
        self.setMinimumSize(840, 560)
        if self._use_minimal_styles:
            self.setStyleSheet("")
        else:
            self.setStyleSheet(generate_stylesheet())

        if self._use_minimal_styles:
            self._setup_ui_compat()
            return

        # Set window icon
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Main container
        container = QWidget()
        container.setStyleSheet(f"background: {Theme.BG_GALLERY};")
        self.setCentralWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        if self._use_frameless_main_window:
            self.title_bar = CustomTitleBar(self, show_window_controls=True)
        else:
            self.title_bar = SimpleTitleBar(self)
        self.title_bar.search_edit.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self.title_bar)

        # Content area with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.setHandleWidth(0)  # Hide default handle
        splitter.setChildrenCollapsible(False)
        splitter.setOpaqueResize(False)
        self.main_splitter = splitter

        # Sidebar
        sidebar = self._create_sidebar()
        splitter.addWidget(sidebar)

        # Insert custom 3D line divider
        class ThreeDLine(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setFixedWidth(5)  # Slightly thicker than right divider
                self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            def paintEvent(self, event):
                p = QPainter(self)
                # Slightly different shade than background
                bg = QColor(Theme.BG_GALLERY)
                line = QColor(bg.red() + 10, bg.green() + 10, bg.blue() + 10)
                p.fillRect(self.rect(), bg)
                p.setPen(QPen(line, 5))
                p.drawLine(self.width() // 2, 0, self.width() // 2, self.height())
                p.end()

        splitter.addWidget(ThreeDLine())

        # Gallery area
        gallery_container = self._create_gallery()
        splitter.addWidget(gallery_container)

        splitter.setSizes([200, 10, 700])
        # Left divider is a permanent border, not user-resizable.
        left_handle = splitter.handle(1)
        left_handle.setEnabled(False)
        left_handle.setCursor(Qt.CursorShape.ArrowCursor)
        left_handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        splitter.setStyleSheet("")  # Remove default handle styling
        main_layout.addWidget(splitter)

        # Status bar + resize grip
        status_container = QFrame()
        status_container.setObjectName("statusBar")
        status_container.setFixedHeight(30)
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(10, 0, 4, 0)
        status_layout.setSpacing(6)

        self.status_bar = QLabel("Ready")
        status_layout.addWidget(self.status_bar)
        status_layout.addStretch()

        self.size_grip = QSizeGrip(status_container)
        self.size_grip.setFixedSize(20, 20)
        self.size_grip.setToolTip("Resize window")
        status_layout.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        main_layout.addWidget(status_container)

    def _setup_ui_compat(self):
        """Compatibility UI for Python 3.14 startup stability."""
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        info = QLabel("Compatibility mode: UI trimmed for startup stability on Python 3.14")
        info.setStyleSheet("color: #666;")
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        region_btn = QPushButton("Region")
        region_btn.clicked.connect(self._start_region_capture)
        btn_row.addWidget(region_btn)

        screen_btn = QPushButton("Screen")
        screen_btn.clicked.connect(self._capture_fullscreen)
        btn_row.addWidget(screen_btn)

        window_btn = QPushButton("Window")
        window_btn.clicked.connect(self._start_window_capture)
        btn_row.addWidget(window_btn)
        layout.addLayout(btn_row)

        utility_row = QHBoxLayout()
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self._show_settings)
        utility_row.addWidget(settings_btn)

        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self._import_image)
        utility_row.addWidget(import_btn)

        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(self._paste_from_clipboard)
        utility_row.addWidget(paste_btn)
        layout.addLayout(utility_row)

        self.status_bar = QLabel("Ready")
        layout.addWidget(self.status_bar)

        self.session_label = QLabel("Screenshots: 0")
        layout.addWidget(self.session_label)

        self.disk_label = QLabel("Storage info available in full UI mode")
        layout.addWidget(self.disk_label)

        layout.addStretch()

    def _folder_thumb_width(self) -> int:
        """Map folder thumbnail scale (1..10) to preview card width in px."""
        scale = int(self.config.get('folder_thumbnail_scale', 5))
        return 24 + scale * 6

    def _create_sidebar(self) -> QWidget:
        """Create the sidebar with buttons"""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Logo
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            logo_pixmap = QPixmap(str(logo_path))
            scaled = logo_pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("background: transparent;")
            layout.addWidget(logo_label)
            layout.addSpacing(10)

        # Capture buttons
        btn_style = f"""
            QPushButton {{
                background: {Theme.BUTTON_BG};
                color: {Theme.BUTTON_TEXT};
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                text-align: left;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background: {Theme.BUTTON_HOVER};
            }}
            QPushButton:pressed {{
                background: {Theme.ACCENT};
            }}
        """

        region_btn = QPushButton("📷 Region (Ctrl+Shift+R)")
        region_btn.setStyleSheet(btn_style)
        region_btn.clicked.connect(self._start_region_capture)
        layout.addWidget(region_btn)

        screen_btn = QPushButton("🖥️ Screen (Ctrl+Shift+S)")
        screen_btn.setStyleSheet(btn_style)
        screen_btn.clicked.connect(self._capture_fullscreen)
        layout.addWidget(screen_btn)

        window_btn = QPushButton("🪟 Window (Ctrl+Shift+W)")
        window_btn.setStyleSheet(btn_style)
        window_btn.clicked.connect(self._start_window_capture)
        layout.addWidget(window_btn)

        # Import buttons
        import_btn = QPushButton("📁 Import from File")
        import_btn.setStyleSheet(btn_style)
        import_btn.clicked.connect(self._import_image)
        layout.addWidget(import_btn)

        paste_btn = QPushButton("📋 Paste from Clipboard")
        paste_btn.setStyleSheet(btn_style)
        paste_btn.clicked.connect(self._paste_from_clipboard)
        layout.addWidget(paste_btn)

        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setStyleSheet(btn_style)
        settings_btn.clicked.connect(self._show_settings)
        layout.addWidget(settings_btn)

        layout.addStretch()

        # Hidden labels kept for internal tracking (not shown in sidebar)
        self.disk_label = QLabel()
        self.disk_label.hide()
        self.session_label = QLabel()
        self.session_label.hide()

        return sidebar

    def _create_gallery(self) -> QWidget:
        """Create the gallery area with right folder sidebar and thumbnails"""
        container = QFrame()
        container.setObjectName("gallery")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        gallery_splitter = QSplitter(Qt.Orientation.Horizontal)
        gallery_splitter.setObjectName("gallerySplitter")
        gallery_splitter.setHandleWidth(0)  # Hide default handle
        gallery_splitter.setChildrenCollapsible(False)
        gallery_splitter.setOpaqueResize(False)
        gallery_splitter.splitterMoved.connect(lambda *_: self._reflow_timer.start())
        self.gallery_splitter = gallery_splitter

        # Left content: OCR status + gallery grid
        main_area = QFrame()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.ocr_status_label = QLabel("")
        self.ocr_status_label.setStyleSheet(
            f"color: {Theme.TEXT_MUTED}; font-size: 10px; padding: 6px 12px; background: transparent;")
        self.ocr_status_label.setVisible(False)

        self.current_folder_label = QLabel("Main")
        self.current_folder_label.setStyleSheet("""
            color: rgb(25, 56, 90);
            background: rgb(238, 201, 142);
            border: 1px solid rgb(32, 79, 126);
            border-radius: 7px;
            font-size: 9pt;
            font-weight: 700;
            padding: 3px 10px;
            margin: 6px 0 2px 10px;
        """)
        self.current_folder_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.current_folder_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._update_current_folder_label()

        folder_title_row = QHBoxLayout()
        folder_title_row.setContentsMargins(0, 0, 0, 0)
        folder_title_row.setSpacing(0)
        folder_title_row.addWidget(self.current_folder_label)
        folder_title_row.addStretch()
        main_layout.addLayout(folder_title_row)
        main_layout.addWidget(self.ocr_status_label)

        self.gallery_scroll = QScrollArea() if self._use_minimal_styles else HoverScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.gallery_scroll.setStyleSheet(self._main_scrollbar_stylesheet())
        # Move scrollbar 10px to the right for visual offset
        self.gallery_scroll.setViewportMargins(0, 0, 10, 0)

        self.gallery_widget = QWidget()
        self.gallery_widget.setStyleSheet(f"background: {Theme.BG_DARK};")
        self.gallery_grid = QGridLayout(self.gallery_widget)
        self.gallery_grid.setContentsMargins(15, 15, 15, 15)
        self.gallery_grid.setSpacing(10)
        self.gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.gallery_scroll.setWidget(self.gallery_widget)
        main_layout.addWidget(self.gallery_scroll)
        gallery_splitter.addWidget(main_area)

        # Insert custom right divider (3D line) to visually match left divider
        class ThreeDLineRight(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setFixedWidth(5)  # Match left divider thickness
                self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            def paintEvent(self, event):
                p = QPainter(self)
                bg = QColor(Theme.BG_DARK)
                line = QColor(bg.red() + 10, bg.green() + 10, bg.blue() + 10)
                grad = QLinearGradient(0, 0, self.width(), 0)
                grad.setColorAt(0.0, bg)
                grad.setColorAt(0.5, line)
                grad.setColorAt(1.0, bg)
                p.fillRect(self.rect(), grad)
                p.setPen(QPen(line, 5))
                p.drawLine(self.width() // 2, 0, self.width() // 2, self.height())
                p.end()

        gallery_splitter.addWidget(ThreeDLineRight())

        # Right sidebar: folders
        self.folder_sidebar = QFrame()
        self.folder_sidebar.setObjectName("folderSidebar")
        self.folder_sidebar.setMinimumWidth(190)
        self.folder_sidebar.setMaximumWidth(520)
        self.folder_sidebar.setStyleSheet(f"""
            QFrame#folderSidebar {{
                background: {Theme.BG_DARK};
                border-left: 1px solid {Theme.BORDER};
            }}
        """)

        sidebar_layout = QVBoxLayout(self.folder_sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(8)

        self.folder_scroll = QScrollArea() if self._use_minimal_styles else HoverScrollArea()
        self.folder_scroll.setWidgetResizable(True)
        self.folder_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.folder_scroll.setStyleSheet(self._main_scrollbar_stylesheet())
        self.folder_scroll.setViewportMargins(-3, 0, 10, 0)

        self.folder_widget = QWidget()
        self.folder_layout = QVBoxLayout(self.folder_widget)
        self.folder_layout.setContentsMargins(0, 0, 0, 0)
        self.folder_layout.setSpacing(2)

        self.folder_scroll.setWidget(self.folder_widget)
        sidebar_layout.addWidget(self.folder_scroll)
        gallery_splitter.addWidget(self.folder_sidebar)
        gallery_splitter.setSizes([760, 5, 260])
        gallery_splitter.setStretchFactor(0, 1)
        gallery_splitter.setStretchFactor(1, 0)
        gallery_splitter.setStretchFactor(2, 0)

        layout.addWidget(gallery_splitter)

        return container

    def _main_scrollbar_stylesheet(self) -> str:
        """Dedicated, high-contrast scrollbar style for main window scroll areas."""
        return """
            QScrollBar:vertical {
                background: #1b2d38;
                width: 16px;
                margin: 1px;
                border: 1px solid #0f1e27;
                border-radius: 8px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #8ea0aa, stop:0.45 #6f838f, stop:1 #4c5f6a);
                min-height: 34px;
                border-radius: 7px;
                border-top: 1px solid #c8d2d8;
                border-left: 1px solid #c8d2d8;
                border-right: 1px solid #2d3d47;
                border-bottom: 1px solid #2d3d47;
                margin: 1px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #b2c4ce, stop:0.5 #7fa0b0, stop:1 #4f6a78);
            }
            QScrollBar:horizontal {
                background: #1b2d38;
                height: 16px;
                margin: 1px;
                border: 1px solid #0f1e27;
                border-radius: 8px;
            }
            QScrollBar::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #8ea0aa, stop:0.45 #6f838f, stop:1 #4c5f6a);
                min-width: 34px;
                border-radius: 7px;
                border-top: 1px solid #c8d2d8;
                border-left: 1px solid #c8d2d8;
                border-right: 1px solid #2d3d47;
                border-bottom: 1px solid #2d3d47;
                margin: 1px;
            }
            QScrollBar::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #b2c4ce, stop:0.5 #7fa0b0, stop:1 #4f6a78);
            }
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {
                background: transparent;
                border: none;
                width: 0px;
                height: 0px;
            }
        """

    # NOTE: custom frameless edge-resize hooks removed.
    # Native window frame now provides standard Windows resize cursors and behavior.

    def _refresh_folder_bar(self):
        """Refresh folder buttons in the right sidebar."""
        if not hasattr(self, 'folder_layout'):
            return
        # Clear existing
        while self.folder_layout.count():
            item = self.folder_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # "Main" button
        preview_width = self._folder_thumb_width()

        all_btn = FolderButton(None, self.save_dir, self.current_folder is None, preview_width=preview_width)
        all_btn.clicked.connect(self._select_folder)
        self.folder_layout.addWidget(all_btn)

        # Folder buttons
        folders = self._get_folders()
        for folder in folders:
            btn = FolderButton(folder, self.save_dir, self.current_folder == folder, preview_width=preview_width)
            btn.clicked.connect(self._select_folder)
            btn.context_menu_requested.connect(self._folder_context_menu)
            btn.file_dropped.connect(self._move_to_folder)
            self.folder_layout.addWidget(btn)

        # Add folder button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(200, 56)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.BUTTON_BG};
                color: {Theme.ACCENT};
                border: 2px dashed {Theme.BUTTON_HOVER};
                border-radius: 6px;
                font-size: 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {Theme.ACCENT};
                background: {Theme.BUTTON_HOVER};
            }}
        """)
        add_btn.clicked.connect(self._create_folder)
        self.folder_layout.addWidget(add_btn)

        self.folder_layout.addStretch()

    def _get_folders(self) -> List[str]:
        """Get list of subfolders"""
        folders = []
        if self.save_dir.exists():
            for item in self.save_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    folders.append(item.name)
        return sorted(folders)

    def _select_folder(self, folder_name: Optional[str]):
        """Select a folder to filter gallery"""
        self.current_folder = folder_name
        self._update_current_folder_label()
        self._refresh_folder_bar()
        self._refresh_gallery()

    def _update_current_folder_label(self):
        """Keep the current-folder badge in sync with gallery filter state."""
        if not hasattr(self, 'current_folder_label'):
            return
        self.current_folder_label.setText(self.current_folder or "Main")

    def _on_search_changed(self, text: str):
        self._search_query = text.strip()
        # Wait for a pause in typing instead of filtering on every keystroke.
        self._search_timer.start()

    def _refresh_gallery(self, use_cached_images: bool = False):
        """Refresh the thumbnail gallery.

        Widgets are kept between refreshes and only re-ordered; thumbnails that are not in
        memory are made by the background ThumbnailLoader, so this never decodes a file.
        """
        if not hasattr(self, 'gallery_grid'):
            return
        self._search_timer.stop()

        # Get images
        if self.current_folder:
            folder_path = self.save_dir / self.current_folder
        else:
            folder_path = self.save_dir

        thumb_size = self._gallery_thumb_size()
        size_tag = f"{thumb_size.width()}x{thumb_size.height()}"
        keys: Dict[str, str] = {}   # filepath -> thumbnail cache key (same format as _thumbnail_cache_key)

        if use_cached_images and self._last_gallery_images:
            images = list(self._last_gallery_images)
        else:
            # Root/main view shows only files in the root save dir (not recursive),
            # not files that were moved into subfolders.
            # scandir: on Windows the directory listing already carries size and dates,
            # so this costs one disk call per folder instead of three per file.
            dated = []
            if folder_path.exists():
                try:
                    with os.scandir(folder_path) as it:
                        for entry in it:
                            if not entry.name.lower().endswith(".png"):
                                continue
                            try:
                                if not entry.is_file():
                                    continue
                                st = entry.stat()
                            except OSError:
                                continue
                            item = folder_path / entry.name
                            keys[str(item)] = f"{item}|{st.st_mtime_ns}|{st.st_size}|{size_tag}"
                            dated.append((st.st_mtime, item))
                except OSError as e:
                    logging.error(f"Gallery scan failed for {folder_path}: {e}")

            # Sort by modification time
            dated.sort(key=lambda e: e[0], reverse=True)
            images = [item for _, item in dated]

            # Filter by search query if active
            if self._search_query and OCR_AVAILABLE:
                matched = set(str(p) for p in self.ocr_index.search(self._search_query))
                images = [p for p in images if str(p) in matched]
                self.ocr_status_label.setText(f'{len(images)} result(s) for "{self._search_query}"')
                self.ocr_status_label.setVisible(True)
            elif self._search_query and not OCR_AVAILABLE:
                self.ocr_status_label.setText("OCR unavailable — Tesseract not found")
                self.ocr_status_label.setVisible(True)
            else:
                self.ocr_status_label.setVisible(False)

            self._last_gallery_images = list(images)

        cols = self._current_gallery_columns(thumb_size)

        # Another folder, thumbnail size or theme: none of the existing widgets can be reused.
        context = (str(folder_path), thumb_size.width(), thumb_size.height(), get_active_theme())
        if context != self._gallery_context:
            self._clear_gallery_widgets()
            self._gallery_context = context

        indexed_paths = set()
        if OCR_AVAILABLE and images:
            indexed_paths = self.ocr_index.get_indexed_filepaths(images)

        order = [str(p) for p in images]
        self._gallery_build_gen += 1
        self._gallery_build = {
            'gen': self._gallery_build_gen, 'order': order, 'keys': keys,
            'indexed': indexed_paths, 'thumb_size': thumb_size, 'cols': cols, 'missing': [],
        }
        self._gallery_order = order
        self._gallery_cols = cols

        self.gallery_widget.setUpdatesEnabled(False)
        try:
            # Widgets not wanted now: hidden while a search filters them out, removed otherwise.
            wanted = set(order)
            for path_str in list(self._thumb_widgets):
                if path_str in wanted:
                    continue
                thumb = self._thumb_widgets[path_str]
                thumb.hide()
                if not self._search_query:
                    del self._thumb_widgets[path_str]
                    thumb.deleteLater()

            # Take every widget out of the grid; the ones still wanted go back in order.
            while self.gallery_grid.count():
                self.gallery_grid.takeAt(0)

            to_load: List[Tuple[str, str]] = []
            for i, path_str in enumerate(order):
                thumb = self._thumb_widgets.get(path_str)
                if thumb is None:
                    self._gallery_build['missing'].append(i)   # created below, a batch at a time
                    continue
                self._place_thumbnail(thumb, i, to_load)
        finally:
            self.gallery_widget.setUpdatesEnabled(True)

        self._thumb_loader.request(to_load)
        self._create_missing_thumbnails(self._gallery_build_gen)

        # Update disk usage
        self._update_disk_usage()

    def _place_thumbnail(self, thumb: 'ThumbnailWidget', index: int, to_load: List[Tuple[str, str]]):
        """Put one widget at its grid position, with its OCR badge and (cached or queued) picture."""
        build = self._gallery_build
        path_str = build['order'][index]
        thumb.set_ocr_indexed(OCR_AVAILABLE and path_str in build['indexed'])

        # A new file, or one edited since its thumbnail was made.
        key = build['keys'].get(path_str) or self._thumbnail_cache_key(Path(path_str), build['thumb_size'])
        if key and thumb.cache_key != key:
            cached = self._thumb_pixmap_cache.get(key)
            if cached is not None:
                self._thumb_pixmap_cache.move_to_end(key)
                thumb.set_thumbnail(cached, key)
            elif key not in self._thumb_failed:
                to_load.append((path_str, key))

        cols = build['cols']
        self.gallery_grid.addWidget(thumb, index // cols, index % cols)
        thumb.show()

    def _create_missing_thumbnails(self, gen: int):
        """Create new thumbnail widgets a batch at a time so a large folder never locks the window.

        The first batch (the top of the gallery) is made at once; the rest between events.
        """
        build = self._gallery_build
        if not build or build['gen'] != gen:
            return  # a newer refresh took over
        missing = build['missing']
        if not missing:
            self._gallery_build_pending = False
            if self._current_gallery_columns(build['thumb_size']) != self._gallery_cols:
                self._reflow_gallery()
            return

        self._gallery_build_pending = True
        batch, build['missing'] = missing[:80], missing[80:]
        to_load: List[Tuple[str, str]] = []
        self.gallery_widget.setUpdatesEnabled(False)
        try:
            for i in batch:
                path_str = build['order'][i]
                thumb = ThumbnailWidget(Path(path_str), build['thumb_size'])
                thumb.clicked.connect(self._on_thumbnail_click)
                thumb.double_clicked.connect(self._open_image)
                thumb.context_menu_requested.connect(self._thumbnail_context_menu)
                self._thumb_widgets[path_str] = thumb
                self._place_thumbnail(thumb, i, to_load)
        finally:
            self.gallery_widget.setUpdatesEnabled(True)
        if to_load:
            self._thumb_loader.extend(to_load)
        QTimer.singleShot(0, lambda g=gen: self._create_missing_thumbnails(g))

    def _gallery_thumb_size(self) -> QSize:
        scale = self.config.get('thumbnail_scale', 5)
        return QSize(80 + scale * 15, 60 + scale * 12)

    def _clear_gallery_widgets(self):
        """Delete every thumbnail widget (folder or thumbnail size changed)."""
        while self.gallery_grid.count():
            self.gallery_grid.takeAt(0)
        for thumb in self._thumb_widgets.values():
            thumb.hide()
            thumb.deleteLater()
        self._thumb_widgets.clear()
        self._gallery_order = []

    def _reflow_gallery(self, force: bool = False):
        """Re-grid the existing thumbnails in gallery order (window/splitter resize, or after a delete)."""
        if not hasattr(self, 'gallery_grid') or self._gallery_build_pending:
            return  # a build still creating widgets re-flows itself when it finishes
        cols = self._current_gallery_columns(self._gallery_thumb_size())
        if cols == self._gallery_cols and not force:
            return
        self.gallery_widget.setUpdatesEnabled(False)
        try:
            while self.gallery_grid.count():
                self.gallery_grid.takeAt(0)
            i = 0
            for path_str in self._gallery_order:
                thumb = self._thumb_widgets.get(path_str)
                if thumb is None:
                    continue
                self.gallery_grid.addWidget(thumb, i // cols, i % cols)
                i += 1
        finally:
            self.gallery_widget.setUpdatesEnabled(True)
        self._gallery_cols = cols

    def _on_thumbnail_loaded(self, path_str: str, key: str, master: QImage):
        """A thumbnail made by the background loader: cache it and put it on its widget."""
        if master.isNull():
            self._thumb_failed.add(key)
            return
        thumb_size = self._gallery_thumb_size()
        if not key.endswith(f"|{thumb_size.width()}x{thumb_size.height()}"):
            return  # thumbnail size changed while it was being made; a new request is queued
        pixmap = QPixmap.fromImage(master.scaled(
            thumb_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self._thumb_pixmap_cache[key] = pixmap
        if len(self._thumb_pixmap_cache) > self._thumb_cache_max_entries:
            self._thumb_pixmap_cache.popitem(last=False)
        thumb = self._thumb_widgets.get(path_str)
        if thumb is not None:
            thumb.set_thumbnail(pixmap, key)

    def _current_gallery_columns(self, thumb_size: QSize) -> int:
        """Calculate how many columns fit in the current gallery viewport."""
        gallery_width = self.gallery_scroll.width() - 50
        return max(1, gallery_width // (thumb_size.width() + 20))

    def _thumbnail_cache_key(self, filepath: Path, thumb_size: QSize) -> Optional[str]:
        """Create a cache key that changes when file content or target thumb size changes."""
        try:
            stat = filepath.stat()
            return f"{filepath}|{stat.st_mtime_ns}|{stat.st_size}|{thumb_size.width()}x{thumb_size.height()}"
        except Exception:
            return None

    def _invalidate_thumbnail_cache(self, filepath: Optional[Path] = None):
        """Invalidate thumbnail cache entries for one file or clear everything."""
        if filepath is None:
            self._thumb_pixmap_cache.clear()
            return

        prefix = f"{filepath}|"
        keys = [k for k in self._thumb_pixmap_cache.keys() if k.startswith(prefix)]
        for key in keys:
            self._thumb_pixmap_cache.pop(key, None)

    def _remove_thumbnail_from_gallery(self, filepath: Path) -> bool:
        """Remove one thumbnail widget and reflow existing widgets without rebuilding all thumbnails."""
        path_str = str(filepath)
        thumb = self._thumb_widgets.pop(path_str, None)
        if thumb is not None:
            thumb.hide()
            thumb.deleteLater()
        if self._gallery_build_pending or path_str not in self._gallery_order:
            return False  # caller falls back to a full refresh
        # Grid insertion order is not display order (widgets are created in batches), so re-flow by path order.
        self._gallery_order = [p for p in self._gallery_order if p != path_str]
        self._reflow_gallery(force=True)
        return True

    def _on_thumbnail_click(self, filepath: Path):
        """Handle single click on thumbnail"""
        self._open_image(filepath)

    def _open_image(self, filepath: Path):
        """Open image — in search preview if a query is active, else system viewer."""
        if self._search_query and OCR_AVAILABLE:
            dlg = SearchPreviewDialog(filepath, self._search_query, parent=self)
            dlg.exec()
        else:
            try:
                os.startfile(str(filepath))
            except Exception as e:
                logging.error(f"Failed to open image: {e}")

    def _open_ocr_text(self, filepath: Path):
        """Retrieve OCR text for the image and open it in the default text editor."""
        text = self.ocr_index.get_text(filepath)
        if not text:
            QMessageBox.information(self, "OCR Text", "No OCR text available for this image.\nIt may not have been indexed yet.")
            return
        # Write to a temp .txt file and open with system text editor
        import tempfile
        txt_path = Path(tempfile.gettempdir()) / f"{filepath.stem}_ocr.txt"
        txt_path.write_text(text, encoding="utf-8")
        try:
            os.startfile(str(txt_path))
        except Exception as e:
            logging.error(f"Failed to open OCR text: {e}")

    def _thumbnail_context_menu(self, filepath: Path, pos: QPoint):
        """Show context menu for thumbnail"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {Theme.BG_LIGHT};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                color: {Theme.TEXT_DARK};
            }}
            QMenu::item:selected {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)

        open_action = menu.addAction("Open Image")
        open_action.triggered.connect(lambda: self._open_image(filepath))

        if OCR_AVAILABLE:
            ocr_action = menu.addAction("Open OCR Text")
            ocr_action.triggered.connect(lambda: self._open_ocr_text(filepath))

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self._edit_image(filepath))

        copy_action = menu.addAction("Copy to Clipboard")
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(filepath))

        menu.addSeparator()

        # Send to submenu
        send_menu = menu.addMenu("Send to...")
        targets = self.config.get('push_targets', [])
        for target in targets:
            if target.get('enabled', True):
                action = send_menu.addAction(target['name'])
                action.triggered.connect(
                    lambda checked, t=target['name'], p=filepath: self._send_to_target(t, p)
                )

        # Move to submenu
        move_menu = menu.addMenu("Move to...")
        folders = self._get_folders()

        if self.current_folder:
            root_action = move_menu.addAction("Root folder")
            root_action.triggered.connect(lambda: self._move_file(filepath, None))

        for folder in folders:
            if folder != self.current_folder:
                action = move_menu.addAction(folder)
                action.triggered.connect(lambda checked, f=folder: self._move_file(filepath, f))

        menu.addSeparator()

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_image(filepath))

        menu.exec(pos)

    def _folder_context_menu(self, folder_name: str, pos: QPoint):
        """Show context menu for folder"""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {Theme.BG_LIGHT};
                border: 1px solid {Theme.BORDER};
                border-radius: 4px;
                padding: 5px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                color: {Theme.TEXT_DARK};
            }}
            QMenu::item:selected {{
                background: {Theme.ACCENT};
                color: white;
            }}
        """)

        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self._rename_folder(folder_name))

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_folder(folder_name))

        menu.exec(pos)

    def _create_folder(self):
        """Create a new folder"""
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            folder_path = self.save_dir / name
            try:
                folder_path.mkdir(exist_ok=True)
                self._refresh_folder_bar()
                self._set_status(f"Created folder: {name}")
            except Exception as e:
                StyledDialog.warning(self, "Error", f"Failed to create folder: {e}")

    def _rename_folder(self, folder_name: str):
        """Rename a folder"""
        new_name, ok = QInputDialog.getText(self, "Rename Folder", "New name:", text=folder_name)
        if ok and new_name and new_name != folder_name:
            old_path = self.save_dir / folder_name
            new_path = self.save_dir / new_name
            try:
                shutil.move(str(old_path), str(new_path))
                if self.current_folder == folder_name:
                    self.current_folder = new_name
                    self._update_current_folder_label()
                self._refresh_folder_bar()
                self._refresh_gallery()
                self._set_status(f"Renamed folder to: {new_name}")
            except Exception as e:
                StyledDialog.warning(self, "Error", f"Failed to rename folder: {e}")

    def _delete_folder(self, folder_name: str):
        """Delete a folder"""
        reply = StyledDialog.question(self, "Delete Folder", f"Delete folder '{folder_name}' and all its contents?")
        if reply:
            folder_path = self.save_dir / folder_name
            try:
                shutil.rmtree(str(folder_path))
                if self.current_folder == folder_name:
                    self.current_folder = None
                    self._update_current_folder_label()
                self._refresh_folder_bar()
                self._refresh_gallery()
                self._set_status(f"Deleted folder: {folder_name}")
            except Exception as e:
                StyledDialog.warning(self, "Error", f"Failed to delete folder: {e}")

    def _move_file(self, filepath: Path, target_folder: Optional[str]):
        """Move file to target folder"""
        if target_folder:
            target = self.save_dir / target_folder / filepath.name
        else:
            target = self.save_dir / filepath.name

        try:
            source = filepath

            # No-op if dropping into the same location.
            try:
                if source.resolve() == target.resolve():
                    self._set_status("Already in selected folder")
                    return
            except Exception:
                pass

            target.parent.mkdir(parents=True, exist_ok=True)

            # Preserve existing target files by using a unique destination name.
            if target.exists():
                stem = target.stem
                suffix = target.suffix
                i = 1
                while True:
                    candidate = target.with_name(f"{stem}_{i}{suffix}")
                    if not candidate.exists():
                        target = candidate
                        break
                    i += 1

            # Prefer atomic rename/replace on same filesystem; fallback to copy+delete.
            moved = False
            try:
                os.replace(str(source), str(target))
                moved = True
            except OSError:
                shutil.copy2(str(source), str(target))
                if source.exists():
                    source.unlink()
                moved = not source.exists()

            # Final safeguard: if source still exists after "move", remove it.
            if source.exists() and source != target:
                source.unlink(missing_ok=True)

            if not moved and source.exists():
                raise RuntimeError("Move failed: source still exists")

            self._invalidate_thumbnail_cache(filepath)
            self._invalidate_thumbnail_cache(target)
            self._refresh_folder_bar()
            self._refresh_gallery()
            self._set_status(f"Moved to: {target_folder or 'root'}")
        except Exception as e:
            StyledDialog.warning(self, "Error", f"Failed to move file: {e}")

    def _move_to_folder(self, folder_name: Optional[str], source_path: Path):
        """Handle file drop on folder"""
        self._move_file(source_path, folder_name)

    def _delete_image(self, filepath: Path):
        """Delete an image"""
        reply = StyledDialog.question(self, "Delete Screenshot", f"Delete {filepath.name}?")
        if reply:
            try:
                file_size = filepath.stat().st_size if filepath.exists() else 0
                filepath.unlink()
                self._invalidate_thumbnail_cache(filepath)

                if OCR_AVAILABLE:
                    self.ocr_index.remove_file(filepath)

                if not self._remove_thumbnail_from_gallery(filepath):
                    self._refresh_gallery()

                self._cached_storage_bytes = max(0, (self._cached_storage_bytes or 0) - file_size)
                self._update_disk_usage()

                # Folder preview strip needs updating, but keep delete interaction snappy.
                QTimer.singleShot(0, self._refresh_folder_bar)

                self._set_status("Screenshot deleted")
            except Exception as e:
                StyledDialog.warning(self, "Error", f"Failed to delete: {e}")

    def _edit_image(self, filepath: Path):
        """Open image in editor"""
        pixmap = QPixmap(str(filepath))
        if pixmap.isNull():
            StyledDialog.warning(self, "Error", "Failed to load image")
            return

        editor = ScreenshotEditor(pixmap)
        editor.editing_complete.connect(lambda p: self._save_edited(p, filepath))
        self._open_editor(editor)

    def _open_editor(self, editor: 'ScreenshotEditor'):
        """Show an editor as a window of its own, beside any already open."""
        # Open editors are held here; dropping the last reference would destroy the window.
        self._editors.append(editor)

        def _forget(*_args, editor=editor):
            # After the editor has closed itself: let it go and free the window.
            def _drop():
                if editor in self._editors:
                    self._editors.remove(editor)
                if editor in self._editors_hidden_for_capture:
                    self._editors_hidden_for_capture.remove(editor)
                editor.deleteLater()
            QTimer.singleShot(0, _drop)

        editor.editing_complete.connect(_forget)
        editor.editing_cancelled.connect(_forget)

        # Every editor opens centred: step a new one down-right off any editor in the same
        # place, so the one underneath can still be seen.
        pos = editor.pos()
        screen = QApplication.primaryScreen().availableGeometry()
        taken = [e.pos() for e in self._editors if e is not editor and e.isVisible()]
        for _ in range(12):
            if not any(abs(p.x() - pos.x()) < 16 and abs(p.y() - pos.y()) < 16 for p in taken):
                break
            # A full-screen capture's editor has no room below: step it sideways instead.
            for step in (QPoint(32, 32), QPoint(32, 0), QPoint(0, 32)):
                nxt = pos + step
                if (nxt.x() + editor.width() <= screen.right() + 1
                        and nxt.y() + editor.height() <= screen.bottom() + 1):
                    break
            else:
                break
            pos = nxt
        editor.move(pos)

        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _save_edited(self, pixmap: QPixmap, filepath: Path):
        """Save edited image back to file and copy it to the clipboard."""
        try:
            self._copy_pixmap_to_clipboard(pixmap)
            copied = True
        except Exception as e:
            logging.error(f"Clipboard copy of edited image failed: {e}")
            copied = False

        # Written in the background like a capture; it waits for the capture's own write of
        # the same file (the editor can open before that write has finished).
        path = str(filepath)
        image = pixmap.toImage()
        before = self._save_threads.get(path)

        def _write(image=image, path=path, before=before):
            if before is not None:
                before.join()
            try:
                old_size = os.path.getsize(path) if os.path.exists(path) else 0
                # Written beside it and swapped in, so the gallery or OCR never reads a half-written
                # file. Windows refuses the swap while another program has the file open: retry, then
                # write in place.
                tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".edit-tmp")
                ok = image.save(tmp, "PNG")
                if ok:
                    for _ in range(20):
                        try:
                            os.replace(tmp, path)
                            break
                        except PermissionError:
                            time.sleep(0.1)
                    else:
                        ok = image.save(path, "PNG")
                        try:
                            os.remove(tmp)
                        except OSError:
                            pass
                delta = (os.path.getsize(path) - old_size) if ok else 0
            except Exception as e:
                logging.error(f"Failed to save edited image {path}: {e}")
                ok, delta = False, 0
            self.edit_written.emit(path, ok, delta)

        t = threading.Thread(target=_write, name="otterly-save-edit", daemon=False)
        self._save_threads[path] = t
        t.start()
        self._set_status("Edited image copied to clipboard" if copied else "Saving edited image...")

    def _on_edit_written(self, path_str: str, ok: bool, delta: int):
        """Background write of an edited image finished."""
        self._save_threads = {p: t for p, t in self._save_threads.items() if t.is_alive()}
        filepath = Path(path_str)
        if not ok:
            StyledDialog.warning(self, "Error", f"Failed to save: {filepath.name}")
            return
        if self._cached_storage_bytes is not None:
            self._cached_storage_bytes += delta
        self._invalidate_thumbnail_cache(filepath)
        self._refresh_gallery()
        self._set_status(f"Edited image saved: {filepath.name} (copied to clipboard)")
        if OCR_AVAILABLE:
            self._start_ocr(filepath)    # the edit may have added text

    def _copy_to_clipboard(self, filepath: Path):
        """Copy image to clipboard"""
        try:
            img = Image.open(str(filepath))
            self._copy_pil_to_clipboard(img)
            self._set_status("Copied to clipboard")
        except Exception as e:
            StyledDialog.warning(self, "Error", f"Failed to copy: {e}")

    def _copy_pil_to_clipboard(self, img: Image.Image):
        """Copy PIL image to Windows clipboard"""
        output = BytesIO()
        img.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Remove BMP header
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def _copy_pixmap_to_clipboard(self, pixmap: QPixmap):
        """Copy QPixmap directly to Windows clipboard (faster than going through disk)"""
        # Convert QPixmap to QImage
        image = pixmap.toImage()
        if image.format() != QImage.Format.Format_RGB32:
            image = image.convertToFormat(QImage.Format.Format_RGB32)

        width = image.width()
        height = image.height()

        # Create BMP data (DIB format for clipboard)
        # DIB is bottom-up: flip once in Qt instead of copying row by row in Python.
        # (RGB32 rows are always width * 4 bytes, so the buffer needs no repacking.)
        flipped = image.mirrored(False, True)
        ptr = flipped.constBits()
        ptr.setsize(flipped.sizeInBytes())
        data = bytes(ptr)

        # Create BITMAPINFOHEADER
        header = struct.pack('<IiiHHIIiiII',
            40,           # biSize
            width,        # biWidth
            height,       # biHeight
            1,            # biPlanes
            32,           # biBitCount
            0,            # biCompression (BI_RGB)
            len(data),    # biSizeImage
            0,            # biXPelsPerMeter
            0,            # biYPelsPerMeter
            0,            # biClrUsed
            0             # biClrImportant
        )

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, header + data)
        win32clipboard.CloseClipboard()

    def _update_disk_usage(self):
        """Update disk usage display"""
        if self._cached_storage_bytes is None:
            total = 0
            if self.save_dir.exists():
                for f in self.save_dir.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
            self._cached_storage_bytes = total
        else:
            total = self._cached_storage_bytes

        mb = total / (1024 * 1024)
        limit = self.config.get('disk_limit_mb', 500)
        self.disk_label.setText(f"Storage: {mb:.1f} / {limit} MB")

    def _set_status(self, message: str):
        """Update status bar"""
        self.status_bar.setText(message)

    def _register_hotkeys(self):
        """Register global hotkeys"""
        try:
            keyboard.remove_all_hotkeys()
        except Exception:
            pass
        try:
            keyboard.add_hotkey('ctrl+shift+s', self._hotkey_fullscreen)
            keyboard.add_hotkey('ctrl+shift+r', self._hotkey_region)
            keyboard.add_hotkey('ctrl+shift+w', self._hotkey_window)
            keyboard.add_hotkey(LIVE_HOTKEY, self._hotkey_live_typing)
        except Exception as e:
            logging.error(f"Failed to register hotkeys: {e}")

    def _register_hotkeys_nonblocking(self):
        """Register hotkeys without blocking initial UI startup."""
        threading.Thread(target=self._register_hotkeys, daemon=True).start()

    def _hotkey_fullscreen(self):
        """Hotkey callback for fullscreen capture"""
        QTimer.singleShot(0, self._capture_fullscreen)

    def _hotkey_region(self):
        """Hotkey callback for region capture"""
        QTimer.singleShot(0, self._start_region_capture)

    def _hotkey_window(self):
        """Hotkey callback for window capture"""
        QTimer.singleShot(0, self._start_window_capture)

    def _hotkey_live_typing(self):
        """Ctrl+Shift+Space: start or stop voice typing (a signal carries it to the UI thread)."""
        self.live_typing_requested.emit()

    def _start_region_capture(self):
        """Start region capture"""
        if self.capture_in_progress:
            return
        self.capture_in_progress = True

        delay = self.config.get('delay', 0)
        if delay > 0:
            self.countdown = DelayCountdown(delay)
            self.countdown.countdown_complete.connect(self._do_region_capture)
            self.countdown.countdown_cancelled.connect(self._capture_cancelled)
            self.countdown.show()
        else:
            QTimer.singleShot(50, self._do_region_capture)

    def _do_region_capture(self):
        """Execute region capture"""
        self._prepare_capture_ui()
        QTimer.singleShot(240, self._show_region_selector)

    def _show_region_selector(self):
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self._on_region_captured)
        self.region_selector.cancelled.connect(self._capture_cancelled)
        self.region_selector.show()

    def _on_region_captured(self, rect: QRect, pixmap: QPixmap):
        """Handle captured region"""
        self._process_capture(pixmap)

    def _capture_fullscreen(self):
        """Capture full screen"""
        if self.capture_in_progress:
            return
        self.capture_in_progress = True

        delay = self.config.get('delay', 0)
        if delay > 0:
            self.countdown = DelayCountdown(delay)
            self.countdown.countdown_complete.connect(self._do_fullscreen_capture)
            self.countdown.countdown_cancelled.connect(self._capture_cancelled)
            self.countdown.show()
        else:
            QTimer.singleShot(50, self._do_fullscreen_capture)

    def _do_fullscreen_capture(self):
        """Execute fullscreen capture"""
        self._prepare_capture_ui()
        QTimer.singleShot(240, self._capture_fullscreen_after_hide)

    def _capture_fullscreen_after_hide(self):
        """Capture full screen once app windows are fully hidden."""
        with mss.mss() as sct:
            pixmap = grab_to_pixmap(sct, sct.monitors[0])
        self._process_capture(pixmap)

    def _start_window_capture(self):
        """Start window capture"""
        if self.capture_in_progress:
            return
        self.capture_in_progress = True

        QTimer.singleShot(50, self._do_window_capture)

    def _do_window_capture(self):
        """Execute window capture selection"""
        self._prepare_capture_ui()
        self.window_selector = WindowSelector()
        self.window_selector.window_selected.connect(self._capture_window)
        self.window_selector.cancelled.connect(self._capture_cancelled)
        self.window_selector.show()

    def _prepare_capture_ui(self):
        """Hide app windows before any capture so they never bleed into screenshots."""
        self._main_was_visible_before_capture = self.isVisible()
        self._floating_bar_was_visible_before_capture = bool(
            self.floating_bar and self.floating_bar.isVisible()
        )

        if self._floating_bar_was_visible_before_capture:
            self.floating_bar.hide()
        if self.isVisible():
            self.hide()

        # The voice typing strip stays out of the shot too.
        strip = getattr(getattr(self, '_live_typing', None), 'strip', None)
        if strip is not None and strip.isVisible():
            strip.hide()
            self._live_strip_hidden_for_capture = True

        # Open editors leave the screen for the capture and come back, as they were, after it.
        for ed in self._editors:
            if ed.isVisible() and not ed.isMinimized() and ed not in self._editors_hidden_for_capture:
                self._editors_hidden_for_capture.append(ed)
                ed.hide()

        # Safety: hide any stray top-level Otterly windows that might still be shown.
        for w in QApplication.topLevelWidgets():
            if not w.isVisible():
                continue
            try:
                title = (w.windowTitle() or "").lower()
            except Exception:
                title = ""
            if w is self or w is self.floating_bar or "otterly" in title:
                try:
                    w.hide()
                except Exception:
                    pass

        QApplication.processEvents()
        # Let Windows compositor commit hidden-state changes before capture.
        if sys.platform == "win32":
            try:
                ctypes.windll.dwmapi.DwmFlush()
            except Exception:
                pass

    def _restore_capture_ui(self):
        """Restore app windows after a capture flow finishes or is cancelled."""
        if not self.config.get('silent_capture', False):
            self.show()

        if (
            self.config.get('floating_bar_visible', True)
            and self.floating_bar
            and self._floating_bar_was_visible_before_capture
        ):
            QTimer.singleShot(120, self.floating_bar.show)

        if self._live_strip_hidden_for_capture:
            self._live_strip_hidden_for_capture = False
            strip = self._live_typing.strip
            if strip is not None and self._live_typing.active:
                strip.show()

        # The editors that were open before the capture, back where they were.
        hidden, self._editors_hidden_for_capture = self._editors_hidden_for_capture, []
        for ed in hidden:
            if ed in self._editors:
                ed.show()

        self._main_was_visible_before_capture = False
        self._floating_bar_was_visible_before_capture = False

    def _capture_window(self, hwnd: int):
        """Capture specific window"""
        try:
            # Get window rect - already physical coords in DPI-aware process (PyQt6)
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            w = x2 - x
            h = y2 - y

            # Pass physical coords directly to mss (both use physical pixels)
            with mss.mss() as sct:
                pixmap = grab_to_pixmap(sct, {"left": x, "top": y, "width": w, "height": h})
            self._process_capture(pixmap)
        except Exception as e:
            logging.error(f"Window capture failed: {e}")
            self._capture_cancelled()

    def _capture_cancelled(self):
        """Handle capture cancellation"""
        self.capture_in_progress = False
        self._restore_capture_ui()
        self._set_status("Capture cancelled")

    def _process_capture(self, pixmap: QPixmap):
        """Process captured screenshot"""
        if self.config.get('edit_before_save', True):
            # The capture is over once its editor is up: the next capture may start while this
            # editor is open, and opens an editor of its own.
            self.capture_in_progress = False
            self._restore_capture_ui()
            editor = ScreenshotEditor(pixmap)
            editor.capture_unsaved = True      # closing it loses the capture: it asks first
            editor.editing_complete.connect(lambda p: self._save_screenshot(p, from_editor=True))
            editor.editing_cancelled.connect(self._edit_before_save_cancelled)
            self._open_editor(editor)
        else:
            self._save_screenshot(pixmap)

    def _edit_before_save_cancelled(self):
        """An editor opened before saving was closed without saving."""
        self._set_status("Capture cancelled")

    def _save_screenshot(self, pixmap: QPixmap, from_editor: bool = False):
        """Save screenshot to disk"""
        if not from_editor:
            self.capture_in_progress = False

        # Copy to clipboard FIRST (instant feedback)
        self._copy_pixmap_to_clipboard(pixmap)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

        # Determine save path
        if self.current_folder:
            save_path = self.save_dir / self.current_folder / filename
            save_path.parent.mkdir(exist_ok=True)
        else:
            save_path = self.save_dir / filename

        # Two captures in the same second must not write the same file.
        i = 1
        while save_path.exists() or str(save_path) in self._pending_save_paths:
            save_path = save_path.with_name(f"screenshot_{timestamp}_{i}.png")
            i += 1
        filename = save_path.name

        # Save to disk in the background: PNG-encoding a full screen takes ~1 s and used to
        # freeze the window. The gallery, folder bar and OCR follow in _on_screenshot_written.
        self._pending_save_paths.add(str(save_path))
        image = pixmap.toImage()

        def _write(image=image, path=str(save_path)):
            try:
                ok = image.save(path, "PNG")
            except Exception as e:
                logging.error(f"Failed to save screenshot {path}: {e}")
                ok = False
            self.screenshot_written.emit(path, ok)

        t = threading.Thread(target=_write, name="otterly-save", daemon=False)
        self._save_threads[str(save_path)] = t
        t.start()

        # Update state
        self.session_count += 1
        self.session_label.setText(f"Screenshots: {self.session_count}")

        # Show notification immediately
        self.toast = ToastNotification(pixmap, filename)
        self._set_status(f"Saved: {filename}")

        # Show window if not silent (not while another capture, started from an open editor, runs)
        if not self.capture_in_progress:
            self._restore_capture_ui()

        # Auto-send: desktop override (from FloatingBar) takes priority over config
        target = self._desktop_target_override or (
            self.config.get('auto_send_target', '')
            if self.config.get('auto_send_enabled', False) else ''
        )
        self._desktop_target_override = None  # consume override

        # Edit after save (not when the editor already ran before the save). Saving the edit
        # overwrites this file and copies it to the clipboard; closing the editor keeps the
        # capture as it was. An auto-send waits for the editor so the edited image is sent.
        if self.config.get('edit_after_save', True) and not self.config.get('edit_before_save', True):
            self._open_editor_after_save(pixmap, save_path, target)
            return
        if target:
            QTimer.singleShot(500, lambda t=target: self._send_to_target(t))

    def _open_editor_after_save(self, pixmap: QPixmap, save_path: Path, target: str = ''):
        editor = ScreenshotEditor(pixmap)

        def _done_edit(p, save_path=save_path, target=target):
            self._save_edited(p, save_path)
            if target:
                QTimer.singleShot(500, lambda t=target: self._send_to_target(t))

        def _closed(target=target):
            if target:
                QTimer.singleShot(500, lambda t=target: self._send_to_target(t))

        editor.editing_complete.connect(_done_edit)
        editor.editing_cancelled.connect(_closed)
        self._open_editor(editor)

    def _on_screenshot_written(self, path_str: str, ok: bool):
        """Background PNG write finished: update storage, gallery, folder bar and OCR."""
        self._pending_save_paths.discard(path_str)
        self._save_threads = {p: t for p, t in self._save_threads.items() if t.is_alive()}
        save_path = Path(path_str)
        if not ok:
            self._set_status(f"Failed to save: {save_path.name}")
            return
        self._invalidate_thumbnail_cache(save_path)

        # Keep storage usage cache in sync without rescanning entire folder tree.
        try:
            self._cached_storage_bytes = (self._cached_storage_bytes or 0) + save_path.stat().st_size
        except Exception:
            self._cached_storage_bytes = None

        self._refresh_folder_bar()
        self._refresh_gallery()

        # Fire OCR in background
        if OCR_AVAILABLE:
            self._start_ocr(save_path)

    def _inject_desktop_target(self):
        """
        Before a floating-bar capture: look at the current virtual desktop,
        find the topmost visible window that matches a push_target pattern,
        and temporarily enable auto-send to it.
        Resets after the next capture completes via _save_screenshot.
        """
        if not PYVDA_AVAILABLE:
            return
        try:
            desktop = VirtualDesktop.current()
            # apps_by_z_order() returns windows top→bottom on current desktop
            apps = desktop.apps_by_z_order()
            targets = self.config.get('push_targets', [])
            for app in apps:
                try:
                    title = win32gui.GetWindowText(app.hwnd).lower()
                except Exception:
                    continue
                if not title:
                    continue
                # Skip our own windows
                if 'otterly screenshots' in title:
                    continue
                for target in targets:
                    pattern = target.get('title_pattern', '').lower()
                    if not pattern:
                        continue
                    if any(p.strip() in title for p in pattern.split('|')):
                        # Found a match — enable auto-send to this target for next capture
                        self._desktop_target_override = target['name']
                        logging.info(f"FloatingBar: auto-send override → {target['name']} ({title})")
                        return
            # No match found — clear override
            self._desktop_target_override = None
        except Exception as e:
            logging.error(f"_inject_desktop_target failed: {e}")
            self._desktop_target_override = None

    def _start_ocr(self, filepath: Path):
        """Start a background OCR worker for a newly saved screenshot."""
        worker = OcrWorker(filepath, self.ocr_index)
        worker.finished.connect(self._on_ocr_done)
        self._ocr_workers.append(worker)
        worker.start()

    def _on_ocr_done(self, filepath: str, text: str):
        """Called when OCR finishes — clean up worker ref."""
        self._ocr_workers = [w for w in self._ocr_workers if w.isRunning()]
        # If user is actively searching, refresh gallery so new result can appear
        if self._search_query:
            self._refresh_gallery()

    def _send_to_target(self, target_name: str, filepath: Path = None):
        """Send screenshot to target application"""
        targets = self.config.get('push_targets', [])
        target = next((t for t in targets if t.get('name') == target_name), None)

        if not target:
            return

        # Copy image to clipboard first if filepath provided
        if filepath:
            try:
                img = Image.open(str(filepath))
                self._copy_pil_to_clipboard(img)
            except Exception as e:
                self._set_status(f"Failed to copy image: {e}")
                return

        pattern = target.get('title_pattern', '').lower()

        # Find window
        def find_window(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                for p in pattern.split('|'):
                    if p in title:
                        results.append(hwnd)
            return True

        results = []
        win32gui.EnumWindows(find_window, results)

        if not results:
            self._set_status(f"'{target_name}' window not found")
            return

        hwnd = results[0]
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Activate window
            win32gui.SetForegroundWindow(hwnd)

            def _paste_hotkey():
                try:
                    keyboard.press_and_release('ctrl+v')
                except Exception as e:
                    logging.error(f"Failed to trigger paste hotkey: {e}")

            QTimer.singleShot(300, _paste_hotkey)
            self._set_status(f"Sent to {target_name}")
        except Exception as e:
            logging.error(f"Failed to send to target: {e}")
            self._set_status(f"Send to {target_name} failed")

    def _import_image(self):
        """Import image from file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import Image",
            str(Path.home() / "Pictures"),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if filepath:
            try:
                img = Image.open(filepath)

                # Convert to QPixmap
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)

                self._process_capture(pixmap)
            except Exception as e:
                StyledDialog.warning(self, "Error", f"Failed to import: {e}")

    def _paste_from_clipboard(self):
        """Paste image from clipboard"""
        try:
            img = ImageGrab.grabclipboard()
            if img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                data = img.tobytes("raw", "RGB")
                qimage = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(qimage)

                self._process_capture(pixmap)
            else:
                StyledDialog.info(self, "Clipboard", "No image in clipboard")
        except Exception as e:
            StyledDialog.warning(self, "Error", f"Failed to paste: {e}")

    def _show_settings(self):
        """Show settings dialog"""
        old_theme = self.config.get('theme', 'solarized_dark')
        old_pin = self.config.get('pin_to_all_desktops', False)
        old_thumb_scale = self.config.get('thumbnail_scale', 5)
        old_folder_thumb_scale = self.config.get('folder_thumbnail_scale', 5)
        old_save_dir = Path(self.config.get('save_dir', SAVE_DIR))
        dialog = SettingsDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_config()
            self._save_config()

            new_save_dir = Path(self.config.get('save_dir', SAVE_DIR))
            if new_save_dir != old_save_dir:
                self.save_dir = new_save_dir
                self.save_dir.mkdir(parents=True, exist_ok=True)
                self.ocr_index = OcrIndex(self.save_dir / "ocr_index.db")
                self._cached_storage_bytes = None
                self._invalidate_thumbnail_cache()
                self._last_gallery_images = []

            # Check if theme changed
            new_theme = self.config.get('theme', 'solarized_dark')
            if new_theme != old_theme:
                self._apply_theme(new_theme)

            # Check if pin setting changed
            new_pin = self.config.get('pin_to_all_desktops', False)
            if new_pin != old_pin:
                if new_pin:
                    self._pin_to_all_desktops()
                else:
                    self._unpin_from_all_desktops()

            # Show/hide floating bar per setting
            if self.config.get('floating_bar_visible', True):
                self._ensure_floating_bar()
            else:
                if self.floating_bar is not None:
                    self.floating_bar.hide()

            thumb_changed = self.config.get('thumbnail_scale', 5) != old_thumb_scale
            folder_thumb_changed = self.config.get('folder_thumbnail_scale', 5) != old_folder_thumb_scale

            if folder_thumb_changed or new_save_dir != old_save_dir:
                self._refresh_folder_bar()

            if thumb_changed:
                # Rebuild visible thumbnails from cached list to avoid expensive rescan on size-only change.
                self._refresh_gallery(use_cached_images=True)
            else:
                self._refresh_gallery()

            self._set_status("Settings saved")

    def _apply_theme(self, theme_key: str):
        """Apply a new theme to the application"""
        set_active_theme(theme_key)

        # Update main stylesheet
        if self._use_minimal_styles:
            self.setStyleSheet("")
        else:
            self.setStyleSheet(generate_stylesheet())

        # Update container background
        container = self.centralWidget()
        if container:
            container.setStyleSheet(f"background: {Theme.BG_GALLERY};")

        # Update gallery widget background
        if hasattr(self, 'gallery_widget'):
            self.gallery_widget.setStyleSheet(f"background: {Theme.BG_GALLERY};")

        # Rebuild sidebar and title bar (they have inline styles)
        self._rebuild_sidebar()
        self._rebuild_title_bar()

    def _rebuild_sidebar(self):
        """Rebuild sidebar with current theme"""
        if self._use_minimal_styles:
            return
        # Find the splitter
        splitter = None
        for child in self.centralWidget().children():
            if isinstance(child, QSplitter):
                splitter = child
                break

        if splitter and splitter.count() > 0:
            old_sidebar = splitter.widget(0)
            new_sidebar = self._create_sidebar()
            splitter.replaceWidget(0, new_sidebar)
            old_sidebar.deleteLater()

    def _rebuild_title_bar(self):
        """Rebuild title bar with current theme"""
        if self._use_minimal_styles:
            return
        main_layout = self.centralWidget().layout()
        if main_layout and main_layout.count() > 0:
            old_title_bar = main_layout.itemAt(0).widget()
            if isinstance(old_title_bar, (CustomTitleBar, SimpleTitleBar)):
                if self._use_frameless_main_window:
                    new_title_bar = CustomTitleBar(self, show_window_controls=True)
                else:
                    new_title_bar = SimpleTitleBar(self)
                new_title_bar.search_edit.textChanged.connect(self._on_search_changed)
                main_layout.replaceWidget(old_title_bar, new_title_bar)
                self.title_bar = new_title_bar
                old_title_bar.deleteLater()

    def _show_about(self):
        """Show about dialog"""
        about = QDialog(self)
        about.setWindowTitle("About")
        about.setFixedSize(300, 250)
        about.setStyleSheet(f"background: {Theme.BG_LIGHT};")

        layout = QVBoxLayout(about)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Logo
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            logo = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio)
            logo.setPixmap(scaled)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)

        # Title
        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_DARK};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version = QLabel(f"Version {APP_VERSION}")
        version.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Description
        desc = QLabel("A modern screenshot utility\nfor Windows")
        desc.setStyleSheet(f"color: {Theme.TEXT_GRAY};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background: #2AA198;
            }}
        """)
        close_btn.clicked.connect(about.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        about.exec()

    def resizeEvent(self, event):
        """Handle window resize"""
        super().resizeEvent(event)
        # Re-flow the existing thumbnails once the drag settles (no rescan, no rebuild).
        if hasattr(self, '_reflow_timer'):
            self._reflow_timer.start()

    def _pin_to_all_desktops(self):
        """Pin the window to appear on all virtual desktops"""
        if not PYVDA_AVAILABLE:
            self._set_status("Install pyvda for virtual desktop pinning")
            return False

        try:
            hwnd = int(self.winId())
            view = AppView(hwnd)
            view.pin()
            self._set_status("Pinned to all virtual desktops")
            return True
        except Exception as e:
            logging.error(f"Pin failed: {e}")
            self._set_status("Pin failed - use Win+Tab to pin manually")
            return False

    def _unpin_from_all_desktops(self):
        """Unpin the window from all virtual desktops"""
        if not PYVDA_AVAILABLE:
            return False

        try:
            hwnd = int(self.winId())
            view = AppView(hwnd)
            view.unpin()
            self._set_status("Unpinned from all desktops")
            return True
        except Exception as e:
            logging.error(f"Unpin failed: {e}")
            return False

    def closeEvent(self, event):
        """Handle window close"""
        if self.floating_bar is not None and self.floating_bar.isVisible():
            result = StyledDialog(
                self,
                "Closing Otterly Screenshots",
                "Keep the floating capture bar running?",
                sub="You can still capture screenshots from any desktop.\n"
                    "Reopen the main window anytime by clicking ◎ on the bar.",
                buttons=[
                    ("Keep bar running", "primary"),
                    ("Close everything", "secondary"),
                ]
            ).exec()

            if result == "Keep bar running":
                self.config['floating_bar_visible'] = True
                self._save_config()
                try:
                    keyboard.remove_all_hotkeys()
                except:
                    pass
                event.ignore()
                self.hide()
                return

        # Full quit — unregister hotkeys, close bar too
        try:
            keyboard.remove_all_hotkeys()
        except:
            pass
        if self.floating_bar is not None:
            self.floating_bar.close()

        self._save_config()
        event.accept()


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    _trace_startup("main start")
    app = QApplication(sys.argv)
    _trace_startup("QApplication created")
    app.setApplicationName(APP_NAME)

    # Set app icon
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        app.setWindowIcon(QIcon(str(logo_path)))

    try:
        print("[Otterly] Creating main window...", flush=True)
        window = MainWindow()
        _trace_startup("MainWindow instance created")
        print("[Otterly] Showing main window...", flush=True)
        _trace_startup("About to call MainWindow.show")
        window.show()
        _trace_startup("MainWindow show called")
        print("[Otterly] Main window shown. Scheduling floating bar...", flush=True)
        QTimer.singleShot(600, window._ensure_floating_bar)
        QTimer.singleShot(1200, window._register_hotkeys_nonblocking)
        _trace_startup("Delayed hotkey registration scheduled")
        # Ensure the main window is brought to the foreground on startup.
        QTimer.singleShot(300, window.showNormal)
        QTimer.singleShot(350, window.raise_)
        QTimer.singleShot(400, window.activateWindow)
        print("[Otterly] Entering event loop. App is running.", flush=True)
        _trace_startup("Entering app.exec")
        sys.exit(app.exec())
    except Exception as e:
        _trace_startup(f"main exception: {e}")
        logging.error(f"Application error: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()
