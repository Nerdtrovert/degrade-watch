#!/usr/bin/env python3
"""
Test script to verify environment loading works like in run_end_to_end.py.
"""

import os
import sys
from pathlib import Path

# Load environment variables from backend/.env if it exists (same as run_end_to_end.py)
backend_env_path = Path(__file__).parent / "backend" / ".env"
if backend_env_path.exists():
    with open(backend_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
else:
    print("WARNING: backend/.env file not found!")
    print(f"Looking for: {backend_env_path.absolute()}")

# Check if env vars are loaded
print("Environment variables after loading .env:")
print(f"RAZORPAY_KEY_ID: {'SET' if os.environ.get('RAZORPAY_KEY_ID') else 'NOT SET'}")
print(f"RAZORPAY_KEY_SECRET: {'SET' if os.environ.get('RAZORPAY_KEY_SECRET') else 'NOT SET'}")

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

# Import and test razorpay availability
try:
    import razorpay
    print(f"Razorpay package available: True")
    print(f"Razorpay version: {getattr(razorpay, '__version__', 'unknown')}")
except ImportError as e:
    print(f"Razorpay package available: False - {e}")

# Now test Recovery Engine
from backend.app.recovery_engine import RecoveryEngine

print("\nCreating Recovery Engine...")
recovery_engine = RecoveryEngine()

print(f"Razorpay client after init: {recovery_engine.razorpay_client}")
if recovery_engine.razorpay_client is not None:
    print("SUCCESS: Razorpay client initialized - will use TEST MODE")
else:
    print("INFO: Razorpay client not initialized - will use SIMULATION MODE")
    # Check why
    key_id = os.environ.get('RAZORPAY_KEY_ID')
    key_secret = os.environ.get('RAZORPAY_KEY_SECRET')
    print(f"  Key ID from env: {'SET' if key_id else 'NOT SET'}")
    print(f"  Key Secret from env: {'SET' if key_secret else 'NOT SET'}")