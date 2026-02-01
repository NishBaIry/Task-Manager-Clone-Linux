"""
ProcessesView - Clean process list with colored usage cells
Inspired by the reference task manager design
"""

import tkinter as tk
from tkinter import ttk, messagebox, Menu
import psutil
import os
import signal
import subprocess
import time
import re
import threading
from ..themes import COLORS, Theme
from ..utils import IconLoader


# Process classification patterns
APP_PATTERNS = [
    'chrome', 'firefox', 'brave', 'edge', 'opera', 'vivaldi', 'chromium',
    'code', 'visual studio', 'pycharm', 'intellij', 'eclipse', 'sublime',
    'atom', 'cursor', 'gedit', 'kate', 'neovim', 'vim',
    'slack', 'discord', 'teams', 'zoom', 'skype', 'telegram', 'signal',
    'spotify', 'vlc', 'mpv', 'rhythmbox', 'clementine', 'audacity',
    'gimp', 'inkscape', 'blender', 'krita', 'darktable',
    'libreoffice', 'writer', 'calc', 'impress',
    'dolphin', 'nautilus', 'thunar', 'nemo', 'pcmanfm',
    'konsole', 'gnome-terminal', 'tilix', 'alacritty', 'kitty', 'wezterm',
    'thunderbird', 'evolution', 'geary',
    'docker', 'postman', 'insomnia', 'dbeaver',
    'obs', 'kdenlive', 'handbrake', 'shotcut',
]

BLACKLIST = {
    'systemd', 'dbus-daemon', 'systemd-resolved', 'systemd-timesyncd',
    'systemd-logind', 'systemd-journald', 'systemd-udevd',
    'xorg', 'xwayland', 'kwin_x11', 'kwin_wayland',
    'mutter', 'gnome-shell', 'plasmashell',
    'pulseaudio', 'pipewire', 'pipewire-pulse', 'wireplumber',
    'kded5', 'kded6', 'ksmserver', 'kglobalaccel5',
    'gvfsd', 'gvfsd-fuse', 'gvfsd-metadata',
    'at-spi-bus-launcher', 'at-spi2-registryd',
    'ibus-daemon', 'ibus-portal', 'fcitx5',
    'xdg-desktop-portal', 'xdg-desktop-portal-gtk', 'xdg-desktop-portal-kde',
    'polkit-kde-authentication-agent-1', 'polkitd',
    'chrome_crashpad_handler', 'crashpad_handler',
}

PARENT_BLACKLIST = {
    'bash', 'zsh', 'sh', 'fish', 'dash', 'ksh',
    'bwrap', 'snap-confine', 'firejail',
    'python', 'python3', 'python2', 'perl', 'ruby', 'node',
    'systemd', 'init',
}


def get_usage_color(value, max_val=100):
    """Get background color based on usage value (yellow/orange gradient)"""
    if value <= 0:
        return COLORS['surface']

    # Normalize value
    ratio = min(1.0, value / max_val)

    if ratio < 0.1:
        return COLORS['surface']
    elif ratio < 0.3:
        # Light yellow
        return '#4a4a2a'
    elif ratio < 0.5:
        # Yellow
        return '#6b6b2a'
    elif ratio < 0.7:
        # Orange-yellow
        return '#8b7b2a'
    else:
        # Orange
        return '#ab8b2a'


# Cached fonts for performance (avoid repeated Theme.get_font calls)
_FONT_SMALL = None
_FONT_BODY = None
_FONT_TINY = None
_FONT_BODY_BOLD = None


def _init_fonts():
    """Initialize cached fonts (call once after tk root exists)"""
    global _FONT_SMALL, _FONT_BODY, _FONT_TINY, _FONT_BODY_BOLD
    if _FONT_SMALL is None:
        _FONT_SMALL = Theme.get_font(Theme.FONT_SIZE_SMALL)
        _FONT_BODY = Theme.get_font(Theme.FONT_SIZE_BODY)
        _FONT_TINY = Theme.get_font(Theme.FONT_SIZE_TINY)
        _FONT_BODY_BOLD = Theme.get_font(Theme.FONT_SIZE_BODY, bold=True)


