#!/usr/bin/env python3
"""Plan conservative reuse of existing suite translations, without changing sources.

Python 3.11+, standard library only; no network or machine translation. Output is a
reviewable proposal, not a claim of linguistic review or complete GUI coverage.
English text, context, plural structure and placeholder shape must match exactly.
Conflicting translations are never settled by majority vote or catalog order.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

LANGUAGES = ('vi', 'en', 'ko', 'ja', 'zh-TW', 'zh-CN')
APPS = ('photo', 'vector', 'film', 'light', 'pdf', 'effect', 'design', 'ui', 'word', 'cad', 'grid')
ALIASES = {'zh': 'zh-CN', 'zh-hans': 'zh-CN', 'zh-cn': 'zh-CN', 'zh-hant': 'zh-TW', 'zh-tw': 'zh-TW'}
RSTRING = r'"(?:[^"\\]|\\.)*"'
PAIR = re.compile(r'\(\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,?\s*\)')
TRIPLE = re.compile(r'\(\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,?\s*\)')
TABLE = re.compile(r'(?:const|static)\s+(\w+)[^=]+?=\s*&\[(.*?)\n\];', re.S)
LOOKUP = re.compile(r'(?:\btl!\s*\(|\b(?:i18n::)?(?:t|tr|tr_noop|trf|trn|tr_args)\s*\()\s*(' + RSTRING + ')')
RUST_PLACEHOLDER = re.compile(r'\{((?:[A-Za-z_]\w*|\d*)(?::[^{}]*)?)\}')
PRINTF_PLACEHOLDER = re.compile(r'%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hlLjzt])?[diuoxXfFeEgGaAcspn](?![A-Za-z])')
QT_PLACEHOLDER = re.compile(r'%(?:L?\d+|n)\b')
RUST_LANGUAGES = {'JAPANESE': 'ja', 'SIMPLIFIED_CHINESE': 'zh-CN', 'TRADITIONAL_CHINESE': 'zh-TW', 'KOREAN': 'ko', 'VIETNAMESE': 'vi'}


def language(code):
    value = code.lower().replace('_', '-')
    return ALIASES.get(value, value)


def decode(raw):
    """Decode an ordinary Rust string strictly; unsupported escapes abort the plan."""
    text, out, index = raw[1:-1], [], 0
    escapes = {'n': '\n', 'r': '\r', 't': '\t', '0': '\x00', '\\': '\\', '"': '"', "'": "'"}
    while index < len(text):
        char = text[index]
        index += 1
        if char != '\\':
            out.append(char)
            continue
        if index >= len(text):
            raise ValueError('Incomplete Rust escape')
        char = text[index]
        index += 1
        if char in escapes:
            out.append(escapes[char])
        elif char == 'u':
            match = re.match(r'\{([0-9a-fA-F_]+)\}', text[index:])
            if not match:
                raise ValueError('Invalid Rust Unicode escape')
            out.append(chr(int(match[1].replace('_', ''), 16)))
            index += match.end()
        elif char == 'x':
            value = text[index:index + 2]
            if not re.fullmatch('[0-9a-fA-F]{2}', value) or int(value, 16) > 127:
                raise ValueError('Invalid Rust ASCII escape')
            out.append(chr(int(value, 16)))
            index += 2
        elif char in '\r\n':
            while index < len(text) and text[index].isspace():
                index += 1
        else:
            raise ValueError('Unsupported Rust escape: ' + char)
    return ''.join(out)


def unescape_tsv(text):
    return re.sub(r'\\([nt\\])', lambda m: {'n': '\n', 't': '\t', '\\': '\\'}[m[1]], text)


def placeholders(text):
    """Count the exact format tokens; escaped literal braces/percent signs are ignored."""
    result, index = Counter(), 0
    while index < len(text):
        if text[index:index + 2] in ('{{', '}}', '%%'):
            index += 2
            continue
        match = RUST_PLACEHOLDER.match(text, index)
        if match:
            result['rust:' + match[1]] += 1
        else:
            match = PRINTF_PLACEHOLDER.match(text, index)
            if match:
                result['printf:' + match[0]] += 1
            else:
                match = QT_PLACEHOLDER.match(text, index)
                if match:
                    result['qt:' + match[0]] += 1
        index = match.end() if match else index + 1
    return result


def signature(text):
    return [[key, count] for key, count in sorted(placeholders(text).items())]


def identity(row):
    # Keep named contexts and plural lookup kinds independent, even when text matches.
    return row['context'], row['source'], row.get('kind', 'plain')


def expected_source(row):
    return row['source'].split('|')[0] if row['context'] == '@plural' else row['source']


def invalid_reason(row, exceptions):
    if row['context'] in ('@id', '@commands', '@menu'):
        return 'identifierWithoutEnglishMeaning'
    forms = row.get('forms', [row['translation']])
    if not forms or any(not value.strip() for value in forms):
        return 'empty'
    expected = placeholders(expected_source(row))
    if row['context'] == '@plural' and any(placeholders(form) != expected for form in row['source'].split('|')):
        return 'pluralSourcePlaceholderMismatch'
    if any(placeholders(value) != expected for value in forms):
        return 'placeholderMismatch'
    if any(value == expected_source(row) or value == row['source'] for value in forms):
        if (row['context'], row['source']) not in exceptions:
            return 'unchangedEnglishWithoutException'
    return None


def read_app(app, source):
    """Read real formats, retaining every row's file, line, table and SHA-256."""
    source = Path(source)
    root = source / 'crates/ui-egui'
    rows, files, issues, keys = [], {}, [], set()

    def body(path):
        relative = str(path.relative_to(source))
        raw = path.read_bytes()
        files[relative] = hashlib.sha256(raw).hexdigest()
        return raw.decode('utf-8')

    def put(code, context, english, value, path, line=None, table=None, kind='plain', forms=None):
        keys.add((context, english, kind))
        if language(code) not in LANGUAGES:
            return
        provenance = {'app': app, 'file': str(path.relative_to(source)), 'sha256': files[str(path.relative_to(source))]}
        if line is not None:
            provenance['line'] = line
        if table:
            provenance['table'] = table
        rows.append({'app': app, 'language': language(code), 'context': context, 'source': english,
                     'translation': value, 'kind': kind, 'forms': forms or [value], 'provenance': provenance})

    for path in sorted((root / 'src/i18n').glob('*.tsv')):
        seen = set()
        for line, text in enumerate(body(path).splitlines(), 1):
            if not text or text.startswith('#'):
                continue
            columns = text.split('\t')
            if len(columns) != 3:
                issues.append({'file': str(path.relative_to(source)), 'line': line, 'reason': 'invalidColumns'})
                continue
            context, english, value = map(unescape_tsv, columns)
            key = context, english
            if key in seen:
                issues.append({'file': str(path.relative_to(source)), 'line': line, 'reason': 'duplicate', 'key': list(key)})
            seen.add(key)
            put(path.stem, context, english, value, path, line, kind='plural' if context == '@plural' else 'plain', forms=value.split('|') if context == '@plural' else None)

    for path in sorted((root / 'locales').glob('*.json')):
        if path.stem.endswith('-formats'):
            continue
        for english, value in json.loads(body(path)).items():
            if isinstance(value, str):
                put(path.stem, '', english, value, path)

    for path in sorted((root / 'locales').glob('*.toml')):
        catalog = tomllib.loads(body(path))
        for section in ('ui', 'commands', 'menu'):
            for english, value in catalog.get(section, {}).items():
                context = '' if section == 'ui' else '@' + section
                if isinstance(value, str):
                    put(path.stem, context, english, value, path, table=section)
                elif isinstance(value, dict) and all(isinstance(v, str) for v in value.values()):
                    put(path.stem, context, english, value.get('other', ''), path, table=section, kind='plural', forms=[value[k] for k in sorted(value)])

    main = root / 'src/i18n.rs'
    if main.is_file() and app in ('design', 'effect', 'grid'):
        text = body(main).split('#[cfg(test)]')[0]
        if app == 'design':
            # The dedicated Japanese TABLE wins over the shared column at runtime.
            ja_path = root / 'src/i18n/ja.rs'
            overrides = set()
            if ja_path.is_file():
                ja_text = body(ja_path).split('#[cfg(test)]')[0]
                for match in PAIR.finditer(ja_text):
                    english, value = map(decode, match.groups())
                    overrides.add(english)
                    put('ja', '', english, value, ja_path, ja_text.count('\n', 0, match.start()) + 1, 'TABLE')
            for match in re.finditer(r'\(\s*(' + RSTRING + r')\s*,\s*\[\s*((?:' + RSTRING + r'\s*,?\s*)+)\]\s*\)', text):
                values = re.findall(RSTRING, match[2])
                if len(values) == 5:
                    for code, value in zip(('de', 'fr', 'es', 'ja', 'zh-CN'), values):
                        english = decode(match[1])
                        if code != 'ja' or english not in overrides:
                            put(code, '', english, decode(value), main, text.count('\n', 0, match.start()) + 1, 'TABLE')
        elif app == 'grid':
            # Only the named Japanese table is a catalog; enum/display pairs are not.
            for table in TABLE.finditer(text):
                if table[1] not in ('JA', 'JAPANESE'):
                    continue
                for match in PAIR.finditer(table[2]):
                    put('ja', '', decode(match[1]), decode(match[2]), main, text.count('\n', 0, table.start(2) + match.start()) + 1, table[1])
            for path in sorted((root / 'src/i18n').glob('*.rs')):
                module = body(path).split('#[cfg(test)]')[0]
                for match in re.finditer('(' + RSTRING + r')\s*=>\s*(' + RSTRING + ')', module):
                    put(path.stem, '', decode(match[1]), decode(match[2]), path, module.count('\n', 0, match.start()) + 1)
        else:
            for path in [main, *sorted((root / 'src/i18n').glob('*.rs'))]:
                module = body(path).split('#[cfg(test)]')[0]
                for table in TABLE.finditer(module):
                    code = next((value for name, value in RUST_LANGUAGES.items() if table[1] == name or table[1].startswith(name + '_')), None)
                    if not code:
                        continue
                    triple_spans = []
                    for match in TRIPLE.finditer(table[2]):
                        triple_spans.append(match.span())
                        context, english, value = map(decode, match.groups())
                        put(code, context, english, value, path, module.count('\n', 0, table.start(2) + match.start()) + 1, table[1])
                    for match in PAIR.finditer(table[2]):
                        if not any(a <= match.start() < b for a, b in triple_spans):
                            put(code, '', decode(match[1]), decode(match[2]), path, module.count('\n', 0, table.start(2) + match.start()) + 1, table[1])

    # Literal source lookups can require a row before any catalog includes it.
    for path in sorted((root / 'src').rglob('*.rs')):
        if 'i18n' in path.parts or path.name.startswith('i18n') or path.name.endswith('_tests.rs'):
            continue
        text = path.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        matches = list(LOOKUP.finditer(text))
        if matches:
            body(path)  # Source lookup keys are also snapshot-bound inputs.
        for match in matches:
            keys.add(('', decode(match[1]), 'plain'))
    scoped = Path(__file__).resolve().parents[1] / 'patches/localization-shared' / (app + '-interface.tsv')
    if scoped.is_file():
        # A spreadsheet Cube and a 3D Cube share an English spelling, not meaning.
        scoped_keys = {unescape_tsv(line.split('\t')[0]) for line in scoped.read_text(encoding='utf-8').splitlines()
                       if line and not line.startswith('#')}
        for row in rows:
            if row['source'] in scoped_keys:
                row['donorScope'] = 'app'
    return {'app': app, 'source': str(source), 'available': source.is_dir(), 'rows': rows, 'keys': keys, 'files': files, 'issues': issues}


