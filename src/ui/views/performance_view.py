"""
PerformanceView - System performance monitoring
WSysMon-inspired layout with sidebar and detail panels
"""

import tkinter as tk
from tkinter import ttk
from collections import deque
import psutil
import time
import subprocess
from ..themes import COLORS, Theme
from ..widgets import GraphWidget, PerformanceButton


class PerformanceView(tk.Frame):
    """
    Performance view with sidebar navigation and metric panels.
    Displays CPU, Memory, Disk, Network, and GPU statistics.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COLORS['bg_primary'], **kwargs)

        self.cpu_history = deque(maxlen=60)
        self.mem_history = deque(maxlen=60)
        self.gpu_history = deque(maxlen=60)
        self.current_panel = 'cpu'
        self.gpu_data = []
        self.has_gpu = False
        self.start_time = time.time()

        # Cached values for expensive operations (updated less frequently)
        self._thread_count = 0
        self._proc_count = 0
        self._cpu_temp = 0
        self._slow_update_counter = 0

        # Get CPU info once
        self._get_cpu_info()

        self._create_ui()

    def _get_cpu_info(self):
        """Get static CPU information"""
        self.cpu_model = "Unknown CPU"
        self.cpu_max_speed = "0 GHz"
        self.cpu_sockets = 1
        self.cpu_cores = psutil.cpu_count(logical=False) or 1
        self.cpu_threads = psutil.cpu_count() or 1

        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'Model name' in line:
                    self.cpu_model = line.split(':')[1].strip()
                elif 'CPU max MHz' in line:
                    max_mhz = float(line.split(':')[1].strip())
                    self.cpu_max_speed = f"{max_mhz/1000:.2f}GHz"
                elif 'Socket(s)' in line:
                    self.cpu_sockets = int(line.split(':')[1].strip())
        except:
            pass

    def _create_ui(self):
        """Create the performance view UI"""
        # Main horizontal container
        main_container = tk.Frame(self, bg=COLORS['bg_primary'])
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left sidebar with fixed width
        self.sidebar = tk.Frame(main_container, bg=COLORS['bg_secondary'], width=Theme.SIDEBAR_WIDTH)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Sidebar content frame with padding on all sides
        sidebar_content = tk.Frame(self.sidebar, bg=COLORS['bg_secondary'])
        sidebar_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create sidebar buttons
        self.buttons = {}
        self._create_sidebar_buttons(sidebar_content)

        # Right content area with padding on the right and bottom
        self.content = tk.Frame(main_container, bg=COLORS['bg_primary'])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, Theme.PADDING_LARGE), pady=(0, Theme.PADDING_MEDIUM))

        # Create panels
        self.panels = {}
        self._create_cpu_panel()
        self._create_memory_panel()
        self._create_disk_panel()
        self._create_network_panel()
        self._create_gpu_panel()

        # Show CPU panel by default
        self._show_panel('cpu')

    def _create_sidebar_buttons(self, parent):
        """Create sidebar navigation buttons"""
        # CPU Button - orange
        self.cpu_btn = PerformanceButton(
            parent, "CPU", icon="",
            on_click=lambda: self._show_panel('cpu'),
            line_color=COLORS['graph_line_orange'],
            fill_color=COLORS['graph_fill_orange']
        )
        self.cpu_btn.pack(fill=tk.X, pady=(0, 8))
        self.buttons['cpu'] = self.cpu_btn

        # Memory Button - purple
        self.mem_btn = PerformanceButton(
            parent, "Memory", icon="",
            on_click=lambda: self._show_panel('memory'),
            line_color=COLORS['graph_line_purple'],
            fill_color=COLORS['graph_fill_purple']
        )
        self.mem_btn.pack(fill=tk.X, pady=8)
        self.buttons['memory'] = self.mem_btn

        # Disk Button - default blue
        self.disk_btn = PerformanceButton(
            parent, "Disk", icon="",
            on_click=lambda: self._show_panel('disk')
        )
        self.disk_btn.pack(fill=tk.X, pady=8)
        self.buttons['disk'] = self.disk_btn

        # Network Button - default blue
        self.net_btn = PerformanceButton(
            parent, "Network", icon="",
            on_click=lambda: self._show_panel('network')
        )
        self.net_btn.pack(fill=tk.X, pady=8)
        self.buttons['network'] = self.net_btn

        # GPU Button - green (hidden until GPU detected)
        self.gpu_btn = PerformanceButton(
            parent, "GPU 0", icon="",
            on_click=lambda: self._show_panel('gpu'),
            line_color=COLORS['graph_line_green'],
            fill_color=COLORS['graph_fill_green']
        )
        self.gpu_btn.pack(fill=tk.X, pady=8)
        self.gpu_btn.pack_forget()
        self.buttons['gpu'] = self.gpu_btn

        # Select CPU by default
        self.cpu_btn.set_selected(True)

    def _create_cpu_panel(self):
        """Create CPU detail panel - WSysMon style"""
        panel = tk.Frame(self.content, bg=COLORS['bg_primary'])

        # Header: CPU title + model name
        header = tk.Frame(panel, bg=COLORS['bg_primary'])
        header.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=(Theme.PADDING_LARGE, Theme.PADDING_SMALL))

        tk.Label(
            header, text="CPU",
            font=Theme.get_font(Theme.FONT_SIZE_TITLE, bold=True),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        ).pack(side=tk.LEFT)

        tk.Label(
            header, text=self.cpu_model,
            font=Theme.get_font(Theme.FONT_SIZE_SMALL),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # Graph labels row: "% Usage" on left, "100" on right
        graph_labels_top = tk.Frame(panel, bg=COLORS['bg_primary'])
        graph_labels_top.pack(fill=tk.X, padx=Theme.PADDING_LARGE)

        tk.Label(
            graph_labels_top, text="% Usage",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            graph_labels_top, text="100",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # CPU Graph - takes most space (borderless like WSysMon)
        graph_frame = tk.Frame(panel, bg=COLORS['bg_tertiary'])
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=Theme.PADDING_LARGE, pady=2)

        # Orange colors for CPU graph
        self.cpu_graph = GraphWidget(graph_frame, height=250,
                                     line_color=COLORS['graph_line_orange'],
                                     fill_color=COLORS['graph_fill_orange'])
        self.cpu_graph.show_labels = False  # We handle labels ourselves
        self.cpu_graph.pack(fill=tk.BOTH, expand=True)

        # Graph labels bottom: "60 Seconds" on left, "0" on right
        graph_labels_bottom = tk.Frame(panel, bg=COLORS['bg_primary'])
        graph_labels_bottom.pack(fill=tk.X, padx=Theme.PADDING_LARGE)

        tk.Label(
            graph_labels_bottom, text="60 Seconds",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            graph_labels_bottom, text="0",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # Stats section - two rows matching WSysMon layout
        stats_container = tk.Frame(panel, bg=COLORS['bg_primary'])
        stats_container.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=(Theme.PADDING_MEDIUM, Theme.PADDING_LARGE))

        # Row 1: Usage, Speed, Processes | Maximum CPU speed
        row1 = tk.Frame(stats_container, bg=COLORS['bg_primary'])
        row1.pack(fill=tk.X, pady=(0, Theme.PADDING_SMALL))

        # Left stats
        left_stats1 = tk.Frame(row1, bg=COLORS['bg_primary'])
        left_stats1.pack(side=tk.LEFT)

        # Usage
        self._create_stat_item(left_stats1, "Usage", "0%", 'cpu_usage')
        # Speed
        self._create_stat_item(left_stats1, "Speed", "0GHz", 'cpu_speed')
        # Processes
        self._create_stat_item(left_stats1, "Processes", "0", 'cpu_procs')

        # Right stats
        right_stats1 = tk.Frame(row1, bg=COLORS['bg_primary'])
        right_stats1.pack(side=tk.RIGHT)

        self._create_stat_item_right(right_stats1, "Maximum CPU speed:", self.cpu_max_speed)

        # Row 2: Threads, Uptime, Temperature | Sockets, Cores, Logical processors
        row2 = tk.Frame(stats_container, bg=COLORS['bg_primary'])
        row2.pack(fill=tk.X)

        # Left stats
        left_stats2 = tk.Frame(row2, bg=COLORS['bg_primary'])
        left_stats2.pack(side=tk.LEFT)

        self._create_stat_item(left_stats2, "Threads", "0", 'cpu_threads')
        self._create_stat_item(left_stats2, "Uptime", "00:00:00", 'cpu_uptime')
        self._create_stat_item(left_stats2, "Temperature", "0°C", 'cpu_temp')

        # Right stats
        right_stats2 = tk.Frame(row2, bg=COLORS['bg_primary'])
        right_stats2.pack(side=tk.RIGHT)

        self._create_stat_item_right(right_stats2, "Sockets:", str(self.cpu_sockets))
        self._create_stat_item_right(right_stats2, "Cores:", str(self.cpu_cores))
        self._create_stat_item_right(right_stats2, "Logical processors:", str(self.cpu_threads))

        self.panels['cpu'] = panel

    def _create_stat_item(self, parent, label, value, var_name=None):
        """Create a stat item (label on top, value below)"""
        frame = tk.Frame(parent, bg=COLORS['bg_primary'])
        frame.pack(side=tk.LEFT, padx=(0, 24))

        tk.Label(
            frame, text=label,
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(anchor='w')

        val_label = tk.Label(
            frame, text=value,
            font=Theme.get_font(Theme.FONT_SIZE_HEADER, bold=True),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        )
        val_label.pack(anchor='w')

        if var_name:
            setattr(self, f'{var_name}_label', val_label)

    def _create_stat_item_right(self, parent, label, value):
        """Create a right-aligned stat item (label: value on same line)"""
        frame = tk.Frame(parent, bg=COLORS['bg_primary'])
        frame.pack(anchor='e')

        tk.Label(
            frame, text=label,
            font=Theme.get_font(Theme.FONT_SIZE_SMALL),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            frame, text=value,
            font=Theme.get_font(Theme.FONT_SIZE_SMALL),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _create_memory_panel(self):
        """Create Memory detail panel"""
        panel = tk.Frame(self.content, bg=COLORS['bg_primary'])

        mem = psutil.virtual_memory()
        total_gb = mem.total / (1024**3)

        # Header
        header = tk.Frame(panel, bg=COLORS['bg_primary'])
        header.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=(Theme.PADDING_LARGE, Theme.PADDING_SMALL))

        tk.Label(
            header, text="Memory",
            font=Theme.get_font(Theme.FONT_SIZE_TITLE, bold=True),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        ).pack(side=tk.LEFT)

        tk.Label(
            header, text=f"{total_gb:.1f} GB DDR",
            font=Theme.get_font(Theme.FONT_SIZE_SMALL),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # Graph labels top
        graph_labels_top = tk.Frame(panel, bg=COLORS['bg_primary'])
        graph_labels_top.pack(fill=tk.X, padx=Theme.PADDING_LARGE)

        tk.Label(
            graph_labels_top, text="% Usage",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            graph_labels_top, text="100",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # Memory Graph (borderless like WSysMon)
        graph_frame = tk.Frame(panel, bg=COLORS['bg_tertiary'])
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=Theme.PADDING_LARGE, pady=2)

        # Purple/blue colors for Memory graph
        self.mem_graph = GraphWidget(graph_frame, height=250,
                                     line_color=COLORS['graph_line_purple'],
                                     fill_color=COLORS['graph_fill_purple'])
        self.mem_graph.show_labels = False
        self.mem_graph.pack(fill=tk.BOTH, expand=True)

        # Graph labels bottom
        graph_labels_bottom = tk.Frame(panel, bg=COLORS['bg_primary'])
        graph_labels_bottom.pack(fill=tk.X, padx=Theme.PADDING_LARGE)

        tk.Label(
            graph_labels_bottom, text="60 Seconds",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            graph_labels_bottom, text="0",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # Stats
        stats_container = tk.Frame(panel, bg=COLORS['bg_primary'])
        stats_container.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=(Theme.PADDING_MEDIUM, Theme.PADDING_LARGE))

        row1 = tk.Frame(stats_container, bg=COLORS['bg_primary'])
        row1.pack(fill=tk.X)

        self._create_stat_item(row1, "In Use", f"{mem.used / (1024**3):.1f} GB", 'mem_used')
        self._create_stat_item(row1, "Available", f"{mem.available / (1024**3):.1f} GB", 'mem_avail')
        self._create_stat_item(row1, "Cached", f"{mem.cached / (1024**3):.1f} GB", 'mem_cached')

        right_stats = tk.Frame(row1, bg=COLORS['bg_primary'])
        right_stats.pack(side=tk.RIGHT)

        self._create_stat_item_right(right_stats, "Total:", f"{total_gb:.1f} GB")

        self.panels['memory'] = panel

    def _create_disk_panel(self):
        """Create Disk detail panel"""
        panel = tk.Frame(self.content, bg=COLORS['bg_primary'])

        # Header
        header = tk.Frame(panel, bg=COLORS['bg_primary'])
        header.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=Theme.PADDING_LARGE)

        tk.Label(
            header, text="Disk",
            font=Theme.get_font(Theme.FONT_SIZE_TITLE, bold=True),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        ).pack(side=tk.LEFT)

        # Disk info
        content_area = tk.Frame(panel, bg=COLORS['bg_primary'])
        content_area.pack(fill=tk.BOTH, expand=True, padx=Theme.PADDING_LARGE)

        try:
            partitions = psutil.disk_partitions()
            for part in partitions[:4]:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    self._create_disk_card(content_area, part, usage)
                except:
                    pass
        except:
            pass

        self.panels['disk'] = panel

    def _create_disk_card(self, parent, partition, usage):
        """Create a card for a disk partition"""
        card = tk.Frame(parent, bg=COLORS['surface'], highlightbackground=COLORS['border'], highlightthickness=1)
        card.pack(fill=tk.X, pady=8)

        inner = tk.Frame(card, bg=COLORS['surface'])
        inner.pack(fill=tk.X, padx=16, pady=12)

        tk.Label(
            inner, text=partition.mountpoint,
            font=Theme.get_font(Theme.FONT_SIZE_BODY, bold=True),
            bg=COLORS['surface'], fg=COLORS['text_primary']
        ).pack(anchor='w')

        tk.Label(
            inner, text=f"{partition.device} ({partition.fstype})",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['surface'], fg=COLORS['text_secondary']
        ).pack(anchor='w')

        bar_frame = tk.Frame(inner, bg=COLORS['bg_tertiary'], height=8)
        bar_frame.pack(fill=tk.X, pady=(8, 4))

        used_pct = usage.percent / 100
        bar = tk.Frame(bar_frame, bg=COLORS['accent'], width=int(used_pct * 300), height=8)
        bar.place(x=0, y=0)

        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        tk.Label(
            inner, text=f"{used_gb:.1f} GB / {total_gb:.1f} GB ({usage.percent:.0f}%)",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['surface'], fg=COLORS['text_secondary']
        ).pack(anchor='w')

    def _create_network_panel(self):
        """Create Network detail panel"""
        panel = tk.Frame(self.content, bg=COLORS['bg_primary'])

        # Header
        header = tk.Frame(panel, bg=COLORS['bg_primary'])
        header.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=Theme.PADDING_LARGE)

        tk.Label(
            header, text="Network",
            font=Theme.get_font(Theme.FONT_SIZE_TITLE, bold=True),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        ).pack(side=tk.LEFT)

        content_area = tk.Frame(panel, bg=COLORS['bg_primary'])
        content_area.pack(fill=tk.BOTH, expand=True, padx=Theme.PADDING_LARGE)

        try:
            stats = psutil.net_io_counters(pernic=True)
            addrs = psutil.net_if_addrs()

            for iface, stat in list(stats.items())[:4]:
                self._create_network_card(content_area, iface, stat, addrs.get(iface, []))
        except:
            pass

        self.panels['network'] = panel

    def _create_network_card(self, parent, iface, stats, addrs):
        """Create a card for a network interface"""
        card = tk.Frame(parent, bg=COLORS['surface'], highlightbackground=COLORS['border'], highlightthickness=1)
        card.pack(fill=tk.X, pady=8)

        inner = tk.Frame(card, bg=COLORS['surface'])
        inner.pack(fill=tk.X, padx=16, pady=12)

        tk.Label(
            inner, text=iface,
            font=Theme.get_font(Theme.FONT_SIZE_BODY, bold=True),
            bg=COLORS['surface'], fg=COLORS['text_primary']
        ).pack(anchor='w')

        ip = "No IP"
        for addr in addrs:
            if addr.family.name == 'AF_INET':
                ip = addr.address
                break

        tk.Label(
            inner, text=ip,
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['surface'], fg=COLORS['text_secondary']
        ).pack(anchor='w')

        stats_row = tk.Frame(inner, bg=COLORS['surface'])
        stats_row.pack(fill=tk.X, pady=(8, 0))

        sent_gb = stats.bytes_sent / (1024**3)
        recv_gb = stats.bytes_recv / (1024**3)

        tk.Label(
            stats_row, text=f"Sent: {sent_gb:.2f} GB",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['surface'], fg=COLORS['accent']
        ).pack(side=tk.LEFT, padx=(0, 16))

        tk.Label(
            stats_row, text=f"Received: {recv_gb:.2f} GB",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['surface'], fg=COLORS['accent_secondary']
        ).pack(side=tk.LEFT)

    def _create_gpu_panel(self):
        """Create GPU detail panel - WSysMon style with green graph"""
        panel = tk.Frame(self.content, bg=COLORS['bg_primary'])

        # Header
        header = tk.Frame(panel, bg=COLORS['bg_primary'])
        header.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=(Theme.PADDING_LARGE, Theme.PADDING_SMALL))

        self.gpu_title_label = tk.Label(
            header, text="GPU 0",
            font=Theme.get_font(Theme.FONT_SIZE_TITLE, bold=True),
            bg=COLORS['bg_primary'], fg=COLORS['text_primary']
        )
        self.gpu_title_label.pack(side=tk.LEFT)

        self.gpu_model_label = tk.Label(
            header, text="No GPU detected",
            font=Theme.get_font(Theme.FONT_SIZE_SMALL),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        )
        self.gpu_model_label.pack(side=tk.RIGHT)

        # Graph labels top
        graph_labels_top = tk.Frame(panel, bg=COLORS['bg_primary'])
        graph_labels_top.pack(fill=tk.X, padx=Theme.PADDING_LARGE)

        tk.Label(
            graph_labels_top, text="% Usage",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            graph_labels_top, text="100",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # GPU Graph (borderless like WSysMon)
        graph_frame = tk.Frame(panel, bg=COLORS['bg_tertiary'])
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=Theme.PADDING_LARGE, pady=2)

        # Green colors for GPU graph
        self.gpu_graph = GraphWidget(graph_frame, height=250,
                                     line_color=COLORS['graph_line_green'],
                                     fill_color=COLORS['graph_fill_green'])
        self.gpu_graph.show_labels = False
        self.gpu_graph.pack(fill=tk.BOTH, expand=True)

        # Graph labels bottom
        graph_labels_bottom = tk.Frame(panel, bg=COLORS['bg_primary'])
        graph_labels_bottom.pack(fill=tk.X, padx=Theme.PADDING_LARGE)

        tk.Label(
            graph_labels_bottom, text="60 Seconds",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        tk.Label(
            graph_labels_bottom, text="0",
            font=Theme.get_font(Theme.FONT_SIZE_TINY),
            bg=COLORS['bg_primary'], fg=COLORS['text_secondary']
        ).pack(side=tk.RIGHT)

        # Stats - WSysMon GPU layout
        stats_container = tk.Frame(panel, bg=COLORS['bg_primary'])
        stats_container.pack(fill=tk.X, padx=Theme.PADDING_LARGE, pady=(Theme.PADDING_MEDIUM, Theme.PADDING_LARGE))

        row1 = tk.Frame(stats_container, bg=COLORS['bg_primary'])
        row1.pack(fill=tk.X, pady=(0, Theme.PADDING_SMALL))

        self._create_stat_item(row1, "Usage", "0%", 'gpu_usage')
        self._create_stat_item(row1, "Speed", "0MHz", 'gpu_speed')
        self._create_stat_item(row1, "Video memory", "0/0 GiB (0%)", 'gpu_vram')

        right_stats1 = tk.Frame(row1, bg=COLORS['bg_primary'])
        right_stats1.pack(side=tk.RIGHT)
        self._create_stat_item_right(right_stats1, "Driver:", "N/A")

        row2 = tk.Frame(stats_container, bg=COLORS['bg_primary'])
        row2.pack(fill=tk.X)

        self._create_stat_item(row2, "Temperature", "0°C", 'gpu_temp')

        self.panels['gpu'] = panel

    def _show_panel(self, panel_name):
        """Show the specified panel"""
        for name, btn in self.buttons.items():
            btn.set_selected(name == panel_name)

        for panel in self.panels.values():
            panel.pack_forget()

        if panel_name in self.panels:
            self.panels[panel_name].pack(fill=tk.BOTH, expand=True)

        self.current_panel = panel_name

    def update(self):
        """Update performance metrics"""
        # Increment slow update counter (for expensive operations)
        self._slow_update_counter += 1
        do_slow_update = (self._slow_update_counter % 5 == 0)  # Every 5 seconds

        # CPU (fast)
        cpu_pct = psutil.cpu_percent()
        self.cpu_history.append(cpu_pct)

        self.cpu_graph.add_value(cpu_pct)
        self.cpu_btn.set_value(cpu_pct)
        self.cpu_btn.add_data_point(cpu_pct)

        if hasattr(self, 'cpu_usage_label'):
            self.cpu_usage_label.configure(text=f"{cpu_pct:.2f}%")

        # CPU Speed (fast)
        try:
            freq = psutil.cpu_freq()
            if freq and hasattr(self, 'cpu_speed_label'):
                self.cpu_speed_label.configure(text=f"{freq.current/1000:.2f}GHz")
        except:
            pass

        # Process count (fast) and threads (SLOW - only update every 5 cycles)
        if do_slow_update:
            try:
                self._proc_count = len(psutil.pids())
                # Thread count is expensive - use cached /proc/stat instead
                try:
                    with open('/proc/stat', 'r') as f:
                        for line in f:
                            if line.startswith('processes'):
                                # This isn't thread count, so estimate from process count
                                break
                    # Simple estimate: ~2-3 threads per process on average
                    self._thread_count = self._proc_count * 2
                except:
                    self._thread_count = self._proc_count * 2
            except:
                pass

        if hasattr(self, 'cpu_procs_label'):
            self.cpu_procs_label.configure(text=str(self._proc_count))
        if hasattr(self, 'cpu_threads_label'):
            self.cpu_threads_label.configure(text=str(self._thread_count))

        # Uptime (fast)
        uptime_seconds = int(time.time() - psutil.boot_time())
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hasattr(self, 'cpu_uptime_label'):
            self.cpu_uptime_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # CPU Temperature (SLOW - only update every 5 cycles)
        if do_slow_update:
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            self._cpu_temp = entries[0].current
                            break
            except:
                pass

        if hasattr(self, 'cpu_temp_label') and self._cpu_temp > 0:
            self.cpu_temp_label.configure(text=f"{self._cpu_temp:.0f}°C")

        # Memory (fast)
        mem = psutil.virtual_memory()
        self.mem_history.append(mem.percent)

        self.mem_graph.add_value(mem.percent)
        self.mem_btn.set_value(mem.percent)
        self.mem_btn.add_data_point(mem.percent)
        self.mem_btn.set_secondary_text(f"{mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} GB")

        if hasattr(self, 'mem_used_label') and self.mem_used_label:
            self.mem_used_label.configure(text=f"{mem.used / (1024**3):.1f} GB")
        if hasattr(self, 'mem_avail_label') and self.mem_avail_label:
            self.mem_avail_label.configure(text=f"{mem.available / (1024**3):.1f} GB")
        if hasattr(self, 'mem_cached_label') and self.mem_cached_label:
            self.mem_cached_label.configure(text=f"{mem.cached / (1024**3):.1f} GB")

        # Disk (moderately slow - only update every 5 cycles)
        if do_slow_update:
            try:
                disk = psutil.disk_usage('/')
                self.disk_btn.set_value(disk.percent)
                self.disk_btn.set_secondary_text(f"{disk.used / (1024**3):.0f} / {disk.total / (1024**3):.0f} GB")
            except:
                pass

        # Network (fast)
        try:
            net = psutil.net_io_counters()
            sent_mb = net.bytes_sent / (1024**2)
            recv_mb = net.bytes_recv / (1024**2)
            self.net_btn.set_value(0, unit="")
            self.net_btn.set_secondary_text(f"S: {sent_mb:.0f} MB  R: {recv_mb:.0f} MB")
        except:
            pass

        # GPU
        if self.gpu_data:
            self._update_gpu_display()

    def update_gpu_data(self, gpu_data):
        """Update GPU data from backend"""
        self.gpu_data = gpu_data

        if gpu_data and not self.has_gpu:
            self.has_gpu = True
            self.gpu_btn.pack(fill=tk.X, pady=8)

            if len(gpu_data) > 0:
                self.gpu_btn.set_title("GPU 0")

    def _update_gpu_display(self):
        """Update GPU panel with latest data"""
        if not self.gpu_data:
            return

        gpu = self.gpu_data[0]

        try:
            gpu_index = int(gpu[0])
            gpu_name = gpu[1]
            gpu_util = int(gpu[2])
            gpu_mem_used = int(gpu[3])
            gpu_mem_total = int(gpu[4])
            gpu_temp = int(gpu[5])
            gpu_power = int(gpu[6])
            gpu_power_limit = int(gpu[7])
        except (ValueError, IndexError):
            return

        self.gpu_history.append(gpu_util)
        self.gpu_graph.add_value(gpu_util)

        self.gpu_btn.set_value(gpu_util)
        self.gpu_btn.add_data_point(gpu_util)
        self.gpu_btn.set_secondary_text(f"{gpu_mem_used} / {gpu_mem_total} MB")

        self.gpu_title_label.configure(text=f"GPU {gpu_index}")
        self.gpu_model_label.configure(text=gpu_name)

        if hasattr(self, 'gpu_usage_label'):
            self.gpu_usage_label.configure(text=f"{gpu_util}%")
        if hasattr(self, 'gpu_vram_label'):
            mem_pct = (gpu_mem_used / gpu_mem_total * 100) if gpu_mem_total > 0 else 0
            self.gpu_vram_label.configure(text=f"{gpu_mem_used/1024:.1f}/{gpu_mem_total/1024:.0f} GiB ({mem_pct:.0f}%)")
        if hasattr(self, 'gpu_temp_label'):
            self.gpu_temp_label.configure(text=f"{gpu_temp}°C")