class SubProcessRow(tk.Frame):
    """Individual process row shown when parent is expanded"""

    def __init__(self, parent, pid, name, cpu, mem, on_select=None, on_context=None, **kwargs):
        super().__init__(parent, bg=COLORS['bg_primary'], cursor='hand2', **kwargs)
        _init_fonts()

        self.pid = pid
        self.pids = [pid]  # For compatibility with kill functions
        self.name = name
        self.cpu = cpu
        self.mem = mem
        self.selected = False
        self.on_select = on_select
        self.on_context = on_context
        self.is_app = False  # Sub-processes shown as individual

        # Cache previous values to skip unnecessary updates
        self._prev_cpu = None
        self._prev_mem = None

        # Inner frame with indentation
        self.inner = tk.Frame(self, bg=COLORS['bg_tertiary'], cursor='hand2')
        self.inner.pack(fill=tk.X, padx=(24, 0), pady=(0, 1))

        self._create_widgets()
        self._bind_events()

    def _create_widgets(self):
        """Create row widgets"""
        # Small indent indicator
        tk.Label(
            self.inner, text="└",
            font=_FONT_SMALL,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_tertiary'],
            width=2
        ).pack(side=tk.LEFT, padx=(4, 0), pady=8)

        # PID as name for sub-process
        self.name_label = tk.Label(
            self.inner, text=f"PID {self.pid}",
            font=_FONT_SMALL,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_secondary'],
            anchor='w'
        )
        self.name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), pady=8)

        # PID
        self.pid_label = tk.Label(
            self.inner, text=str(self.pid),
            font=_FONT_SMALL,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_tertiary'],
            width=8, anchor='e'
        )
        self.pid_label.pack(side=tk.RIGHT, padx=(8, 16), pady=8)

        # Memory
        mem_mb = self.mem
        if mem_mb >= 1024:
            mem_text = f"{mem_mb/1024:.2f}GiB"
        else:
            mem_text = f"{mem_mb:.2f}MiB"
        mem_color = get_usage_color(mem_mb, 4096)
        self.mem_label = tk.Label(
            self.inner, text=mem_text,
            font=_FONT_SMALL,
            bg=mem_color, fg=COLORS['text_primary'],
            width=10, anchor='e', padx=6, pady=8
        )
        self.mem_label.pack(side=tk.RIGHT, padx=(0, 8))

        # CPU
        cpu_color = get_usage_color(self.cpu, 10)
        self.cpu_label = tk.Label(
            self.inner, text=f"{self.cpu:.2f}%",
            font=_FONT_SMALL,
            bg=cpu_color, fg=COLORS['text_primary'],
            width=8, anchor='e', padx=6, pady=8
        )
        self.cpu_label.pack(side=tk.RIGHT, padx=(0, 8))

    def _bind_events(self):
        """Bind mouse events"""
        widgets = [self, self.inner, self.name_label, self.cpu_label, self.mem_label, self.pid_label]
        for w in widgets:
            w.bind('<Enter>', self._on_enter)
            w.bind('<Leave>', self._on_leave)
            w.bind('<Button-1>', self._on_click)
            w.bind('<Button-3>', self._on_right_click)

    def _on_enter(self, event):
        if not self.selected:
            self._set_bg(COLORS['surface_hover'])

    def _on_leave(self, event):
        if not self.selected:
            self._set_bg(COLORS['bg_tertiary'])

    def _on_click(self, event):
        if self.on_select:
            self.on_select(self)

    def _on_right_click(self, event):
        if self.on_select:
            self.on_select(self)
        if self.on_context:
            self.on_context(event, self)

    def _set_bg(self, color):
        self.inner.configure(bg=color)
        self.name_label.configure(bg=color)
        self.pid_label.configure(bg=color)

    def set_selected(self, selected):
        self.selected = selected
        if selected:
            self._set_bg(COLORS['selection'])
        else:
            self._set_bg(COLORS['bg_tertiary'])

    def update_data(self, cpu, mem):
        """Update process data (skip if unchanged)"""
        # Round to avoid unnecessary updates from tiny changes
        cpu_rounded = round(cpu, 1)
        mem_rounded = round(mem, 1)

        # Skip update if values haven't changed significantly
        if cpu_rounded == self._prev_cpu and mem_rounded == self._prev_mem:
            return

        self._prev_cpu = cpu_rounded
        self._prev_mem = mem_rounded
        self.cpu = cpu
        self.mem = mem

        cpu_color = get_usage_color(cpu, 10)
        self.cpu_label.configure(text=f"{cpu:.2f}%", bg=cpu_color)

        if mem >= 1024:
            mem_text = f"{mem/1024:.2f}GiB"
        else:
            mem_text = f"{mem:.2f}MiB"
        mem_color = get_usage_color(mem, 4096)
        self.mem_label.configure(text=mem_text, bg=mem_color)