def read_supplement(path):
    """Optional authored exact-term rows; disagreements still become conflicts."""
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = []
    for entry in data.get('entries', []):
        if set(entry['values']) != set(LANGUAGES) or entry['values']['en'] != entry['source']:
            raise ValueError('Supplement entries must provide all six languages and exact English')
        for code in LANGUAGES:
            if code != 'en':
                rows.append({'app': 'shared-authored', 'language': code, 'context': entry.get('context', ''), 'source': entry['source'],
                             'translation': entry['values'][code], 'kind': entry.get('kind', 'plain'), 'forms': [entry['values'][code]],
                             'provenance': {'app': 'shared-authored', 'file': path.name, 'sha256': digest, 'review': data['review'], 'semanticScope': entry['meaning']}})
    return rows


def build_plan(apps, exceptions=(), supplement=()):
    """Return deterministic proposals; no catalog is modified by this function."""
    allowed = {(row.get('context', ''), row['source']) for row in exceptions}
    pool, rejected, current = defaultdict(list), [], defaultdict(list)
    for row in [row for app in apps for row in app['rows']] + list(supplement):
        if row['language'] == 'en':
            continue
        current[(row['app'], row['language'], *identity(row))].append(row)
        if row.get('donorScope') == 'app':
            continue  # Preserve its own valid translation, but never export its domain to another app.
        reason = invalid_reason(row, allowed)
        if reason:
            rejected.append({'language': row['language'], 'context': row['context'], 'source': row['source'], 'translation': row['translation'], 'reason': reason, 'provenance': row['provenance']})
        else:
            pool[(row['language'], *identity(row))].append(row)

    conflicts, accepted = [], {}
    for key, candidates in sorted(pool.items()):
        values = defaultdict(list)
        for candidate in candidates:
            # Plural category count and forms are part of a value, never flattened.
            values[json.dumps(candidate['forms'], ensure_ascii=False, separators=(',', ':'))].append(candidate)
        if len(values) != 1:
            conflicts.append({'language': key[0], 'context': key[1], 'source': key[2], 'kind': key[3],
                              'variants': [{'translation': group[0]['translation'], 'forms': group[0]['forms'], 'provenance': sorted([row['provenance'] for row in group], key=lambda p: json.dumps(p, sort_keys=True))} for _, group in sorted(values.items())]})
        else:
            accepted[key] = candidates

    proposals, unresolved, target_files = [], Counter(), Counter()
    for app in sorted(apps, key=lambda a: a['app']):
        if app['app'] not in APPS:  # Launcher is an immutable donor/reference.
            continue
        for context, source, kind in sorted(app['keys']):
            for code in LANGUAGES:
                if code == 'en':
                    continue
                existing = current.get((app['app'], code, context, source, kind), [])
                if existing and any(invalid_reason(row, allowed) is None for row in existing):
                    continue  # Never overwrite an existing nonempty valid translation.
                donors = accepted.get((code, context, source, kind), [])
                donors = [row for row in donors if row['app'] != app['app']]
                if not donors:
                    unresolved[(app['app'], code)] += 1
                    continue
                candidate = donors[0]
                target = suggested_target(app['app'], code, context)
                target_files[(app['app'], code, target['file'], target['format'])] += 1
                proposals.append({'app': app['app'], 'language': code, 'context': context, 'source': source, 'kind': kind,
                                  'translation': candidate['translation'], 'forms': candidate['forms'], 'placeholderShape': signature(expected_source(candidate)),
                                  'action': 'add' if not existing else 'replaceInvalid', 'previous': sorted({row['translation'] for row in existing}),
                                  'target': target, 'provenance': sorted([row['provenance'] for row in donors], key=lambda p: json.dumps(p, sort_keys=True))})
    counts = Counter((row['app'], row['language']) for row in proposals)
    summary = [{'app': app['app'], 'proposed': {code: counts[app['app'], code] for code in LANGUAGES if code != 'en'},
                'unresolved': {code: unresolved[app['app'], code] for code in LANGUAGES if code != 'en'}} for app in sorted(apps, key=lambda a: a['app']) if app['app'] in APPS]
    return {'schemaVersion': 1, 'languages': list(LANGUAGES),
            'policy': {'sourceMutation': False, 'exactContextAndEnglishOnly': True, 'allDonorsMustAgree': True, 'placeholderTokensMustMatch': True,
                       'chineseConversion': False, 'identifierOnlyReuse': False, 'existingValidRowsOverwritten': False,
                       'linguisticReview': 'Existing catalog provenance plus separately attributed authored supplement; screen and native execution still require verification.'},
            'officialExceptions': sorted(list(exceptions), key=lambda row: (row.get('context', ''), row['source'])),
            'inputs': [{'app': app['app'], 'available': app['available'], 'files': [{'file': file, 'sha256': digest} for file, digest in sorted(app['files'].items())], 'parseIssues': app['issues']} for app in sorted(apps, key=lambda a: a['app'])],
            'summary': summary, 'proposalCount': len(proposals), 'conflictCount': len(conflicts), 'rejectedCount': len(rejected),
            'targetFiles': [{'app': app, 'language': code, 'file': file, 'format': fmt, 'entries': count} for (app, code, file, fmt), count in sorted(target_files.items())],
            'proposals': proposals, 'conflicts': conflicts, 'rejected': sorted(rejected, key=lambda row: (row['language'], row['context'], row['source'], json.dumps(row['provenance'], sort_keys=True)))}


