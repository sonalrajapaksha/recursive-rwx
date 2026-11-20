"""Select audited optimizer fixtures; otherwise run the full test catalog."""

import gzip
import hashlib
import json
import math
import re
import zlib
from pathlib import Path

DATA = Path("/data")
MAP = Path(__file__).with_name("fixture-map.json.gz")
SHA = "eb11aec4be8cb2122afe713a4816662c3f0fb2fa"
MAP_DIGEST = "b29ed0b07ec1cfa8084294eef1d9fb2ccb5e8e6a82483d12519063e9c16a1b98"
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$")


def bounded_fixture_patch(text: str, files: dict[str, str]) -> bool:
    """Accept only ordinary edits whose old hunk content matches mapped files."""
    # ponytail: only mapped fixture edits are narrowed; extend after dependency audits.
    try:
        lines = text.splitlines(keepends=True)
        i = count = 0
        while i < len(lines):
            header = re.fullmatch(r"diff --git a/([^\s]+) b/([^\s]+)\n", lines[i])
            i += 1
            if not header or header[1] != header[2] or header[1] not in files:
                return False
            path = header[1]
            original = files[path].splitlines(keepends=True)
            if not re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+ 100644\n", lines[i]):
                return False
            i += 1
            if lines[i:i + 2] != [f"--- a/{path}\n", f"+++ b/{path}\n"]:
                return False
            i += 2
            prior = hunks = delta = 0
            while i < len(lines) and lines[i].startswith("@@ "):
                h = HUNK.fullmatch(lines[i].rstrip("\n"))
                i += 1
                if not h:
                    return False
                old, old_count = int(h[1]), int(h[2] or 1)
                new, new_count = int(h[3]), int(h[4] or 1)
                pos = old - 1 if old_count else old
                new_pos = new - 1 if new_count else new
                if pos < prior or pos > len(original) or new_pos != pos + delta:
                    return False
                used = added = 0
                while i < len(lines) and lines[i][:1] in (" ", "+", "-"):
                    row = lines[i]
                    i += 1
                    if not row.endswith("\n"):
                        return False
                    if row[0] in " -":
                        if pos >= len(original) or original[pos] != row[1:]:
                            return False
                        pos += 1
                        used += 1
                    if row[0] in " +":
                        added += 1
                if used != old_count or added != new_count:
                    return False
                prior = pos
                delta += new_count - old_count
                hunks += 1
            if not hunks:
                return False
            count += 1
        return count > 0
    except (IndexError, ValueError):
        return False


def split(tests: list[dict]) -> list[list[int]]:
    """Choose the cheapest longest-first schedule in integer milliseconds."""
    ordered = sorted(tests, key=lambda t: (-math.floor(t["seconds"] * 1000 + 0.5), t["number"]))
    best, best_cost = [], float("inf")
    for count in range(1, min(8, len(ordered)) + 1):
        workers = [[] for _ in range(count)]
        loads = [0] * count
        for test in ordered:
            index = loads.index(min(loads))
            workers[index].append(test["number"])
            loads[index] += math.floor(test["seconds"] * 1000 + 0.5)
        cost = max(loads) + 2000 * count
        if cost < best_cost:
            best, best_cost = workers, cost
    return best


def main() -> None:
    tests = json.loads((DATA / "tests.json").read_text())["tests"]
    workers = split(tests)
    try:
        artifact = MAP.read_bytes()
        if hashlib.sha256(artifact).hexdigest() != MAP_DIGEST:
            raise ValueError("map checksum mismatch")
        mapping = json.loads(gzip.decompress(artifact))
        catalog = hashlib.sha256("\n".join(sorted(t["id"] for t in tests)).encode()).hexdigest()
        if (mapping["schema"] != 1 or mapping["sha"] != SHA or mapping["catalog"] != catalog or
                any(t["file"] != t["id"].split("::", 1)[0] for t in tests)):
            raise ValueError("map does not match catalog")
        fixture_workers = split([t for t in tests if t["file"] in
                                 ("tests/test_optimizer.py", "tests/test_executor.py")])
        if not fixture_workers:
            raise ValueError("fixture consumers missing")
    except (OSError, EOFError, ValueError, KeyError, TypeError, zlib.error):
        mapping = None
    for patch in sorted((DATA / "commits").glob("*.patch")):
        try:
            bounded = mapping is not None and bounded_fixture_patch(
                patch.read_text(encoding="utf-8"), mapping["files"])
        except (OSError, UnicodeError, KeyError, TypeError):
            bounded = False
        print(json.dumps({"commit": patch.stem, "workers": fixture_workers if bounded else workers},
                         separators=(",", ":")))


if __name__ == "__main__":
    main()
