# -*- coding: utf-8 -*-
"""
Created on Fri Sep 12 13:40:34 2025

@author: Tejaswini

entry point for the Calibration App
This file launched the Streamlit UI defined in ui.py
"""

import os
import sys
import subprocess
from pathlib import Path

def run_ui():
    try:
        ui_path = Path(__file__).resolve().parent / "ui_mod.py"
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(ui_path)], check=True)
    except Exception as e:
        print("Error launching UI:", e)

if __name__ == "__main__":
    print("🚀 Starting Calibration App...")
    run_ui()