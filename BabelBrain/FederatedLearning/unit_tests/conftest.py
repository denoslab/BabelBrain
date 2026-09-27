import os
import sys

# BabelBrain modules import each other from BabelBrain/BabelBrain, as when the app runs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
