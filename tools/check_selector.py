"""Small parser and scheduler regression check: python tools/check_selector.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selector import bounded_fixture_patch, split

p = 'tests/fixtures/optimizer/example.sql'
files = {p: 'first\nsecond\n'}
prefix = f'diff --git a/{p} b/{p}\nindex 123..456 100644\n--- a/{p}\n+++ b/{p}\n'
assert bounded_fixture_patch(prefix + '@@ -1,2 +1,2 @@\n first\n-second\n+changed\n', files)
assert bounded_fixture_patch(prefix + '@@ -1,0 +2 @@\n+inserted\n', files)
assert bounded_fixture_patch(prefix + '@@ -2 +1,0 @@\n-second\n', files)
assert not bounded_fixture_patch(prefix + '@@ -1 +1 @@\n-wrong\n+changed\n', files)
assert not bounded_fixture_patch(prefix + '@@ -1 +2 @@\n-first\n+changed\n', files)
assert not bounded_fixture_patch(prefix + 'Binary files differ\n', files)
assert not bounded_fixture_patch(prefix.replace(' 100644', ' 100755') + '@@ -1 +1 @@\n-first\n+changed\n', files)
assert not bounded_fixture_patch(prefix + '@@ -1 +1 @@\n-first\n+changed\n\\ No newline at end of file\n', files)
assert not bounded_fixture_patch(prefix.replace('b/' + p, 'b/renamed') + '@@ -1 +1 @@\n-first\n+changed\n', files)
assert not bounded_fixture_patch(prefix + '@@ -1 +1 @@\n-first\n+changed\n' + 'unsupported\n', files)
assert not bounded_fixture_patch(prefix + '@@ -1 +1 @@\n-first\n+changed\n' +
                                 'diff --git a/sqlglot/parser.py b/sqlglot/parser.py\n', files)
assert split([]) == []
assert split([{'number': 0, 'seconds': 0}]) == [[0]]
assert split([{'number': i, 'seconds': 10} for i in range(8)]) == [[i] for i in range(8)]
print('selector checks passed')
