"""
MainWindow - Task Manager Application
WSysMon-inspired main window with tabbed interface
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys

from .themes import COLORS, Theme
from .views import ProcessesView, PerformanceView


class TaskManagerApp:
    """
    Main Task Manager application.
    Coordinates backend communication and view updates.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Task Manager")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        self.root.configure(bg=COLORS['bg_primary'])

        # Load app icon
        self._app_icon = None
        self._sidebar_icon = None
        self._load_app_icon()

        # State
        self.running = True
        self.proc = None
        self.current_view = 'processes'

        # Setup UI
        self._setup_styles()
        self._create_ui()

        # Start backend
        self._start_backend()

        # Start periodic updates
        self._start_updates()

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_app_icon(self):
        """Load the white app icon and set as window icon"""
        try:
            src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(src_dir, 'activity-tracker-white.png')
            if os.path.exists(icon_path):
                from PIL import Image, ImageTk

                icon = Image.open(icon_path).convert('RGBA')

                # Window titlebar icon: composite onto dark bg
                win_bg = Image.new('RGBA', (32, 32), (36, 36, 36, 255))
                win_icon = icon.resize((32, 32), Image.LANCZOS)
                win_bg.paste(win_icon, mask=win_icon.split()[3])
                self._app_icon = ImageTk.PhotoImage(win_bg.convert('RGB'))
                self.root.iconphoto(False, self._app_icon)

                # Sidebar icon: composite onto sidebar bg (#242424)
                side_bg = Image.new('RGBA', (22, 22), (0x24, 0x24, 0x24, 255))
                side_icon = icon.resize((22, 22), Image.LANCZOS)
                side_bg.paste(side_icon, mask=side_icon.split()[3])
                self._sidebar_icon = ImageTk.PhotoImage(side_bg.convert('RGB'))
        except Exception:
            pass

    def _setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Notebook (tabs)
        style.configure(
            'TNotebook',
            background=COLORS['bg_primary'],
            borderwidth=0
        )
        style.configure(
            'TNotebook.Tab',
            background=COLORS['bg_secondary'],
            foreground=COLORS['text_secondary'],
            padding=[16, 8],
            font=Theme.get_font(Theme.FONT_SIZE_BODY)
        )
        style.map(
            'TNotebook.Tab',
            background=[('selected', COLORS['accent'])],
            foreground=[('selected', COLORS['text_primary'])]
        )

        # PanedWindow
        style.configure(
            'TPanedwindow',
            background=COLORS['bg_primary']
        )

        # Scrollbar
        style.configure(
            'Vertical.TScrollbar',
            background=COLORS['surface'],
            troughcolor=COLORS['bg_secondary'],
            borderwidth=0,
            arrowsize=0
        )

    def _create_ui(self):
        """Create the main UI"""
        # Main container with sidebar and content
        self.main_container = tk.Frame(self.root, bg=COLORS['bg_primary'])
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Create sidebar
        self._create_sidebar()

        # Create content area
        self._create_content()

        # Select initial view (after views are created)
        self._select_tab('processes')

    def _create_sidebar(self):
        """Create the left sidebar with navigation"""
        sidebar = tk.Frame(
            self.main_container,
            bg=COLORS['bg_secondary'],
            width=180
        )
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # App title: icon + "Task" on line 1, "Manager" on line 2
        title_area = tk.Frame(sidebar, bg=COLORS['bg_secondary'])
        title_area.pack(padx=16, pady=(20, 24), anchor='w')

        # Line 1: icon + "Task"
        line1 = tk.Frame(title_area, bg=COLORS['bg_secondary'])
        line1.pack(anchor='w')

        if self._sidebar_icon:
            tk.Label(
                line1, image=self._sidebar_icon,
                bg=COLORS['bg_secondary']
            ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            line1,
            text="Task",
            font=Theme.get_font(Theme.FONT_SIZE_HEADER, bold=True),
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_primary']
        ).pack(side=tk.LEFT)

        # Line 2: "Manager" indented to align under "Task" (icon 22px + gap 8px = 30px)
        tk.Label(
            title_area,
            text="Manager",
            font=Theme.get_font(Theme.FONT_SIZE_HEADER, bold=True),
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_primary']
        ).pack(anchor='w', padx=(30, 0))

        # Navigation buttons
        self.tab_buttons = {}

        self.processes_tab = self._create_sidebar_button(sidebar, "Processes", 'processes')
        self.processes_tab.pack(fill=tk.X, padx=8, pady=2)

        self.performance_tab = self._create_sidebar_button(sidebar, "Performance", 'performance')
        self.performance_tab.pack(fill=tk.X, padx=8, pady=2)

    def _create_sidebar_button(self, parent, text, view_name):
        """Create a sidebar navigation button"""
        btn = tk.Frame(
            parent,
            bg=COLORS['bg_secondary'],
            cursor='hand2'
        )

        label = tk.Label(
            btn,
            text=text,
            font=Theme.get_font(Theme.FONT_SIZE_BODY),
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_secondary'],
            anchor='w'
        )
        label.pack(fill=tk.X, padx=16, pady=12)

        def on_click(e):
            self._select_tab(view_name)

        def on_enter(e):
            if self.current_view != view_name:
                btn.configure(bg=COLORS['surface_hover'])
                label.configure(bg=COLORS['surface_hover'])

        def on_leave(e):
            if self.current_view != view_name:
                btn.configure(bg=COLORS['bg_secondary'])
                label.configure(bg=COLORS['bg_secondary'])

        btn.bind('<Button-1>', on_click)
        label.bind('<Button-1>', on_click)
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)

        self.tab_buttons[view_name] = (btn, label)
        return btn

    def _select_tab(self, view_name):
        """Select a tab"""
        self.current_view = view_name

        for name, (btn, label) in self.tab_buttons.items():
            if name == view_name:
                btn.configure(bg=COLORS['accent'])
                label.configure(
                    bg=COLORS['accent'],
                    fg=COLORS['text_primary'],
                    font=Theme.get_font(Theme.FONT_SIZE_BODY, bold=True)
                )
            else:
                btn.configure(bg=COLORS['bg_secondary'])
                label.configure(
                    bg=COLORS['bg_secondary'],
                    fg=COLORS['text_secondary'],
                    font=Theme.get_font(Theme.FONT_SIZE_BODY)
                )

        # Show/hide views
        if view_name == 'processes':
            self.processes_view.pack(fill=tk.BOTH, expand=True)
            self.performance_view.pack_forget()
        else:
            self.performance_view.pack(fill=tk.BOTH, expand=True)
            self.processes_view.pack_forget()

    def _create_content(self):
        """Create the main content area"""
        self.content = tk.Frame(self.main_container, bg=COLORS['bg_primary'])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create views
        self.processes_view = ProcessesView(self.content)
        self.performance_view = PerformanceView(self.content)

        # Show processes view by default
        self.processes_view.pack(fill=tk.BOTH, expand=True)

    def _start_backend(self):
        """Start the C backend process"""
        try:
            # Find backend location
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            backend_path = os.path.join(backend_dir, 'src', 'backend', 'task_manager')
            source_path = os.path.join(backend_dir, 'src', 'backend', 'task_manager.c')

            # Also check root directory (for backward compatibility)
            if not os.path.exists(source_path):
                source_path = os.path.join(backend_dir, 'task_manager.c')
                backend_path = os.path.join(backend_dir, 'task_manager')

            # Compile if needed
            if not os.path.exists(backend_path) or (
                os.path.exists(source_path) and
                os.path.getmtime(source_path) > os.path.getmtime(backend_path)
            ):
                print(f"Compiling backend from {source_path}...")
                result = subprocess.run(
                    ['gcc', '-o', backend_path, source_path, '-Wall', '-O2'],
                    capture_output=True, text=True
                )
                if result.returncode != 0:
                    messagebox.showerror("Error", f"Failed to compile backend:\n{result.stderr}")
                    self.root.quit()
                    return

            # Start backend
            self.proc = subprocess.Popen(
                [backend_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Start reader thread
            threading.Thread(target=self._read_backend, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start backend: {e}")
            self.root.quit()

    def _read_backend(self):
        """Read data from backend"""
        frame = []
        gpu_frame = []
        in_gpu_block = False

        try:
            for line in self.proc.stdout:
                if not self.running:
                    break

                line = line.strip()
                if not line:
                    continue

                # Handle GPU data block
                if line == "GPU_START":
                    in_gpu_block = True
                    gpu_frame.clear()
                    continue
                elif line == "GPU_END":
                    in_gpu_block = False
                    if gpu_frame:
                        self.root.after(0, self._update_gpu, gpu_frame.copy())
                    continue

                if in_gpu_block:
                    if line.startswith("GPU|"):
                        parts = line.split('|')
                        if len(parts) == 9:  # GPU|index|name|util|mem_used|mem_total|temp|power|power_limit
                            gpu_frame.append(parts[1:])  # Skip "GPU" prefix
                    continue

                # Handle process data
                if line == "END":
                    if frame:
                        self.root.after(0, self._update_processes, frame.copy())
                        frame.clear()
                    continue

                parts = line.split('|')
                if len(parts) == 6:
                    frame.append(parts)

        except Exception as e:
            if self.running:
                print(f"Backend error: {e}")

    def _update_processes(self, data):
        """Update processes view with new data"""
        self.processes_view.update_data(data)

    def _update_gpu(self, gpu_data):
        """Update performance view with GPU data"""
        self.performance_view.update_gpu_data(gpu_data)

    def _start_updates(self):
        """Start periodic updates"""
        self._update_performance()
        self._update_window_pids()

    def _update_performance(self):
        """Update performance view"""
        if not self.running:
            return

        # Always collect performance data so graphs have history from startup
        self.performance_view.update()

        self.root.after(1000, self._update_performance)

    def _update_window_pids(self):
        """Update window PIDs for process classification"""
        if not self.running:
            return

        # Run in background, less frequently (10 seconds)
        self.processes_view.update_window_pids()
        self.root.after(10000, self._update_window_pids)

    def _on_close(self):
        """Handle window close"""
        self.running = False

        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except:
                self.proc.kill()

        self.root.destroy()


def main():
    """Application entry point"""
    root = tk.Tk()
    app = TaskManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
