"""Generate the conservative optimizer-fixture map from the pinned checkout.

Usage: python tools/build_fixture_map.py /path/to/sqlglot /path/to/tests.json
"""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SHA = 'eb11aec4be8cb2122afe713a4816662c3f0fb2fa'
root = Path(sys.argv[1]).resolve()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == SHA
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip()
tests = json.loads(Path(sys.argv[2]).read_text())['tests']
catalog = hashlib.sha256('\n'.join(sorted(t['id'] for t in tests)).encode()).hexdigest()
files = {p.relative_to(root).as_posix(): p.read_text(encoding='utf-8')
         for p in sorted((root / 'tests/fixtures/optimizer').glob('*.sql'))}
assert files
payload = json.dumps({'schema': 1, 'sha': SHA, 'catalog': catalog, 'files': files},
                     sort_keys=True, separators=(',', ':')).encode()
Path('fixture-map.json.gz').write_bytes(gzip.compress(payload, mtime=0))
