#!/usr/bin/env python3
"""Copy the qualified suite verbatim into the versioned distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--freeze', type=Path, required=True)
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
excluded = {'BENCHMARK.md', 'runner_v05.py', 'screen_v05.py', 'runtime/README.md'}
manifest = {}
for source in sorted(args.freeze.rglob('*')):
    if not source.is_file() or '__pycache__' in source.parts:
        continue
    relative = source.relative_to(args.freeze).as_posix()
    if relative in excluded:
        continue
    destination = args.destination / relative
    if destination.exists():
        assert destination.read_bytes() == source.read_bytes(), relative
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    manifest[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
(args.destination / 'SOURCE_MANIFEST.json').write_text(json.dumps(dict(
    version='1.0.0', source='qualified 0.5 evaluator R1, 2026-09-27',
    compatibility='Original packet and evaluator bytes retained, including internal 0.5 paths.',
    sha256=manifest), indent=2) + '\n')
print(f'Packaged {len(manifest)} byte-identical source files')
