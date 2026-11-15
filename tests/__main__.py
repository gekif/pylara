"""Run the whole suite:  python -m tests"""
import subprocess
import sys

codes = [
    subprocess.call([sys.executable, "-m", "tests.test_framework"]),
    subprocess.call([sys.executable, "-m", "unittest", "tests.test_features", "tests.test_security", "tests.test_docs", "-v"]),
]
sys.exit(1 if any(codes) else 0)
