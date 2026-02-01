"""
WSysMon-inspired Theme Configuration
Dark theme with accent colors matching the original
"""

COLORS = {
    # Background colors
    'bg_primary': '#1a1a1a',
    'bg_secondary': '#242424',
    'bg_tertiary': '#2d2d2d',
    'surface': '#303030',
    'surface_hover': '#3d3d3d',
    'surface_active': '#454545',

    # Accent colors (WSysMon blue-gray)
    'accent': '#4a7895',
    'accent_hover': '#5a8aa8',
    'accent_light': '#2a4455',
    'accent_secondary': '#ae785a',

    # Selection (blended with dark bg since tkinter doesn't support alpha)
    'selection': '#3a5a75',
    'selection_border': '#8bc8ff',

    # Status colors
    'danger': '#e81123',
    'danger_hover': '#ff2737',
    'warning': '#ffa500',
    'success': '#10893e',

    # Text colors
    'text_primary': '#ffffff',
    'text_secondary': '#999999',
    'text_tertiary': '#666666',
    'text_on_accent': '#ffffff',

    # Border
    'border': '#404040',
    'border_light': '#505050',

    # Graph colors (fill colors blended with bg since tkinter doesn't support alpha)
    'graph_line': '#4a7895',
    'graph_fill': '#2a3a45',
    'graph_line_secondary': '#ae785a',
    'graph_fill_secondary': '#3a2a25',
    # CPU - orange
    'graph_line_orange': '#e07020',
    'graph_fill_orange': '#3a2a20',
    # GPU - green
    'graph_line_green': '#7cb342',
    'graph_fill_green': '#2a3a25',
    # Memory - blue/purple
    'graph_line_purple': '#9575cd',
    'graph_fill_purple': '#2a2a3a',
    'graph_grid': '#333333',
    'graph_axis': '#555555',

    # Process bar colors (WSysMon orange gradient)
    'bar_base': '#ffd163',
    'bar_text_light': '#ffffff',
    'bar_text_dark': '#000000',

    # Category colors
    'category_apps': '#4a7895',
    'category_background': '#666666',
    'category_system': '#555555',
}


class Theme:
    """Theme configuration and utilities"""

    # Fonts - using fonts that render cleanly on Linux
    # DejaVu Sans: Best anti-aliasing on Linux, clear at all sizes
    # DejaVu Sans Mono: Matching monospace for numbers
    FONT_FAMILY = 'DejaVu Sans'
    FONT_FAMILY_FALLBACK = 'sans-serif'
    FONT_FAMILY_MONO = 'DejaVu Sans Mono'
    FONT_FAMILY_MONO_FALLBACK = 'monospace'

    # Font sizes (slightly larger for better anti-aliasing)
    FONT_SIZE_TITLE = 26
    FONT_SIZE_HEADER = 17
    FONT_SIZE_SUBHEADER = 15
    FONT_SIZE_BODY = 13
    FONT_SIZE_SMALL = 12
    FONT_SIZE_TINY = 11

    # Spacing
    PADDING_LARGE = 20
    PADDING_MEDIUM = 12
    PADDING_SMALL = 8
    PADDING_TINY = 4

    # Sizes
    SIDEBAR_WIDTH = 260
    BUTTON_HEIGHT = 100
    GRAPH_HEIGHT = 80
    ROW_HEIGHT = 36
    HEADER_HEIGHT = 48

    # Graph settings
    GRAPH_LINE_WIDTH = 3
    GRAPH_HISTORY_SIZE = 60

    # Font availability cache
    _font_available_cache = {}
    # Font tuple cache (key: (size, bold, mono) -> font tuple)
    _font_tuple_cache = {}

    @staticmethod
    def _check_font_available(font_name):
        """Check if a font is available on the system (cached)"""
        if font_name in Theme._font_available_cache:
            return Theme._font_available_cache[font_name]

        try:
            import tkinter as tk
            import tkinter.font as tkfont
            root = tk._default_root
            if root:
                # Cache the family list to avoid repeated lookups
                if not hasattr(Theme, '_font_families'):
                    Theme._font_families = {f.lower() for f in tkfont.families()}
                available = font_name.lower() in Theme._font_families
                Theme._font_available_cache[font_name] = available
                return available
        except:
            pass
        Theme._font_available_cache[font_name] = False
        return False

    @staticmethod
    def get_font(size=None, bold=False):
        """Get font tuple for tkinter (cached for performance)"""
        size = size or Theme.FONT_SIZE_BODY
        cache_key = (size, bold, False)

        if cache_key in Theme._font_tuple_cache:
            return Theme._font_tuple_cache[cache_key]

        weight = 'bold' if bold else 'normal'

        # Try primary font, fall back if not available
        if Theme._check_font_available(Theme.FONT_FAMILY):
            result = (Theme.FONT_FAMILY, size, weight)
        else:
            result = (Theme.FONT_FAMILY_FALLBACK, size, weight)

        Theme._font_tuple_cache[cache_key] = result
        return result

    @staticmethod
    def get_mono_font(size=None, bold=False):
        """Get monospace font tuple (cached for performance)"""
        size = size or Theme.FONT_SIZE_BODY
        cache_key = (size, bold, True)

        if cache_key in Theme._font_tuple_cache:
            return Theme._font_tuple_cache[cache_key]

        weight = 'bold' if bold else 'normal'

        # Try primary mono font, fall back if not available
        if Theme._check_font_available(Theme.FONT_FAMILY_MONO):
            result = (Theme.FONT_FAMILY_MONO, size, weight)
        else:
            result = (Theme.FONT_FAMILY_MONO_FALLBACK, size, weight)

        Theme._font_tuple_cache[cache_key] = result
        return result

    @staticmethod
    def get_bar_alpha(value, scale=40):
        """Calculate alpha for usage bar (WSysMon style)"""
        return min(1.0, 0.1 + (value / scale))

    @staticmethod
    def get_bar_text_color(alpha):
        """Get text color based on bar alpha"""
        return COLORS['bar_text_dark'] if alpha > 0.6 else COLORS['text_primary']

    @staticmethod
    def hex_to_rgb(hex_color):
        """Convert hex color to RGB tuple (0-255)"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def rgb_to_hex(r, g, b):
        """Convert RGB to hex"""
        return f'#{r:02x}{g:02x}{b:02x}'

    @staticmethod
    def blend_color(color1, color2, alpha):
        """Blend two colors"""
        r1, g1, b1 = Theme.hex_to_rgb(color1)
        r2, g2, b2 = Theme.hex_to_rgb(color2)

        r = int(r1 * (1 - alpha) + r2 * alpha)
        g = int(g1 * (1 - alpha) + g2 * alpha)
        b = int(b1 * (1 - alpha) + b2 * alpha)

        return Theme.rgb_to_hex(r, g, b)
