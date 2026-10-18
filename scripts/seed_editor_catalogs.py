#!/usr/bin/env python3
"""Seed Sound/Deck candidate catalogs with attributed exact matches and authored text.

No English placeholder copies are inserted into other languages. This is a
recoverable development step, not evidence of complete localization. Run
`audit_localization.py --require-complete` before considering a release.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import reuse_six_language_catalogs as reuse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'patches/localization-shared'


def authored_rows(path):
    result = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        columns = line.split('\t')
        if len(columns) != 6:
            raise ValueError(f'{path.name}:{number}: expected six columns')
        key, *values = map(reuse.unescape_tsv, columns)
        if key in result:
            raise ValueError(f'Duplicate authored key: {key}')
        if any(not value.strip() or reuse.placeholders(value) != reuse.placeholders(key) for value in values):
            raise ValueError(f'Empty or placeholder mismatch: {key}')
        result[key] = dict(zip(('vi', 'ko', 'ja', 'zh-TW', 'zh-CN'), values))
    return result


def seed(root, app):
    exceptions = json.loads((DATA / 'official-exceptions.json').read_text(encoding='utf-8'))['entries']
    allowed = {(e.get('context', ''), e['source']) for e in exceptions}
    donors = defaultdict(set)
    for name in (*reuse.APPS, 'launcher'):
        source = root / ('.work/launcher/source' if name == 'launcher' else '.work/full-native/' + name + '/source')
        scoped_path = DATA / (name + '-interface.tsv')
        scoped_keys = set(authored_rows(scoped_path)) if name != app and scoped_path.is_file() else set()
        for row in reuse.read_app(name, source)['rows']:
            # A presentation "Bounce" is an animation; an audio "Bounce" exports
            # a mix. App-specific editorial decisions are not generic donors.
            if row['source'] in scoped_keys:
                continue
            if row['language'] == 'en' or row['context'] or row['kind'] != 'plain' or reuse.invalid_reason(row, allowed):
                continue
            donors[row['source'], row['language']].add(row['translation'])
    pool = {key: next(iter(values)) for key, values in donors.items() if len(values) == 1}
    # Explicitly authored terminology is an editorial decision, never a majority vote.
    for row in reuse.read_supplement(DATA / 'common-software-terms.json'):
        pool[row['source'], row['language']] = row['translation']
    for key, values in authored_rows(DATA / 'editor-interface.tsv').items():
        for code, value in values.items():
            pool[key, code] = value
    scoped = DATA / (app + '-interface.tsv')
    scoped_rows = {}
    if scoped.is_file():
        scoped_rows = authored_rows(scoped)
        for key, values in scoped_rows.items():
            for code, value in values.items():
                pool[key, code] = value
    keys = json.loads((DATA / (app + '-source-keys.json')).read_text(encoding='utf-8'))['keys']
    folder = root / '.work/full-native' / app / 'source/crates/ui-egui/src/i18n'
    folder.mkdir(exist_ok=True)
    report = {'app': app, 'status': 'development-incomplete-not-released', 'keys': len(keys), 'languages': {}}
    def escape(value):
        return value.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')
    for code in reuse.LANGUAGES:
        path = folder / (code + '.tsv')
        # Never discard translations that a reviewer has already completed in place.
        existing = {}
        if path.is_file():
            for line in path.read_text(encoding='utf-8').splitlines():
                if line and not line.startswith('#'):
                    context, key, value = map(reuse.unescape_tsv, line.split('\t'))
                    existing[key] = value
        lines = ['# KIO source-keyed candidate catalog. Missing entries are NOT counted as translated.']
        missing = []
        for key in keys:
            # Scoped editorial rows were reviewed for this application. They may
            # correct a generic donor in these newly introduced candidate catalogs.
            value = key if code == 'en' or ('', key) in allowed else scoped_rows.get(key, {}).get(code) or existing.get(key) or pool.get((key, code))
            if value:
                lines.append('\t'.join(map(escape, ('@msg' if '{' in key else '', key, value))))
            else:
                missing.append(key)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        report['languages'][code] = {'keys': len(lines) - 1, 'missing': len(missing), 'missingKeys': missing}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--app', choices=('sound', 'deck'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = seed(args.root, args.app)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**report, 'languages': {k: {n: v for n, v in row.items() if n != 'missingKeys'} for k, row in report['languages'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
