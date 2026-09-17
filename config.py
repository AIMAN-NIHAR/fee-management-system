import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'change-this-to-something-random'
    DATABASE = os.path.join(BASE_DIR, 'fee_management.db')