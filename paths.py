import os
import sys

# Get absolute path to the directory containing this script (Root of project on external drive)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(*relative_parts) -> str:
    """Returns absolute path relative to the portable application root directory."""
    return os.path.abspath(os.path.join(BASE_DIR, *relative_parts))

def ensure_dir_exists(dir_path: str) -> str:
    """Ensures directory exists and returns absolute path."""
    os.makedirs(dir_path, exist_ok=True)
    return dir_path
