import os
import sys

def get_persistent_dir():
    """
    Returns the folder where the .exe itself lives (so the database
    sits right next to it and survives between runs), or the normal
    project folder when running as a regular Python script.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

BASE_DIR = get_persistent_dir()

class Config:
    SECRET_KEY = 'change-this-to-something-random'
    DATABASE = os.path.join(BASE_DIR, 'fee_management.db')