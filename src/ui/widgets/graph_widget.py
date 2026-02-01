"""
GraphWidget - Optimized real-time line graph for performance monitoring
Uses canvas item reuse instead of delete/recreate for better performance
"""

import tkinter as tk
from collections import deque
from ..themes import COLORS, Theme


class GraphWidget(tk.Canvas):
    """
    Optimized graph widget for displaying real-time performance data.
    Reuses canvas items instead of deleting and recreating each frame.
    """

    def __init__(self, parent, width=400, height=140, line_color=None, fill_color=None, **kwargs):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=COLORS['bg_primary'],
            highlightthickness=0,
            **kwargs
        )

        self.data_primary = deque(maxlen=Theme.GRAPH_HISTORY_SIZE)
        self.data_secondary = deque(maxlen=Theme.GRAPH_HISTORY_SIZE)

        self.max_value = 100
        self.show_secondary = False
        self.show_grid = True
        self.show_labels = True

        # Custom colors
        self.line_color = line_color or COLORS['graph_line']
        self.fill_color = fill_color or COLORS['graph_fill']

        self.label_y = "%"
        self.label_x = ""

        # Margins
        self.margin_left = 45 if self.show_labels else 15
        self.margin_right = 15
        self.margin_top = 15
        self.margin_bottom = 25 if self.show_labels else 15

        # Canvas item IDs for reuse (avoid delete/create overhead)
        self._bg_rect = None
        self._grid_lines = []
        self._fill_polygon = None
        self._data_line = None
        self._fill_polygon_secondary = None
        self._data_line_secondary = None
        self._value_text = None
        self._label_items = []
        self._initialized = False
        self._dirty = True

        # Cache fonts (avoid repeated font tuple creation)
        self._font_small_bold = Theme.get_font(Theme.FONT_SIZE_SMALL, bold=True)
        self._font_tiny = Theme.get_font(Theme.FONT_SIZE_TINY)

        # Cache dimensions
        self._last_width = 0
        self._last_height = 0

        self.bind('<Configure>', self._on_resize)

    def set_max_value(self, value):
        """Set maximum Y-axis value"""
        self.max_value = max(1, value)
        self._dirty = True

    def set_labels(self, y_label="", x_label=""):
        """Set axis labels"""
        self.label_y = y_label
        self.label_x = x_label
        self._dirty = True

    def add_value(self, value, secondary=None):
        """Add a new data point"""
        self.data_primary.append(value)
        if secondary is not None:
            self.data_secondary.append(secondary)
        self._dirty = True
        self._update_graph()

    def clear(self):
        """Clear all data"""
        self.data_primary.clear()
        self.data_secondary.clear()
        self._dirty = True
        self._update_graph()

    def _on_resize(self, event=None):
        """Handle resize"""
        w = self.winfo_width()
        h = self.winfo_height()
        if w != self._last_width or h != self._last_height:
            self._last_width = w
            self._last_height = h
            self._initialized = False  # Force full redraw on resize
            self._dirty = True
            self._update_graph()

    def _init_canvas_items(self, left, top, right, bottom):
        """Initialize all canvas items once"""
        self.delete('all')

        # Background rectangle
        self._bg_rect = self.create_rectangle(
            left, top, right, bottom,
            fill=COLORS['bg_tertiary'],
            outline=''
        )

        # Grid lines (4 horizontal + 3 vertical = 7 lines)
        self._grid_lines = []
        for _ in range(7):
            line_id = self.create_line(0, 0, 0, 0, fill=COLORS['graph_grid'], dash=(2, 4))
            self._grid_lines.append(line_id)

        # Secondary data (behind primary)
        self._fill_polygon_secondary = self.create_polygon(
            0, 0, fill=COLORS['graph_fill_secondary'], outline='', state='hidden'
        )
        self._data_line_secondary = self.create_line(
            0, 0, 0, 0, fill=COLORS['graph_line_secondary'],
            width=Theme.GRAPH_LINE_WIDTH, smooth=True, state='hidden'
        )

        # Primary data polygon and line
        self._fill_polygon = self.create_polygon(
            0, 0, fill=self.fill_color, outline=''
        )
        self._data_line = self.create_line(
            0, 0, 0, 0, fill=self.line_color,
            width=Theme.GRAPH_LINE_WIDTH, smooth=True
        )

        # Current value text
        self._value_text = self.create_text(
            right - 5, top + 5,
            text="",
            anchor='ne',
            font=self._font_small_bold,
            fill=COLORS['text_primary']
        )

        # Labels (if enabled)
        self._label_items = []
        if self.show_labels:
            # Y-axis labels (top, middle, bottom)
            for _ in range(3):
                label_id = self.create_text(0, 0, text="", anchor='e',
                                           font=self._font_tiny, fill=COLORS['text_tertiary'])
                self._label_items.append(label_id)
            # X-axis labels (left, right)
            for _ in range(2):
                label_id = self.create_text(0, 0, text="", anchor='nw',
                                           font=self._font_tiny, fill=COLORS['text_tertiary'])
                self._label_items.append(label_id)

        self._initialized = True

    def _update_graph(self):
        """Update graph using existing canvas items"""
        if not self._dirty:
            return

        w = self.winfo_width()
        h = self.winfo_height()

        if w < 50 or h < 50:
            return

        # Calculate graph area
        graph_left = self.margin_left
        graph_right = w - self.margin_right
        graph_top = self.margin_top
        graph_bottom = h - self.margin_bottom

        graph_width = graph_right - graph_left
        graph_height = graph_bottom - graph_top

        if graph_width < 10 or graph_height < 10:
            return

        # Initialize canvas items if needed
        if not self._initialized:
            self._init_canvas_items(graph_left, graph_top, graph_right, graph_bottom)

        # Update background rectangle
        self.coords(self._bg_rect, graph_left, graph_top, graph_right, graph_bottom)

        # Update grid lines
        if self.show_grid:
            idx = 0
            # Horizontal lines (25%, 50%, 75%)
            for pct in [0.25, 0.5, 0.75]:
                y = graph_bottom - (pct * graph_height)
                self.coords(self._grid_lines[idx], graph_left, y, graph_right, y)
                self.itemconfigure(self._grid_lines[idx], state='normal')
                idx += 1
            # Vertical lines
            for i in range(1, 4):
                x = graph_left + (i * 0.25 * graph_width)
                self.coords(self._grid_lines[idx], x, graph_top, x, graph_bottom)
                self.itemconfigure(self._grid_lines[idx], state='normal')
                idx += 1
            # Hide unused grid lines
            while idx < len(self._grid_lines):
                self.itemconfigure(self._grid_lines[idx], state='hidden')
                idx += 1

        # Update secondary data
        if self.show_secondary and len(self.data_secondary) > 1:
            points = self._calculate_points(self.data_secondary, graph_left, graph_top, graph_width, graph_height)
            self._update_data_series(points, graph_top + graph_height,
                                    self._fill_polygon_secondary, self._data_line_secondary)
            self.itemconfigure(self._fill_polygon_secondary, state='normal')
            self.itemconfigure(self._data_line_secondary, state='normal')
        else:
            self.itemconfigure(self._fill_polygon_secondary, state='hidden')
            self.itemconfigure(self._data_line_secondary, state='hidden')

        # Update primary data
        if len(self.data_primary) > 1:
            points = self._calculate_points(self.data_primary, graph_left, graph_top, graph_width, graph_height)
            self._update_data_series(points, graph_top + graph_height,
                                    self._fill_polygon, self._data_line)
            self.itemconfigure(self._fill_polygon, state='normal')
            self.itemconfigure(self._data_line, state='normal')
        else:
            self.itemconfigure(self._fill_polygon, state='hidden')
            self.itemconfigure(self._data_line, state='hidden')

        # Update value text
        if len(self.data_primary) > 0:
            current = self.data_primary[-1]
            self.coords(self._value_text, graph_right - 5, graph_top + 5)
            self.itemconfigure(self._value_text, text=f"{current:.1f}{self.label_y}")
        else:
            self.itemconfigure(self._value_text, text="")

        # Update labels
        if self.show_labels and self._label_items:
            # Y-axis labels
            self.coords(self._label_items[0], graph_left - 5, graph_top)
            self.itemconfigure(self._label_items[0], text=f"{self.max_value:.0f}")

            self.coords(self._label_items[1], graph_left - 5, (graph_top + graph_bottom) / 2)
            self.itemconfigure(self._label_items[1], text=f"{self.max_value/2:.0f}")

            self.coords(self._label_items[2], graph_left - 5, graph_bottom)
            self.itemconfigure(self._label_items[2], text="0")

            # X-axis labels
            self.coords(self._label_items[3], graph_left, graph_bottom + 5)
            self.itemconfigure(self._label_items[3], text="0", anchor='nw')

            self.coords(self._label_items[4], graph_right, graph_bottom + 5)
            self.itemconfigure(self._label_items[4], text="60s", anchor='ne')

        self._dirty = False

    def _calculate_points(self, data, left, top, width, height):
        """Calculate graph points from data"""
        points = []
        max_points = Theme.GRAPH_HISTORY_SIZE

        for i, value in enumerate(data):
            x = left + (i / max_points) * width
            clamped = max(0, min(self.max_value, value))
            y = top + height - (clamped / self.max_value) * height
            points.append((x, y))

        return points

    def _update_data_series(self, points, bottom_y, fill_item, line_item):
        """Update a data series polygon and line"""
        if len(points) < 2:
            return

        # Build fill polygon points
        fill_points = [(points[0][0], bottom_y)]
        fill_points.extend(points)
        fill_points.append((points[-1][0], bottom_y))
        flat_fill = [coord for point in fill_points for coord in point]

        # Update polygon
        self.coords(fill_item, *flat_fill)

        # Update line
        flat_line = [coord for point in points for coord in point]
        self.coords(line_item, *flat_line)

    # Legacy method for compatibility
    def redraw(self):
        """Redraw the graph (legacy compatibility)"""
        self._dirty = True
        self._update_graph()


class MiniGraphWidget(GraphWidget):
    """Smaller graph widget for performance buttons"""

    def __init__(self, parent, width=110, height=60, **kwargs):
        super().__init__(parent, width=width, height=height, **kwargs)
        self.show_labels = False
        self.show_grid = False
        self.margin_left = 5
        self.margin_right = 5
        self.margin_top = 5
        self.margin_bottom = 5
