#!/usr/bin/env python3
"""
Task Manager Launcher
Convenience script to run the application from the project root
"""

import os
import sys

# Change to project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from ui import TaskManagerApp
import tkinter as tk


if __name__ == "__main__":
    root = tk.Tk()
    app = TaskManagerApp(root)
    root.mainloop()