class ProcessRow(tk.Frame):
    """Process row with colored usage cells - expandable if multiple PIDs"""

    # Row height to show ~10 processes in view
    ROW_HEIGHT = 48

    def __init__(self, parent, name, pids, cpu, mem, state, is_app=False,
                 on_select=None, on_context=None, process_details=None, icon=None, **kwargs):
        super().__init__(parent, bg=COLORS['bg_primary'], cursor='hand2', **kwargs)
        _init_fonts()

        self.name = name
        self.pids = pids
        self.cpu = cpu
        self.mem = mem
        self.state = state
        self.is_app = is_app
        self.selected = False
        self.on_select = on_select
        self.on_context = on_context
        self.expanded = False
        self.process_details = process_details or {}  # {pid: {'cpu': x, 'mem': y}}
        self.sub_rows = {}
        self.icon = icon  # PhotoImage for app icon

        # Cache previous values to skip unnecessary updates
        self._prev_cpu = None
        self._prev_mem = None
        self._prev_pids_count = None

        # Inner frame for actual content with padding
        self.inner = tk.Frame(self, bg=COLORS['surface'], cursor='hand2')
        self.inner.pack(fill=tk.X, pady=(0, 2))  # Small gap between rows

        # Container for sub-process rows (initially hidden)
        self.sub_container = tk.Frame(self, bg=COLORS['bg_primary'])

        self._create_widgets()
        self._bind_events()

    def _create_widgets(self):
        """Create row widgets"""
        # Expand arrow (for processes with children)
        arrow = "▶" if len(self.pids) > 1 else " "
        self.arrow_label = tk.Label(
            self.inner, text=arrow,
            font=_FONT_SMALL,
            bg=COLORS['surface'], fg=COLORS['text_tertiary'],
            width=2
        )
        self.arrow_label.pack(side=tk.LEFT, padx=(8, 0), pady=12)

        # Process count badge (shows number of processes if > 1)
        count_text = f"({len(self.pids)})" if len(self.pids) > 1 else ""
        self.count_label = tk.Label(
            self.inner, text=count_text,
            font=_FONT_TINY,
            bg=COLORS['surface'], fg=COLORS['text_tertiary']
        )
        self.count_label.pack(side=tk.LEFT, padx=(0, 4), pady=12)

        # Icon for apps
        self.icon_label = None
        if self.icon and self.is_app:
            self.icon_label = tk.Label(
                self.inner, image=self.icon,
                bg=COLORS['surface']
            )
            self.icon_label.pack(side=tk.LEFT, padx=(0, 6), pady=8)

        # Name - expands to fill available space
        self.name_label = tk.Label(
            self.inner, text=self.name,
            font=_FONT_BODY,
            bg=COLORS['surface'], fg=COLORS['text_primary'],
            anchor='w'
        )
        self.name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=12)

        # PID (on the right)
        pid_text = str(self.pids[0]) if len(self.pids) == 1 else f"{len(self.pids)} PIDs"
        self.pid_label = tk.Label(
            self.inner, text=pid_text,
            font=_FONT_BODY,
            bg=COLORS['surface'], fg=COLORS['text_secondary'],
            width=8, anchor='e'
        )
        self.pid_label.pack(side=tk.RIGHT, padx=(8, 16), pady=12)

        # Memory cell with colored background (pack from right)
        mem_mb = self.mem
        if mem_mb >= 1024:
            mem_text = f"{mem_mb/1024:.2f}GiB"
        else:
            mem_text = f"{mem_mb:.2f}MiB"
        mem_color = get_usage_color(mem_mb, 4096)  # 4GB is high
        self.mem_label = tk.Label(
            self.inner, text=mem_text,
            font=_FONT_BODY,
            bg=mem_color, fg=COLORS['text_primary'],
            width=10, anchor='e', padx=8, pady=12
        )
        self.mem_label.pack(side=tk.RIGHT, padx=(0, 8))

        # CPU cell with colored background (pack from right)
        cpu_color = get_usage_color(self.cpu, 10)  # 10% is high for single process
        self.cpu_label = tk.Label(
            self.inner, text=f"{self.cpu:.2f}%",
            font=_FONT_BODY,
            bg=cpu_color, fg=COLORS['text_primary'],
            width=8, anchor='e', padx=8, pady=12
        )
        self.cpu_label.pack(side=tk.RIGHT, padx=(0, 8))

    def _bind_events(self):
        """Bind mouse events"""
        # Arrow is clickable for expand/collapse
        self.arrow_label.bind('<Button-1>', self._on_arrow_click)
        self.arrow_label.configure(cursor='hand2')

        # Other widgets for selection
        widgets = [self.inner, self.name_label, self.count_label,
                   self.cpu_label, self.mem_label, self.pid_label]
        if self.icon_label:
            widgets.append(self.icon_label)
        for w in widgets:
            w.bind('<Enter>', self._on_enter)
            w.bind('<Leave>', self._on_leave)
            w.bind('<Button-1>', self._on_click)
            w.bind('<Button-3>', self._on_right_click)

        # Also bind to self but not arrow for hover
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_arrow_click(self, event):
        """Handle arrow click for expand/collapse"""
        if len(self.pids) > 1:
            self._toggle_expand()
        return "break"  # Prevent event propagation

    def _toggle_expand(self):
        """Toggle expanded state"""
        self.expanded = not self.expanded
        if self.expanded:
            self.arrow_label.configure(text="▼")
            self._show_sub_processes()
        else:
            self.arrow_label.configure(text="▶")
            self._hide_sub_processes()

    def _show_sub_processes(self):
        """Show individual process rows"""
        self.sub_container.pack(fill=tk.X, after=self.inner)

        for pid in self.pids:
            if pid not in self.sub_rows:
                details = self.process_details.get(pid, {'cpu': 0, 'mem': 0})
                sub_row = SubProcessRow(
                    self.sub_container, pid, self.name,
                    details.get('cpu', 0), details.get('mem', 0),
                    on_select=self.on_select, on_context=self.on_context
                )
                sub_row.pack(fill=tk.X)
                self.sub_rows[pid] = sub_row

    def _hide_sub_processes(self):
        """Hide individual process rows"""
        self.sub_container.pack_forget()

    def _on_enter(self, event):
        if not self.selected:
            self._set_bg(COLORS['surface_hover'])

    def _on_leave(self, event):
        if not self.selected:
            self._set_bg(COLORS['surface'])

    def _on_click(self, event):
        if self.on_select:
            self.on_select(self)

    def _on_right_click(self, event):
        if self.on_select:
            self.on_select(self)
        if self.on_context:
            self.on_context(event, self)

    def _set_bg(self, color):
        """Set background color for non-usage cells"""
        self.inner.configure(bg=color)
        self.arrow_label.configure(bg=color)
        self.count_label.configure(bg=color)
        self.name_label.configure(bg=color)
        self.pid_label.configure(bg=color)
        if self.icon_label:
            self.icon_label.configure(bg=color)

    def set_selected(self, selected):
        self.selected = selected
        if selected:
            self._set_bg(COLORS['selection'])
        else:
            self._set_bg(COLORS['surface'])

    def update_data(self, cpu, mem, state, pids, process_details=None):
        """Update process data (skip unchanged values)"""
        # Round to avoid unnecessary updates from tiny changes
        cpu_rounded = round(cpu, 1)
        mem_rounded = round(mem, 1)
        pids_count = len(pids)

        self.state = state
        self.pids = pids
        if process_details:
            self.process_details = process_details

        # Only update CPU if changed
        if cpu_rounded != self._prev_cpu:
            self._prev_cpu = cpu_rounded
            self.cpu = cpu
            cpu_color = get_usage_color(cpu, 10)
            self.cpu_label.configure(text=f"{cpu:.2f}%", bg=cpu_color)

        # Only update Memory if changed
        if mem_rounded != self._prev_mem:
            self._prev_mem = mem_rounded
            self.mem = mem
            if mem >= 1024:
                mem_text = f"{mem/1024:.2f}GiB"
            else:
                mem_text = f"{mem:.2f}MiB"
            mem_color = get_usage_color(mem, 4096)
            self.mem_label.configure(text=mem_text, bg=mem_color)

        # Only update PID count if changed
        if pids_count != self._prev_pids_count:
            self._prev_pids_count = pids_count
            if pids_count > 1:
                arrow = "▼" if self.expanded else "▶"
                self.count_label.configure(text=f"({pids_count})")
                self.pid_label.configure(text=f"{pids_count} PIDs")
            else:
                arrow = " "
                self.count_label.configure(text="")
                self.pid_label.configure(text=str(pids[0]))
            self.arrow_label.configure(text=arrow)

        # Update sub-rows if expanded
        if self.expanded and process_details:
            # Remove sub-rows for processes that no longer exist
            for pid in list(self.sub_rows.keys()):
                if pid not in pids:
                    self.sub_rows[pid].destroy()
                    del self.sub_rows[pid]

            # Add/update sub-rows
            for pid in pids:
                details = process_details.get(pid, {'cpu': 0, 'mem': 0})
                if pid in self.sub_rows:
                    self.sub_rows[pid].update_data(details.get('cpu', 0), details.get('mem', 0))
                else:
                    sub_row = SubProcessRow(
                        self.sub_container, pid, self.name,
                        details.get('cpu', 0), details.get('mem', 0),
                        on_select=self.on_select, on_context=self.on_context
                    )
                    sub_row.pack(fill=tk.X)
                    self.sub_rows[pid] = sub_row


