import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import app
    print('app import ok')
except Exception as exc:
    import traceback
    traceback.print_exc()
    raise