def suggested_target(app, code, context):
    """Hints only: creating a file still requires wiring it into that app's runtime."""
    stem = {'zh-CN': 'zh-hans', 'zh-TW': 'zh-hant'}.get(code, code)
    base = 'crates/ui-egui/'
    if app == 'light':
        return {'file': base + 'locales/' + stem + '.json', 'format': 'json'}
    if app == 'ui':
        stem = {'zh-CN': 'zh-Hans', 'zh-TW': 'zh-Hant'}.get(code, code)
        return {'file': base + 'locales/' + stem + '.toml', 'format': 'toml'}
    if app in ('design', 'effect', 'grid'):
        return {'file': base + 'src/i18n/kio-six-language.json', 'format': 'runtime-adapter-required', 'context': context}
    return {'file': base + 'src/i18n/' + stem + '.tsv', 'format': 'tsv'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--supplement', type=Path, help='Optional explicitly authored six-language exact terms')
    parser.add_argument('--exceptions', type=Path, help='Explicit official technical/product-name exception decisions')
    args = parser.parse_args()
    default_exceptions = Path(__file__).resolve().parents[1] / 'patches/localization-shared/official-exceptions.json'
    exception_path = args.exceptions or default_exceptions
    exceptions = json.loads(exception_path.read_text(encoding='utf-8'))['entries'] if exception_path.is_file() else []
    apps = [read_app(app, args.root / '.work/full-native' / app / 'source') for app in APPS]
    launcher = args.root / '.work/launcher/source'
    if launcher.is_dir():
        apps.append(read_app('launcher', launcher))
    plan = build_plan(apps, exceptions, read_supplement(args.supplement) if args.supplement else [])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'proposals': plan['proposalCount'], 'conflicts': plan['conflictCount'], 'rejected': plan['rejectedCount'], 'apps': plan['summary']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
