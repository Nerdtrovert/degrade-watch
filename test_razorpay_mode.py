#!/usr/bin/env python3
"""
Test script to verify Recovery Engine mode selection.
"""

import os
import sys
from pathlib import Path

# Load environment variables from backend/.env if it exists (same as run_end_to_end.py)
backend_env_path = Path(__file__).parent.parent / "backend" / ".env"
if backend_env_path.exists():
    with open(backend_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / "backend"))

from backend.app.recovery_engine import RecoveryEngine
from app.database import SessionLocal

def test_recovery_engine_mode():
    """Test that Recovery Engine detects Razorpay credentials and initializes client."""
    print("Testing Recovery Engine initialization...")

    # Create a database session for the recovery engine
    db = SessionLocal()
    try:
        # Create recovery engine instance
        recovery_engine = RecoveryEngine(db_session=db)
    finally:
        db.close()

    # Check if Razorpay client was initialized
    if recovery_engine.razorpay_client is not None:
        print("RAZORPAY MODE: TEST MODE (client initialized)")
        return "TEST_MODE"
    else:
        print("RAZORPAY MODE: SIMULATION MODE (client not initialized)")
        return "SIMULATION_MODE"

if __name__ == "__main__":
    mode = test_recovery_engine_mode()
    print(f"Result: {mode}")