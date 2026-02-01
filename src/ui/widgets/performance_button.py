"""
PerformanceButton - Optimized sidebar button with embedded mini graph
Uses canvas item reuse for better performance
"""

import tkinter as tk
from collections import deque
from ..themes import COLORS, Theme


class PerformanceButton(tk.Frame):
    """
    Optimized button widget for performance sidebar.
    Displays title, info text, and a mini graph with efficient updates.
    """

    def __init__(self, parent, title, icon="", on_click=None,
                 line_color=None, fill_color=None, **kwargs):
        super().__init__(
            parent,
            bg=COLORS['surface'],
            cursor='hand2',
            **kwargs
        )

        self.title = title
        self.icon = icon
        self.on_click = on_click
        self.selected = False

        # Custom graph colors
        self.line_color = line_color or COLORS['graph_line']
        self.fill_color = fill_color or COLORS['graph_fill']

        # Data for mini graph
        self.data = deque(maxlen=30)
        self.max_value = 100

        # Cache widgets for fast bg updates (avoid winfo_children traversal)
        self._bg_widgets = []

        # Canvas item IDs for graph (avoid delete/recreate)
        self._graph_fill = None
        self._graph_line = None
        self._graph_initialized = False
        self._graph_dirty = True

        # Cache fonts
        self._font_subheader_bold = Theme.get_font(Theme.FONT_SIZE_SUBHEADER, bold=True)
        self._font_header_bold = Theme.get_font(Theme.FONT_SIZE_HEADER, bold=True)
        self._font_tiny = Theme.get_font(Theme.FONT_SIZE_TINY)

        # Configure height only - width will fill parent
        self.configure(height=Theme.BUTTON_HEIGHT)
        self.pack_propagate(False)

        self._create_widgets()
        self._bind_events()

    def _create_widgets(self):
        """Create button contents"""
        # Main container
        content = tk.Frame(self, bg=COLORS['surface'])
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Left side: Title and info
        left_frame = tk.Frame(content, bg=COLORS['surface'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Title with optional icon
        title_text = f"{self.icon}  {self.title}" if self.icon else self.title
        self.title_label = tk.Label(
            left_frame,
            text=title_text,
            font=self._font_subheader_bold,
            bg=COLORS['surface'],
            fg=COLORS['text_primary'],
            anchor='w'
        )
        self.title_label.pack(anchor='w')

        # Info text container
        self.info_frame = tk.Frame(left_frame, bg=COLORS['surface'])
        self.info_frame.pack(anchor='w', pady=(4, 0))

        # Primary info (e.g., "45%")
        self.value_label = tk.Label(
            self.info_frame,
            text="0%",
            font=self._font_header_bold,
            bg=COLORS['surface'],
            fg=COLORS['accent'],
            anchor='w'
        )
        self.value_label.pack(anchor='w')

        # Secondary info
        self.secondary_label = tk.Label(
            self.info_frame,
            text="",
            font=self._font_tiny,
            bg=COLORS['surface'],
            fg=COLORS['text_secondary'],
            anchor='w'
        )
        self.secondary_label.pack(anchor='w')

        # Right side: Mini graph (borderless)
        self.graph_canvas = tk.Canvas(
            content,
            width=100,
            height=60,
            bg=COLORS['bg_tertiary'],
            highlightthickness=0
        )
        self.graph_canvas.pack(side=tk.RIGHT, padx=(8, 0))

        # Cache all widgets that need bg changes (flat list for fast iteration)
        self._bg_widgets = [
            self, content, left_frame, self.info_frame,
            self.title_label, self.value_label, self.secondary_label
        ]

    def _bind_events(self):
        """Bind interaction events"""
        widgets = [self, self.title_label, self.value_label,
                   self.secondary_label, self.info_frame, self.graph_canvas]

        for widget in widgets:
            widget.bind('<Enter>', self._on_enter)
            widget.bind('<Leave>', self._on_leave)
            widget.bind('<Button-1>', self._on_click)

    def _on_enter(self, event):
        """Mouse enter"""
        if not self.selected:
            self._set_bg_fast(COLORS['surface_hover'])

    def _on_leave(self, event):
        """Mouse leave"""
        if not self.selected:
            self._set_bg_fast(COLORS['surface'])

    def _on_click(self, event):
        """Handle click"""
        if self.on_click:
            self.on_click()

    def _set_bg_fast(self, color):
        """Set background color using cached widget list (fast)"""
        for widget in self._bg_widgets:
            try:
                widget.configure(bg=color)
            except tk.TclError:
                pass

    def set_selected(self, selected):
        """Set selection state"""
        self.selected = selected
        if selected:
            self._set_bg_fast(COLORS['selection'])
            self.configure(highlightbackground=COLORS['selection_border'],
                          highlightthickness=2)
        else:
            self._set_bg_fast(COLORS['surface'])
            self.configure(highlightbackground=COLORS['border'],
                          highlightthickness=0)

    def set_title(self, title):
        """Set the button title"""
        self.title = title
        title_text = f"{self.icon}  {title}" if self.icon else title
        self.title_label.configure(text=title_text)

    def set_value(self, value, unit="%"):
        """Set primary value display"""
        self.value_label.configure(text=f"{value:.1f}{unit}")

    def set_secondary_text(self, text):
        """Set secondary info text"""
        self.secondary_label.configure(text=text)

    def add_data_point(self, value):
        """Add a data point to the graph"""
        self.data.append(value)
        self._graph_dirty = True
        self._update_graph()

    def _init_graph_items(self):
        """Initialize graph canvas items once"""
        self.graph_canvas.delete('all')

        # Create fill polygon and line (initially with dummy coords)
        self._graph_fill = self.graph_canvas.create_polygon(
            0, 0, fill=self.fill_color, outline=''
        )
        self._graph_line = self.graph_canvas.create_line(
            0, 0, 0, 0, fill=self.line_color, width=2, smooth=True
        )
        self._graph_initialized = True

    def _update_graph(self):
        """Update the mini graph using existing canvas items"""
        if not self._graph_dirty:
            return

        w = self.graph_canvas.winfo_width()
        h = self.graph_canvas.winfo_height()

        if w < 20 or h < 20:
            return

        if not self._graph_initialized:
            self._init_graph_items()

        if len(self.data) < 2:
            # Hide items when not enough data
            self.graph_canvas.itemconfigure(self._graph_fill, state='hidden')
            self.graph_canvas.itemconfigure(self._graph_line, state='hidden')
            self._graph_dirty = False
            return

        margin = 4
        graph_w = w - margin * 2
        graph_h = h - margin * 2

        # Build points
        points = []
        for i, value in enumerate(self.data):
            x = margin + (i / 30) * graph_w
            clamped = max(0, min(self.max_value, value))
            y = margin + graph_h - (clamped / self.max_value) * graph_h
            points.append((x, y))

        # Build fill polygon
        fill_points = [(points[0][0], margin + graph_h)]
        fill_points.extend(points)
        fill_points.append((points[-1][0], margin + graph_h))
        flat_fill = [c for p in fill_points for c in p]

        # Update polygon coords
        self.graph_canvas.coords(self._graph_fill, *flat_fill)
        self.graph_canvas.itemconfigure(self._graph_fill, state='normal')

        # Update line coords
        line_flat = [c for p in points for c in p]
        self.graph_canvas.coords(self._graph_line, *line_flat)
        self.graph_canvas.itemconfigure(self._graph_line, state='normal')

        self._graph_dirty = False
