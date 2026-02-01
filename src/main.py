#!/usr/bin/env python3
"""
Task Manager - Main Entry Point
Run this file to start the application
"""

import sys
import os

# Enable font anti-aliasing for Tkinter on Linux
# These must be set BEFORE importing tkinter
os.environ.setdefault('GDK_BACKEND', 'x11')

# Improve font rendering on Linux
os.environ.setdefault('FREETYPE_PROPERTIES', 'truetype:interpreter-version=40')

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import TaskManagerApp
import tkinter as tk


def configure_fonts(root):
    """Configure font rendering for better anti-aliasing"""
    try:
        # Set DPI scaling
        root.tk.call('tk', 'scaling', 1.0)

        # Try to enable font smoothing via Tk options
        root.option_add('*Font', 'TkDefaultFont')

        # Configure default fonts with anti-aliasing hints
        import tkinter.font as tkfont

        # Set default font to a well-rendered one
        default_font = tkfont.nametofont('TkDefaultFont')
        default_font.configure(family='DejaVu Sans', size=11)

        text_font = tkfont.nametofont('TkTextFont')
        text_font.configure(family='DejaVu Sans', size=11)

        fixed_font = tkfont.nametofont('TkFixedFont')
        fixed_font.configure(family='DejaVu Sans Mono', size=10)

    except Exception:
        pass


def main():
    """Start the Task Manager application"""
    root = tk.Tk()

    # Configure fonts before creating widgets
    configure_fonts(root)

    # Create and run application
    app = TaskManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
