import sys
import os

# Add the parent directory (root of the project) to sys.path
# This allows importing 'main' from the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from mangum import Mangum
from main import app

handler = Mangum(app)