class SectionHeader(tk.Frame):
    """Section header (Apps, Background, etc.)"""

    def __init__(self, parent, title, count=0, expanded=True, on_toggle=None,
                 bg_color=None, **kwargs):
        super().__init__(parent, bg=bg_color or COLORS['accent'], **kwargs)
        _init_fonts()

        self.title = title
        self.count = count
        self.expanded = expanded
        self.on_toggle = on_toggle
        self.bg_color = bg_color or COLORS['accent']

        self._create_widgets()

    def _create_widgets(self):
        """Create header widgets"""
        self.configure(cursor='hand2')

        # Title
        self.title_label = tk.Label(
            self, text=self.title,
            font=_FONT_BODY_BOLD,
            bg=self.bg_color, fg=COLORS['text_primary']
        )
        self.title_label.pack(side=tk.LEFT, padx=16, pady=12)

        # Bind click
        for widget in [self, self.title_label]:
            widget.bind('<Button-1>', self._on_click)
            widget.configure(cursor='hand2')

    def _on_click(self, event):
        self.expanded = not self.expanded
        if self.on_toggle:
            self.on_toggle(self.expanded)

    def set_count(self, count):
        self.count = count


class ProcessesView(tk.Frame):
    """Clean process list view"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_primary'], **kwargs)

        self.process_data = []
        self.process_groups = {}
        self.window_pids = set()
        self.classification_cache = {}
        self.selected_row = None
        self.rows = {}
        self.apps_expanded = True
        self.bg_expanded = True
        self._cache_cleanup_counter = 0
        self._window_pid_thread_running = False  # Prevent thread accumulation

        # Icon loader for app icons
        self.icon_loader = IconLoader(size=20)

        self._create_ui()

    def _create_ui(self):
        """Create the processes view UI"""
        _init_fonts()

        # Column headers with right padding to match content
        header_frame = tk.Frame(self, bg=COLORS['bg_tertiary'])
        header_frame.pack(fill=tk.X, padx=(0, Theme.PADDING_MEDIUM))

        # Spacer for arrow
        tk.Label(header_frame, text="", width=2,
                bg=COLORS['bg_tertiary']).pack(side=tk.LEFT, padx=(8, 0))

        # Name header - expands to fill space
        tk.Label(
            header_frame, text="Name",
            font=_FONT_BODY_BOLD,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_secondary'],
            anchor='w'
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8), pady=12)

        # PID header (on right side) - matches data column padding
        tk.Label(
            header_frame, text="PID", width=8,
            font=_FONT_BODY_BOLD,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_secondary'],
            anchor='e'
        ).pack(side=tk.RIGHT, padx=(8, 16), pady=12)

        # RAM header (pack from right) - matches data column with internal padx
        tk.Label(
            header_frame, text="RAM", width=10,
            font=_FONT_BODY_BOLD,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_secondary'],
            anchor='e', padx=8
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=12)

        # CPU header (pack from right) - matches data column with internal padx
        tk.Label(
            header_frame, text="CPU", width=8,
            font=_FONT_BODY_BOLD,
            bg=COLORS['bg_tertiary'], fg=COLORS['text_secondary'],
            anchor='e', padx=8
        ).pack(side=tk.RIGHT, padx=(0, 8), pady=12)

        # Scrollable content area with right padding
        container = tk.Frame(self, bg=COLORS['bg_primary'])
        container.pack(fill=tk.BOTH, expand=True, padx=(0, Theme.PADDING_MEDIUM))

        # Canvas for scrolling
        self.canvas = tk.Canvas(container, bg=COLORS['bg_primary'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)

        self.scroll_frame = tk.Frame(self.canvas, bg=COLORS['bg_primary'])
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor='nw')

        self.scroll_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel scrolling - scroll by 3 units for smoother feel with bigger rows
        self.canvas.bind_all('<Button-4>', lambda e: self.canvas.yview_scroll(-3, 'units'))
        self.canvas.bind_all('<Button-5>', lambda e: self.canvas.yview_scroll(3, 'units'))

        # Apps section
        self.apps_header = SectionHeader(
            self.scroll_frame, "Apps", 0, True,
            on_toggle=lambda exp: self._toggle_section('apps', exp),
            bg_color='#2a6a6a'
        )
        self.apps_header.pack(fill=tk.X)

        self.apps_container = tk.Frame(self.scroll_frame, bg=COLORS['bg_primary'])
        self.apps_container.pack(fill=tk.X)

        # Background processes section (same color as Apps)
        self.bg_header = SectionHeader(
            self.scroll_frame, "Background", 0, True,
            on_toggle=lambda exp: self._toggle_section('bg', exp),
            bg_color='#2a6a6a'
        )
        self.bg_header.pack(fill=tk.X)

        self.bg_container = tk.Frame(self.scroll_frame, bg=COLORS['bg_primary'])
        self.bg_container.pack(fill=tk.X)

        # Bottom toolbar with End task button
        bottom_bar = tk.Frame(self, bg=COLORS['bg_secondary'])
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Process count
        self.count_label = tk.Label(
            bottom_bar, text="0 processes",
            font=_FONT_BODY,
            bg=COLORS['bg_secondary'], fg=COLORS['text_secondary']
        )
        self.count_label.pack(side=tk.LEFT, padx=16, pady=12)

        # End task button
        self.end_btn = tk.Button(
            bottom_bar, text="End task",
            font=_FONT_BODY_BOLD,
            bg=COLORS['danger'], fg=COLORS['text_primary'],
            activebackground=COLORS['danger_hover'], activeforeground=COLORS['text_primary'],
            relief=tk.FLAT, padx=24, pady=8, cursor='hand2',
            state=tk.DISABLED, command=self._kill_selected
        )
        self.end_btn.pack(side=tk.RIGHT, padx=16, pady=8)

    def _toggle_section(self, section, expanded):
        """Toggle section visibility"""
        if section == 'apps':
            self.apps_expanded = expanded
            if expanded:
                self.apps_container.pack(fill=tk.X, after=self.apps_header)
            else:
                self.apps_container.pack_forget()
        else:
            self.bg_expanded = expanded
            if expanded:
                self.bg_container.pack(fill=tk.X, after=self.bg_header)
            else:
                self.bg_container.pack_forget()

    def update_window_pids(self):
        """Update the set of PIDs that have windows (runs in background)"""
        # Prevent spawning multiple threads if previous one is still running
        if self._window_pid_thread_running:
            return

        def _fetch_pids():
            try:
                pids = set()
                try:
                    # Use wmctrl if available (faster than xprop)
                    result = subprocess.run(
                        ['wmctrl', '-lp'],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n'):
                            parts = line.split()
                            if len(parts) >= 3:
                                try:
                                    pid = int(parts[2])
                                    if pid > 0:
                                        pids.add(pid)
                                except ValueError:
                                    continue
                        self.window_pids = pids
                        return
                except FileNotFoundError:
                    pass  # wmctrl not installed, fall back to xprop
                except:
                    pass

                # Fallback to xprop (slower)
                try:
                    result = subprocess.run(
                        ['xprop', '-root', '_NET_CLIENT_LIST'],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0:
                        window_ids = re.findall(r'0x[0-9a-fA-F]+', result.stdout)
                        # Limit to first 50 windows to avoid slowdown
                        for wid in window_ids[:50]:
                            try:
                                pid_result = subprocess.run(
                                    ['xprop', '-id', wid, '_NET_WM_PID'],
                                    capture_output=True, text=True, timeout=0.2
                                )
                                if '_NET_WM_PID' in pid_result.stdout:
                                    match = re.search(r'=\s*(\d+)', pid_result.stdout)
                                    if match:
                                        pids.add(int(match.group(1)))
                            except:
                                continue
                except:
                    pass
                self.window_pids = pids
            finally:
                self._window_pid_thread_running = False

        # Run in background thread to avoid blocking UI
        self._window_pid_thread_running = True
        threading.Thread(target=_fetch_pids, daemon=True).start()

    def _classify_process(self, pid, name):
        """Classify process as app or background"""
        # Check cache first (fast path)
        if pid in self.classification_cache:
            cached = self.classification_cache[pid]
            # Re-check window_pids for previously non-app processes
            if not cached and pid in self.window_pids:
                self.classification_cache[pid] = True
                return True
            return cached

        name_lower = name.lower()

        # Quick blacklist check (no system calls needed) - case insensitive
        if name_lower in BLACKLIST or name_lower in PARENT_BLACKLIST:
            self.classification_cache[pid] = False
            return False

        # Also check for partial matches (e.g., crashpad in chrome_crashpad_handler)
        if any(bl in name_lower for bl in ['crashpad', 'helper', 'zygote', 'nacl_helper']):
            self.classification_cache[pid] = False
            return False

        # Check if it has a window (fast set lookup)
        if pid in self.window_pids:
            self.classification_cache[pid] = True
            return True

        # Check app patterns (no system calls)
        if any(pat in name_lower for pat in APP_PATTERNS):
            self.classification_cache[pid] = True
            return True

        # Only do expensive uid check if nothing else matched
        try:
            proc = psutil.Process(pid)
            if proc.uids().real != os.getuid():
                self.classification_cache[pid] = False
                return False
        except:
            self.classification_cache[pid] = False
            return False

        self.classification_cache[pid] = False
        return False

    def update_data(self, data):
        """Update process data from backend"""
        self.process_data = data

        # Periodic cache cleanup (every 30 updates)
        self._cache_cleanup_counter += 1
        if self._cache_cleanup_counter >= 30:
            self._cache_cleanup_counter = 0
            current_pids = {int(d[0]) for d in data}
            # Remove stale entries
            self.classification_cache = {
                pid: val for pid, val in self.classification_cache.items()
                if pid in current_pids
            }

        apps = {}
        background = {}

        for pid, name, state, cpu, mem, threads in data:
            int_pid = int(pid)
            cpu_val = float(cpu)
            mem_mb = int(mem) / 1024

            is_app = self._classify_process(int_pid, name)
            target = apps if is_app else background

            if name not in target:
                target[name] = {'pids': [], 'cpu': 0.0, 'mem': 0.0, 'state': state, 'details': {}}

            target[name]['pids'].append(int_pid)
            target[name]['cpu'] += cpu_val
            target[name]['mem'] += mem_mb
            # Store individual process details for expansion
            target[name]['details'][int_pid] = {'cpu': cpu_val, 'mem': mem_mb}

        self._update_rows(apps, background)
        self.count_label.configure(text=f"{len(data)} processes")
        self.process_groups = {**apps, **background}

    def _update_rows(self, apps, background):
        """Update process rows"""
        current_keys = set()

        for name in apps:
            current_keys.add(('app', name))
        for name in background:
            current_keys.add(('bg', name))

        existing_keys = set(self.rows.keys())
        to_add = current_keys - existing_keys
        to_remove = existing_keys - current_keys
        to_update = current_keys & existing_keys

        # Remove dead processes
        for key in to_remove:
            self.rows[key].destroy()
            del self.rows[key]

        # Update existing
        for key in to_update:
            section, name = key
            info = apps[name] if section == 'app' else background[name]
            self.rows[key].update_data(
                info['cpu'], info['mem'], info['state'], info['pids'],
                process_details=info.get('details', {})
            )

        # Add new
        for key in to_add:
            section, name = key
            if section == 'app':
                info = apps[name]
                # Get icon for app
                icon = self.icon_loader.get_icon(name)
                row = ProcessRow(
                    self.apps_container, name, info['pids'],
                    info['cpu'], info['mem'], info['state'], is_app=True,
                    on_select=self._on_row_select, on_context=self._show_context_menu,
                    process_details=info.get('details', {}), icon=icon
                )
            else:
                info = background[name]
                row = ProcessRow(
                    self.bg_container, name, info['pids'],
                    info['cpu'], info['mem'], info['state'], is_app=False,
                    on_select=self._on_row_select, on_context=self._show_context_menu,
                    process_details=info.get('details', {})
                )
            self.rows[key] = row
            row.pack(fill=tk.X)

        self.apps_header.set_count(len(apps))
        self.bg_header.set_count(len(background))

    def _on_row_select(self, row):
        """Handle row selection"""
        if self.selected_row:
            self.selected_row.set_selected(False)

        self.selected_row = row
        row.set_selected(True)
        self.end_btn.configure(state=tk.NORMAL)

    def _show_context_menu(self, event, row):
        """Show right-click context menu"""
        menu = Menu(self, tearoff=0)
        menu.configure(bg=COLORS['surface'], fg=COLORS['text_primary'],
                      activebackground=COLORS['selection'], activeforeground=COLORS['text_primary'])

        # Different label for single process vs group
        if isinstance(row, SubProcessRow):
            menu.add_command(label=f"End Process (PID {row.pid})", command=self._kill_selected)
            menu.add_command(label="Force Kill (SIGKILL)", command=self._force_kill_selected)
        else:
            if len(row.pids) > 1:
                menu.add_command(label=f"End All ({len(row.pids)} processes)", command=self._kill_selected)
            else:
                menu.add_command(label="End Task", command=self._kill_selected)
            menu.add_command(label="Force Kill (SIGKILL)", command=self._force_kill_selected)

        menu.add_separator()
        menu.add_command(label="Properties", command=lambda: self._show_details(row))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_details(self, row):
        """Show process details dialog"""
        dialog = tk.Toplevel(self)

        # Handle both ProcessRow and SubProcessRow
        is_sub = isinstance(row, SubProcessRow)
        title = f"PID {row.pid}" if is_sub else row.name
        dialog.title(f"Properties - {title}")
        dialog.geometry("420x320")
        dialog.configure(bg=COLORS['bg_secondary'])
        dialog.transient(self)

        content = tk.Frame(dialog, bg=COLORS['bg_secondary'])
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Cache header font for dialog
        header_font = Theme.get_font(Theme.FONT_SIZE_HEADER, bold=True)

        tk.Label(
            content, text=title,
            font=header_font,
            bg=COLORS['bg_secondary'], fg=COLORS['text_primary']
        ).pack(anchor='w', pady=(0, 16))

        if is_sub:
            details = [
                ("Process Name", row.name),
                ("PID", str(row.pid)),
                ("CPU Usage", f"{row.cpu:.2f}%"),
                ("Memory", f"{row.mem:.2f} MiB" if row.mem < 1024 else f"{row.mem/1024:.2f} GiB"),
            ]
        else:
            details = [
                ("Type", "Application" if row.is_app else "Background process"),
                ("PIDs", ", ".join(str(p) for p in row.pids[:5]) + ("..." if len(row.pids) > 5 else "")),
                ("Process Count", str(len(row.pids))),
                ("Total CPU", f"{row.cpu:.2f}%"),
                ("Total Memory", f"{row.mem:.2f} MiB" if row.mem < 1024 else f"{row.mem/1024:.2f} GiB"),
            ]

        try:
            pid = row.pid if is_sub else row.pids[0]
            proc = psutil.Process(pid)
            details.append(("User", proc.username()))
            details.append(("Threads", str(proc.num_threads())))
            details.append(("Status", proc.status()))
            if not is_sub:
                details.append(("Executable", proc.exe()[:50] + "..." if len(proc.exe()) > 50 else proc.exe()))
        except:
            pass

        for label, value in details:
            row_frame = tk.Frame(content, bg=COLORS['bg_secondary'])
            row_frame.pack(fill=tk.X, pady=4)

            tk.Label(
                row_frame, text=f"{label}:", width=14, anchor='w',
                font=_FONT_BODY,
                bg=COLORS['bg_secondary'], fg=COLORS['text_secondary']
            ).pack(side=tk.LEFT)

            tk.Label(
                row_frame, text=value, anchor='w',
                font=_FONT_BODY,
                bg=COLORS['bg_secondary'], fg=COLORS['text_primary']
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _kill_selected(self):
        """Kill selected process"""
        if not self.selected_row:
            return

        row = self.selected_row
        pids = row.pids
        is_sub = isinstance(row, SubProcessRow)

        if is_sub:
            msg = f"End process PID {row.pid}?"
        else:
            msg = f"End '{row.name}'?"
            if len(pids) > 1:
                msg += f"\n\n{len(pids)} processes will be terminated."

        if not messagebox.askyesno("End task", msg):
            return

        killed = 0
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
            except:
                pass

        time.sleep(0.3)

        for pid in pids:
            try:
                if psutil.Process(pid).is_running():
                    os.kill(pid, signal.SIGKILL)
            except:
                pass

        if killed > 0:
            if is_sub:
                messagebox.showinfo("Success", f"Terminated process {row.pid}")
            else:
                messagebox.showinfo("Success", f"Terminated {killed} process(es)")

        self.selected_row = None
        self.end_btn.configure(state=tk.DISABLED)

    def _force_kill_selected(self):
        """Force kill with SIGKILL"""
        if not self.selected_row:
            return

        row = self.selected_row
        is_sub = isinstance(row, SubProcessRow)

        for pid in row.pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except:
                pass

        if is_sub:
            messagebox.showinfo("Success", f"Sent SIGKILL to process {row.pid}")
        else:
            messagebox.showinfo("Success", f"Sent SIGKILL to {len(row.pids)} process(es)")
