#!/usr/bin/env python3
"""Apply reviewed, additive TSV reuse to already registered languages only.

The planner is deliberately read-only. This separate step revalidates all source
hashes, keeps existing translations verbatim, writes a recoverable before/after
receipt, and refuses an incomplete or modified plan. New runtime languages and
non-TSV formats require a separate implementation review.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import reuse_six_language_catalogs as reuse


def sha(data):
    return hashlib.sha256(data).hexdigest()


def escape(value):
    return value.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


def source_for(root, app):
    if app == 'launcher':
        return root / '.work/launcher/source'
    if app not in reuse.APPS:
        raise ValueError('Unknown application: ' + app)
    return root / '.work/full-native' / app / 'source'


def prepare_changes(root, plan, exceptions, supplement):
    """Recompute the whole plan from pinned live inputs before any source write."""
    apps = []
    for entry in plan['inputs']:
        source = source_for(root, entry['app'])
        app = reuse.read_app(entry['app'], source)
        expected = {row['file']: row['sha256'] for row in entry['files']}
        if app['files'] != expected or app['issues']:
            raise ValueError('Catalog inputs changed or have parse errors: ' + entry['app'])
        apps.append(app)
    current = reuse.build_plan(apps, exceptions, supplement)
    if current != plan:
        raise ValueError('Plan does not match recomputed proposals; review it again')
    by_app = {app['app']: app for app in apps}
    additions, skipped = defaultdict(list), Counter()
    for row in plan['proposals']:
        if row['action'] != 'add':
            skipped['existingTranslationRetained'] += 1
            continue
        # Do not transfer ID lookups, plural categories or unrelated generic
        # words by guessing their meaning. The planner matches context exactly.
        if row['kind'] != 'plain' or row['context'].startswith('@'):
            skipped['requiresSemanticReview'] += 1
            continue
        app = by_app[row['app']]
        candidates = {
            r['provenance']['file'] for r in app['rows']
            if r['language'] == row['language'] and r['provenance']['file'].endswith('.tsv')
        }
        if len(candidates) != 1:
            skipped['runtimeLanguageOrFormatReviewRequired'] += 1
            continue
        relative = next(iter(candidates))
        additions[(row['app'], relative)].append(row)
    changes = []
    for (app, relative), rows in sorted(additions.items()):
        path = source_for(root, app) / relative
        before = path.read_bytes()
        text = before.decode('utf-8')
        suffix = '\n# KIO additive translations: exact source/context, unanimous catalog donors.\n'
        suffix += ''.join('\t'.join(map(escape, (r['context'], r['source'], r['translation']))) + '\n' for r in rows)
        after = (text.rstrip('\n') + '\n' + suffix).encode('utf-8')
        changes.append({'app': app, 'path': relative, 'before': before,
                        'after': after, 'entries': rows})
    return changes, dict(skipped)


def apply(root, plan, exceptions, supplement, receipt):
    if receipt.exists():
        raise ValueError('Receipt directory already exists; originals will not be overwritten')
    changes, skipped = prepare_changes(root, plan, exceptions, supplement)
    receipt.mkdir(parents=True)
    # Save every original and proposed output before mutating any source file.
    records = []
    for change in changes:
        for side in ('before', 'after'):
            backup = receipt / side / change['app'] / change['path']
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(change[side])
        records.append({'app': change['app'], 'path': change['path'],
                        'beforeSha256': sha(change['before']), 'afterSha256': sha(change['after']),
                        'entries': len(change['entries'])})
    result = {'schemaVersion': 1, 'status': 'prepared', 'appliedEntries': sum(r['entries'] for r in records),
              'files': records, 'skipped': skipped,
              'limitations': 'Additive source changes only; native builds, linguistic and screen review remain required.'}
    manifest = receipt / 'receipt.json'
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for change in changes:
        path = source_for(root, change['app']) / change['path']
        if path.read_bytes() != change['before']:
            raise ValueError('Concurrent catalog edit; recover from receipt before retrying')
        temp = path.with_name(path.name + '.kio-reuse-tmp')
        with temp.open('xb') as output:
            output.write(change['after'])
        temp.replace(path)
    result['status'] = 'applied'
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    folder = args.root / 'patches/localization-shared'
    exceptions = json.loads((folder / 'official-exceptions.json').read_text(encoding='utf-8'))['entries']
    supplement = reuse.read_supplement(folder / 'common-software-terms.json')
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    result = apply(args.root, plan, exceptions, supplement, args.receipt)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
