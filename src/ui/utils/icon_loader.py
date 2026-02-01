"""
IconLoader - Load application icons from .desktop files and icon themes
Uses CairoSVG to render SVG icons to PNG for Tkinter display
"""

import os
import glob
import subprocess
import io
from pathlib import Path
from typing import Optional, Dict

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import cairosvg
    HAS_CAIROSVG = True
except ImportError:
    HAS_CAIROSVG = False


class IconLoader:
    """
    Loads application icons from the system using SVG with CairoSVG.
    Searches .desktop files and icon themes.
    """

    # Standard .desktop file locations
    DESKTOP_DIRS = [
        '/usr/share/applications',
        '/usr/local/share/applications',
        os.path.expanduser('~/.local/share/applications'),
        '/var/lib/flatpak/exports/share/applications',
        os.path.expanduser('~/.local/share/flatpak/exports/share/applications'),
        '/var/lib/snapd/desktop/applications',
    ]

    # Icon theme directories
    ICON_DIRS = [
        '/usr/share/icons',
        '/usr/local/share/icons',
        os.path.expanduser('~/.local/share/icons'),
        '/usr/share/pixmaps',
    ]

    # Preferred icon sizes (scalable first for SVG)
    ICON_SIZES = ['scalable', '256x256', '128x128', '64x64', '48x48', '32x32', '24x24']

    # Icon categories to search
    ICON_CATEGORIES = ['apps', 'applications', 'places', 'mimetypes', 'legacy']

    def __init__(self, size: int = 20):
        """
        Initialize the icon loader.

        Args:
            size: Target icon size in pixels
        """
        self.size = size
        self._cache: Dict[str, Optional[any]] = {}  # name -> PhotoImage or None
        self._desktop_cache: Dict[str, Optional[str]] = {}  # name -> icon_name or None
        self._icon_theme = self._get_icon_theme()
        self._build_desktop_index()

    def _get_icon_theme(self) -> str:
        """Get the current icon theme name"""
        # Try gsettings first (GNOME)
        try:
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'icon-theme'],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                theme = result.stdout.strip().strip("'\"")
                if theme:
                    return theme
        except:
            pass

        # Try KDE
        try:
            kde_config = os.path.expanduser('~/.config/kdeglobals')
            if os.path.exists(kde_config):
                with open(kde_config, 'r') as f:
                    for line in f:
                        if line.startswith('Theme='):
                            return line.split('=')[1].strip()
        except:
            pass

        # Fallback to common themes
        for theme in ['breeze', 'Adwaita', 'hicolor', 'Papirus']:
            theme_path = f'/usr/share/icons/{theme}'
            if os.path.exists(theme_path):
                return theme

        return 'hicolor'

    def _build_desktop_index(self):
        """Build an index of process names to .desktop files"""
        self._desktop_index: Dict[str, str] = {}  # lowercase name -> icon name

        for desktop_dir in self.DESKTOP_DIRS:
            if not os.path.exists(desktop_dir):
                continue

            for desktop_file in glob.glob(os.path.join(desktop_dir, '*.desktop')):
                try:
                    exec_name = None
                    icon_name = None
                    app_name = None

                    with open(desktop_file, 'r', errors='ignore') as f:
                        in_desktop_entry = False
                        for line in f:
                            line = line.strip()
                            if line == '[Desktop Entry]':
                                in_desktop_entry = True
                                continue
                            if line.startswith('[') and line.endswith(']'):
                                in_desktop_entry = False
                                continue
                            if not in_desktop_entry:
                                continue

                            if line.startswith('Exec='):
                                exec_val = line[5:].strip()
                                exec_parts = exec_val.split()
                                if exec_parts:
                                    exec_name = os.path.basename(exec_parts[0])
                                    if exec_name in ('env', 'bash', 'sh', 'flatpak', 'snap'):
                                        for part in exec_parts[1:]:
                                            if not part.startswith('-') and '=' not in part:
                                                exec_name = os.path.basename(part)
                                                break

                            elif line.startswith('Icon='):
                                icon_name = line[5:].strip()

                            elif line.startswith('Name='):
                                app_name = line[5:].strip()

                    if icon_name:
                        if exec_name:
                            self._desktop_index[exec_name.lower()] = icon_name
                        if app_name:
                            self._desktop_index[app_name.lower()] = icon_name
                        basename = os.path.basename(desktop_file).replace('.desktop', '')
                        self._desktop_index[basename.lower()] = icon_name

                except Exception:
                    continue

    def _find_icon_file(self, icon_name: str) -> Optional[str]:
        """Find the actual icon file path for an icon name (prefers SVG)"""
        if not icon_name:
            return None

        # If it's already an absolute path
        if os.path.isabs(icon_name):
            if os.path.exists(icon_name):
                return icon_name
            return None

        # Check pixmaps (prefer SVG)
        for ext in ['.svg', '.png', '.xpm', '']:
            pixmap_path = f'/usr/share/pixmaps/{icon_name}{ext}'
            if os.path.exists(pixmap_path):
                return pixmap_path

        # Search in icon themes
        themes_to_search = [self._icon_theme, 'hicolor', 'breeze', 'Adwaita', 'AdwaitaLegacy', 'HighContrast']

        for theme in themes_to_search:
            for icon_dir in self.ICON_DIRS:
                theme_path = os.path.join(icon_dir, theme)
                if not os.path.exists(theme_path):
                    continue

                # Search by size (scalable first for SVG)
                for size in self.ICON_SIZES:
                    for category in self.ICON_CATEGORIES:
                        # Prefer SVG, then PNG
                        for ext in ['.svg', '.png', '.xpm']:
                            icon_path = os.path.join(
                                theme_path, size, category, f'{icon_name}{ext}'
                            )
                            if os.path.exists(icon_path):
                                return icon_path

        return None

    def _load_svg(self, svg_path: str) -> Optional[Image.Image]:
        """Load an SVG file and convert to PIL Image using CairoSVG"""
        if not HAS_CAIROSVG:
            return None

        try:
            # Render SVG to PNG in memory at desired size
            png_data = cairosvg.svg2png(
                url=svg_path,
                output_width=self.size,
                output_height=self.size
            )
            # Load PNG data into PIL
            img = Image.open(io.BytesIO(png_data))
            return img
        except Exception:
            return None

    def _load_image(self, icon_path: str) -> Optional[Image.Image]:
        """Load an image file (SVG or raster) into PIL Image"""
        if not HAS_PIL:
            return None

        try:
            if icon_path.endswith('.svg'):
                return self._load_svg(icon_path)
            else:
                img = Image.open(icon_path)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                img = img.resize((self.size, self.size), Image.Resampling.LANCZOS)
                return img
        except Exception:
            return None

    def get_icon(self, process_name: str, root=None) -> Optional[any]:
        """
        Get an icon for a process name.

        Args:
            process_name: The process name (e.g., 'firefox', 'code')
            root: Tkinter root window (needed for PhotoImage)

        Returns:
            A Tkinter PhotoImage or None if not found
        """
        if not HAS_PIL:
            return None

        name_lower = process_name.lower()

        # Check cache first
        if name_lower in self._cache:
            return self._cache[name_lower]

        # Try to find icon name from desktop file
        icon_name = self._desktop_index.get(name_lower)

        # Try variations if not found
        if not icon_name:
            for suffix in ['-bin', '-browser', '-stable', '-beta', '-dev']:
                base_name = name_lower.replace(suffix, '')
                if base_name in self._desktop_index:
                    icon_name = self._desktop_index[base_name]
                    break

        # Try common mappings
        if not icon_name:
            mappings = {
                'chrome': 'google-chrome',
                'chromium-browser': 'chromium',
                'code': 'visual-studio-code',
                'code-oss': 'visual-studio-code',
                'cursor': 'cursor',
                'firefox-esr': 'firefox',
                'thunderbird': 'thunderbird',
                'nautilus': 'org.gnome.Nautilus',
                'gnome-terminal': 'org.gnome.Terminal',
                'konsole': 'utilities-terminal',
                'dolphin': 'org.kde.dolphin',
                'vlc': 'vlc',
                'spotify': 'spotify',
                'discord': 'discord',
                'slack': 'slack',
                'telegram-desktop': 'telegram',
                'steam': 'steam',
            }
            icon_name = mappings.get(name_lower)

        if not icon_name:
            icon_name = name_lower

        # Find the actual icon file
        icon_path = self._find_icon_file(icon_name)

        if not icon_path:
            self._cache[name_lower] = None
            return None

        # Load the image
        img = self._load_image(icon_path)

        if not img:
            self._cache[name_lower] = None
            return None

        # Convert to PhotoImage
        try:
            photo = ImageTk.PhotoImage(img)
            self._cache[name_lower] = photo
            return photo
        except Exception:
            self._cache[name_lower] = None
            return None

    def clear_cache(self):
        """Clear the icon cache"""
        self._cache.clear()
