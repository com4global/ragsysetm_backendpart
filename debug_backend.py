#!/usr/bin/env python
"""
Debug script to run FastAPI backend with debugpy
This allows you to set breakpoints and debug the backend
"""

import debugpy
import uvicorn
import sys
from pathlib import Path

# Ensure we're in the right directory
import os
os.chdir(Path(__file__).parent)

# Start the debugpy listener on port 5678
# Connect from VS Code when prompted
print("\n" + "="*70)
print("🔴 DEBUGPY LISTENER STARTED ON PORT 5678")
print("="*70)
print("\nTo debug from VS Code:")
print("1. Click Run → Select 'Debug FastAPI Backend' from dropdown")
print("2. Or press Ctrl+F5 to start debugging")
print("\nIf using attach mode:")
print("   - Run this script first")
print("   - Then attach debugger from VS Code")
print("   - Use 'Python: Attach using Process ID' configuration")
print("\n" + "="*70 + "\n")

debugpy.listen(("localhost", 5678))
print("⏳ Waiting for debugger to attach...")
print("   (You can also continue without attaching - debugger will pause at breakpoints)")
# Uncomment next line to wait for debugger before starting
# debugpy.wait_for_client()

# Start FastAPI with Uvicorn
print("\n🚀 Starting FastAPI backend on http://localhost:8000")
print("📚 Swagger UI available at http://localhost:8000/docs\n")

uvicorn.run(
    "main:app",
    host="127.0.0.1",
    port=8000,
    reload=True,
    reload_dirs=["."],
    log_level="info"
)
