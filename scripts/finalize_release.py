#!/usr/bin/env python3
"""Verify application downloads and refresh content-addressed public assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    args = parser.parse_args()
    site = Path(__file__).resolve().parents[1] / 'site'
    data = json.loads((site / 'results.json').read_text())
    checksums = {}
    for run in data['runs']:
        item = run['source_archive']
        digest = sha(args.assets / item['file'])
        assert digest == item['sha256'], item['file']
        checksums[item['file']] = digest
    for name in ('results.json', 'EVALUATION_R4.json'):
        shutil.copyfile(site / name, args.assets / name)
        checksums[name] = sha(site / name)
    text = json.dumps(checksums, indent=2) + '\n'
    (site / 'RELEASE_SHA256.json').write_text(text)
    (args.assets / 'RELEASE_SHA256.json').write_text(text)
    html = (site / 'index.html').read_text()
    for name in ('data.js', 'report.js', 'style.css'):
        html, count = re.subn(re.escape(name) + r'\?v=[a-f0-9]{12}',
                             name + '?v=' + sha(site / name)[:12], html)
        assert count == 1, name
    (site / 'index.html').write_text(html)
    print(f'Verified {len(data["runs"])} source archives; refreshed checksums and cache-busting URLs.')


if __name__ == '__main__':
    main()
