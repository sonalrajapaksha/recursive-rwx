"""Record exploratory baseline dependencies; incomplete traces are never trusted.

Run in the pinned Linux image with coverage==7.13.4 installed, from a clean
sqlglot checkout: SKIP_INTEGRATION=0 PYTHONPATH=$PWD python /path/to/trace_dependencies.py OUTPUT [pytest paths...]
The default path is tests. The result includes collection, fixture closures,
line execution, file access, and subprocess uncertainty; it is not a selector map.
"""
import gzip
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

import coverage
from coverage.numbits import numbits_to_nums
import pytest

SHA = 'eb11aec4be8cb2122afe713a4816662c3f0fb2fa'
ROOT = Path.cwd().resolve()


def main():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    output = Path(sys.argv[1]).resolve()
    paths = sys.argv[2:] or ['tests']
    current = ['collection']
    reads = {}
    children = set()
    fixture_edges = {}

    def audit(event, args):
        if event in ('subprocess.Popen', 'os.fork', 'os.posix_spawn'):
            children.add(current[0])
        if event not in ('open', 'os.listdir', 'os.scandir') or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        try:
            name = Path(os.fsdecode(args[0])).resolve().relative_to(ROOT).as_posix()
        except (ValueError, OSError):
            return
        reads.setdefault(current[0], set()).add((event, name))

    class Plugin:
        def pytest_collection_finish(self, session):
            self.collected = sorted(item.nodeid for item in session.items)

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_protocol(self, item, nextitem):
            current[0] = item.nodeid
            cov.switch_context(item.nodeid)
            yield
            edges = []
            for name in item.fixturenames:
                for definition in item._fixtureinfo.name2fixturedefs.get(name, ()):
                    func = definition.func
                    path = getattr(getattr(func, '__code__', None), 'co_filename', '')
                    try:
                        path = Path(path).resolve().relative_to(ROOT).as_posix()
                    except ValueError:
                        continue
                    edges.append((name, definition.scope, path, getattr(func, '__qualname__', '')))
            fixture_edges[item.nodeid] = sorted(edges)
            current[0] = 'outside'
            cov.switch_context('outside')

    with tempfile.TemporaryDirectory() as temp:
        database = str(Path(temp) / 'coverage.sqlite')
        cov = coverage.Coverage(data_file=database, source=[str(ROOT)], config_file=False)
        plugin = Plugin()
        sys.addaudithook(audit)
        cov.start()
        result = int(pytest.main(['-q', '-p', 'no:cacheprovider', *paths], plugins=[plugin]))
        cov.stop()
        cov.save()
        connection = sqlite3.connect(database)
        lines = []
        query = '''SELECT context.context, file.path, line_bits.numbits FROM line_bits
                   JOIN context ON context.id=line_bits.context_id JOIN file ON file.id=line_bits.file_id'''
        for context, filename, bits in connection.execute(query):
            try:
                name = Path(filename).resolve().relative_to(ROOT).as_posix()
            except ValueError:
                continue
            lines.append((context or 'collection', name, numbits_to_nums(bits)))
        payload = {'schema': 1, 'sha': SHA, 'exitstatus': result,
                   'python': sys.version, 'platform': sys.platform, 'paths': paths,
                   'collected': getattr(plugin, 'collected', []), 'fixture_edges': fixture_edges,
                   'lines': sorted(lines), 'reads': {k: sorted(v) for k, v in sorted(reads.items())},
                   'subprocess_contexts': sorted(children),
                   'uncertainty': ['subprocess execution is not traced', 'dynamic and reused fixtures require attribution audit',
                                   'audit hooks do not capture every native file access']}
        output.write_bytes(gzip.compress(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode(), mtime=0))
    return result


if __name__ == '__main__':
    raise SystemExit(main())
