import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[0]
BACKEND = ROOT / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
import analytics.flows.tooling as tooling
print('Mapping defined:', 'Mapping' in tooling.__dict__)
print('Mapping value:', tooling.__dict__.get('Mapping'))
