"""
FoodWaste360 - Streamlit Community Cloud entry point.

Streamlit Community Cloud defaults the "Main file path" to streamlit_app.py.
This thin wrapper simply runs the real application in app.py so both names
work as deployment entry points.
"""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
