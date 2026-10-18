#!/usr/bin/env python3
"""Audit the real native workspaces; never equate a catalog with complete GUI QA.

Python 3.11+. No network, external translation service, credentials or user data.
Counts use the union of existing catalog keys plus literal translation calls. The
separate direct-UI list is a review queue, not an assertion that every literal is
user-facing (IDs, document text and expressions require contextual review).
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib

LANGUAGES = ('vi', 'en', 'ko', 'ja', 'zh-TW', 'zh-CN')
APPS = ('photo', 'vector', 'film', 'light', 'pdf', 'effect', 'design', 'ui', 'word', 'sound', 'deck', 'cad', 'grid', 'launcher')
ALIASES = {'zh': 'zh-CN', 'zh-cn': 'zh-CN', 'zh-hans': 'zh-CN', 'zh-tw': 'zh-TW', 'zh-hant': 'zh-TW'}
RSTRING = r'"(?:[^"\\]|\\.)*"'
PLACEHOLDER = re.compile(r'(?<!\{)\{([A-Za-z_][\w]*(?::[^{}]*)?)\}(?!\})')
DIRECT_UI = re.compile(r'\.(?:label|button|small_button|heading|strong|weak|small|menu_button|link|on_hover_text|on_disabled_hover_text|hint_text|selected_text)\s*\(\s*(' + RSTRING + ')')
DIRECT_CHOICE_UI = re.compile(r'\.(?:radio|selectable_label|checkbox)\s*\(\s*[^,\n;()]+,\s*(' + RSTRING + ')')
DIRECT_RICH_UI = re.compile(r'\bRichText::new\s*\(\s*(' + RSTRING + ')')
DIRECT_WINDOW_UI = re.compile(r'\bWindow::new\s*\(\s*(' + RSTRING + ')')
DIRECT_LINK_UI = re.compile(r'\.hyperlink_to\s*\(\s*(' + RSTRING + ')')
CUSTOM_CHECKBOX_UI = re.compile(r'\b(?:crate::)?widgets::checkbox\s*\(\s*ui\s*,\s*[^,\n]+,\s*(' + RSTRING + ')')
DIRECT_FORMAT_UI = re.compile(r'\.(?:label|button|small_button|heading|strong|weak|small|hyperlink_to|on_hover_text|hint_text|selected_text)\s*\(\s*(?:(?:egui::)?RichText::new\s*\(\s*)?format!\s*\(\s*(' + RSTRING + ')')
LOOKUP = re.compile(r'(?:\btl!\s*\(|\b(?:i18n::)?(?:t|tr|tr_noop|trf|trn|msg)\s*\()\s*(?:&\s*)?\(*\s*(' + RSTRING + ')')
OFFICIAL_NAMES = {'launcher': {('', value) for value in ('Launcher', 'KIO App Suite', 'Discord', 'GitHub', 'KIO Launcher {version}', 'KIO Launcher', 'ArtCraft', '{name} {version}')}}


def reviewed_exceptions(app, language):
    path = Path(__file__).resolve().parents[1] / 'patches/localization-shared/reviewed-interface-exceptions.json'
    entries = json.loads(path.read_text(encoding='utf-8'))['entries'] if path.is_file() else []
    return {(row.get('context', ''), row['source']) for row in entries
            if row['app'] == app and language in row['languages'] and row.get('reason')}


def canonical_language(code):
    code = code.lower().replace('_', '-')
    return ALIASES.get(code, code)


def literal(raw):
    # Rust's Unicode escapes use braces rather than JSON's four-digit spelling.
    raw = re.sub(r'\\u\{([0-9a-fA-F_]+)\}', lambda m: chr(int(m[1].replace('_', ''), 16)), raw)
    try:
        return json.loads(raw)
    except ValueError:
        return raw[1:-1].replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')


def unescape_tsv(text):
    return re.sub(r'\\([nt\\])', lambda m: {'n': '\n', 't': '\t', '\\': '\\'}[m[1]], text)


def display_prose(text):
    # Catch Korean/Japanese/Chinese and accented Vietnamese too; single Latin
    # hotkey letters and punctuation-only icons are technical, not prose.
    return sum(char.isalpha() for char in text) >= 2 or bool(re.search('[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7a3]', text))


def read_tsv(path):
    rows, errors = {}, []
    for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        cols = line.split('\t')
        if len(cols) != 3:
            errors.append({'line': n, 'type': 'invalidColumns'})
            continue
        context, source, translation = map(unescape_tsv, cols)
        key = (context, source)
        if key in rows:
            errors.append({'line': n, 'type': 'duplicate', 'key': list(key)})
        rows[key] = translation
    return rows, errors


def collect_catalogs(source):
    root = source / 'crates/ui-egui'
    catalogs, files, errors = {}, [], []
    def put(code, rows, path):
        lang = canonical_language(code)
        catalogs.setdefault(lang, {}).update(rows)
        files.append({'path': path.relative_to(source).as_posix(), 'language': lang, 'keys': len(rows), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for f in sorted((root / 'src/i18n').glob('*.tsv')):
        rows, bad = read_tsv(f)
        errors.extend({'file': f.relative_to(source).as_posix(), **e} for e in bad)
        put(f.stem, rows, f)
    for f in sorted((root / 'locales').glob('*.json')):
        if f.stem.endswith('-formats'):
            continue  # format patterns are audited separately; they are not interface messages
        data = json.loads(f.read_text(encoding='utf-8'))
        put(f.stem, {('', k): v for k, v in data.items() if isinstance(v, str)}, f)
    for f in sorted((root / 'locales').glob('*.toml')):
        data, rows = tomllib.loads(f.read_text(encoding='utf-8')), {}
        for section in ('ui', 'commands', 'menu'):
            for k, value in data.get(section, {}).items():
                rows[('' if section == 'ui' else '@' + section, k)] = value if isinstance(value, str) else value.get('other', '')
        put(f.stem, rows, f)
    main = root / 'src/i18n.rs'
    if main.is_file() and not list((root / 'locales').glob('*')):
        text = main.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        # Design's five-language column table.
        for m in re.finditer(r'\(\s*(' + RSTRING + r')\s*,\s*\[\s*((?:' + RSTRING + r'\s*,?\s*)+)\]\s*\)', text):
            values = re.findall(RSTRING, m[2])
            if len(values) == 5:
                for lang, raw in zip(('de', 'fr', 'es', 'ja', 'zh-CN'), values):
                    catalogs.setdefault(lang, {})[('', literal(m[1]))] = literal(raw)
        # Design's dedicated Japanese table wins over the legacy shared column.
        # Ignoring it reports more than a thousand already translated labels as English.
        ja = root / 'src/i18n/ja.rs'
        if source.parent.name == 'design' and ja.is_file():
            body = ja.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
            rows = {('', literal(m[1])): literal(m[2]) for m in re.finditer(r'\(\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,?\s*\)', body)}
            put('ja', rows, ja)
        # Grid's Japanese pairs and its per-language match tables.
        if source.parent.name == 'grid':
            for table in re.finditer(r'(?:const|static)\s+(?:JA|JAPANESE)\b[^=]+?=\s*&\[(.*?)\n\];', text, re.S):
                for m in re.finditer(r'\(\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,?\s*\)', table[1]):
                    catalogs.setdefault('ja', {})[('', literal(m[1]))] = literal(m[2])
            for f in (root / 'src/i18n').glob('*.rs'):
                code = canonical_language(f.stem)
                rows = {('', literal(m[1])): literal(m[2]) for m in re.finditer('(' + RSTRING + r')\s*=>\s*(' + RSTRING + ')', f.read_text(encoding='utf-8').split('#[cfg(test)]')[0])}
                if rows:
                    put(code, rows, f)
        # Effect uses separate command/source/translation and plain-source tables.
        if source.parent.name == 'effect':
            names = {'JAPANESE': 'ja', 'SIMPLIFIED_CHINESE': 'zh-CN', 'TRADITIONAL_CHINESE': 'zh-TW', 'KOREAN': 'ko', 'VIETNAMESE': 'vi'}
            for f in [main, *sorted((root / 'src/i18n').glob('*.rs'))]:
                body = f.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
                for m in re.finditer(r'(?:const|static)\s+(\w+)[^=]+?=\s*&\[(.*?)\n\];', body, re.S):
                    lang = next((v for k, v in names.items() if m[1].startswith(k)), None)
                    if not lang:
                        continue
                    for row in re.finditer(r'\(\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')(?:\s*,\s*(' + RSTRING + r'))?\s*\)', m[2]):
                        if row[3]:
                            key, value = (literal(row[1]), literal(row[2])), literal(row[3])
                        else:
                            key, value = ('', literal(row[1])), literal(row[2])
                        catalogs.setdefault(lang, {})[key] = value
    return catalogs, files, errors


def source_literals(source):
    keys, review = set(), []
    root = source / 'crates/ui-egui/src'
    roots = [root, *(path / 'src' for path in (source / 'apps').glob('*') if path.is_dir())]
    for f in sorted({path for folder in roots for path in folder.rglob('*.rs')}):
        if 'i18n' in f.parts or f.name.startswith('i18n') or f.name.endswith('_tests.rs'):
            continue
        text = f.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        for m in LOOKUP.finditer(text):
            value = literal(m[1])
            # Empty text and punctuation-only icons have no linguistic content.
            if any(c.isalpha() for c in value):
                keys.add(('', value))
        for m in (*DIRECT_UI.finditer(text), *DIRECT_CHOICE_UI.finditer(text), *DIRECT_RICH_UI.finditer(text), *DIRECT_LINK_UI.finditer(text), *CUSTOM_CHECKBOX_UI.finditer(text)):
            value = literal(m[1])
            if display_prose(value):
                review.append({'path': f.relative_to(source).as_posix(), 'line': text.count('\n', 0, m.start()) + 1, 'text': value})
        for m in DIRECT_WINDOW_UI.finditer(text):
            # A hidden-title window may use its constructor solely as a stable widget ID.
            if re.match(r'\s*\)\s*\.title_bar\(false\)', text[m.end():]):
                continue
            value = literal(m[1])
            if display_prose(value):
                review.append({'path': f.relative_to(source).as_posix(), 'line': text.count('\n', 0, m.start()) + 1, 'text': value})
        for m in DIRECT_FORMAT_UI.finditer(text):
            value = literal(m[1])
            fixed = re.sub(r'\{[^{}]*\}', '', value).strip()
            # Standard unit symbols remain literal; variable names themselves
            # are not UI text. Actual prose around arguments needs localization.
            if display_prose(fixed) and fixed not in {'pt', 'px', 'mm', 'cm', 'in', 'ms', 'Hz', 'kHz', 'KB', 'MB', 'GB', 'TB'}:
                review.append({'path': f.relative_to(source).as_posix(), 'line': text.count('\n', 0, m.start()) + 1, 'text': value, 'kind': 'untranslatedFormatTemplate'})
    return keys, review


def grid_metadata_keys(source):
    """Grid draws engine labels, form metadata and function help indirectly.

    Only presentation fields and function descriptions are included. Formula
    names/signatures, command IDs, parameter docs and workbook values stay out.
    """
    keys = set()
    folders = [source / 'crates/engine/src/cmd', source / 'crates/ui-egui/src']
    for folder in folders:
        for path in folder.glob('*.rs'):
            if path.name.startswith('i18n'):
                continue
            text = path.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
            for match in re.finditer(r'\bcmd!\s*\(\s*(?:(?:noundo|query)\s+)?' + RSTRING + r'\s*,\s*(' + RSTRING + r')\s*,\s*\[([^\]]*)\]', text):
                keys.add(('', literal(match[1])))
                keys.update(('', literal(raw)) for raw in re.findall(RSTRING, match[2]))
            for match in re.finditer(r'\blabel:\s*(' + RSTRING + ')', text):
                keys.add(('', literal(match[1])))
            for match in re.finditer(r'\bmenu:\s*&\[([^\]]*)\]', text):
                keys.update(('', literal(raw)) for raw in re.findall(RSTRING, match[1]))
            for match in re.finditer(r'\b(?:Dialog::)?(?:form|custom)\(\s*' + RSTRING + r'\s*,\s*(' + RSTRING + ')', text):
                keys.add(('', literal(match[1])))
            # Static menu tuples separate the human label from command/format IDs.
            for block in re.finditer(r'for\s*\(\s*label\s*,[^)]*\)\s+in\s*\[(.*?)\]\s*\{', text, re.S):
                for row in re.finditer(r'\(\s*(' + RSTRING + r')\s*,', block[1]):
                    keys.add(('', literal(row[1])))
            # Choice tuples store (wire value, displayed caption), in that order.
            for block in re.finditer(r'\boptions:\s*vec!\[(.*?)\]', text, re.S):
                for row in re.finditer(r'\(\s*' + RSTRING + r'\s*,\s*(' + RSTRING + r')\s*\)', block[1]):
                    keys.add(('', literal(row[1])))
    function_names = set()
    for path in (source / 'crates/functions/src').glob('*.rs'):
        text = path.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        # Mask comments, preserving string contents and offsets.
        tokens = re.compile(RSTRING + r'|//[^\n]*|/\*.*?\*/', re.S)
        code = tokens.sub(lambda m: ' ' * len(m[0]) if m[0].startswith(('//', '/*')) else m[0], text)
        for match in re.finditer(r'\bf!\s*\(', code):
            strings = re.findall(RSTRING, code[match.end():match.end() + 8192])[:3]
            if len(strings) == 3:
                name, signature, description = map(literal, strings)
                if re.fullmatch('[A-Z][A-Z0-9.]*', name) and signature.startswith(name + '('):
                    keys.add(('', description))
                    function_names.add(name)
    special = source / 'crates/engine/src/cmd/formulas.rs'
    if special.is_file():
        text = special.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        block = re.search(r'let specials:[^=]+=\s*&\[(.*?)\n\s*\];', text, re.S)
        if block:
            for row in re.finditer(r'\(\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,\s*(' + RSTRING + r')\s*,?\s*\)', block[1]):
                name, category, signature, description = map(literal, row.groups())
                if name not in function_names and signature.startswith(name + '('):
                    keys.update({('', category), ('', description)})
    return keys


def placeholders(text):
    # Count anonymous/positional/format-spec arguments too, preserving repeated
    # variables. Doubled braces and percent signs are literal escape sequences.
    rust = re.compile(r'\{((?:[A-Za-z_]\w*|\d*)(?::[^{}]*)?)\}')
    printf = re.compile(r'%(?:\d+\$)?[-+#0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hlLjzt])?[diuoxXfFeEgGaAcspn](?![A-Za-z])')
    qt = re.compile(r'%(?:L?\d+|n)\b')
    result, index = Counter(), 0
    while index < len(text):
        if text[index:index + 2] in ('{{', '}}', '%%'):
            index += 2
            continue
        match = rust.match(text, index)
        if match:
            result[match[1]] += 1
        else:
            match = printf.match(text, index) or qt.match(text, index)
            if match:
                result[match[0]] += 1
        index = match.end() if match else index + 1
    return result


def audit_app(app, source):
    if not source.is_dir():
        return {'id': app, 'sourceAvailable': False, 'complete': False}
    catalogs, inputs, parse_errors = collect_catalogs(source)
    literal_keys, direct = source_literals(source)
    if app == 'grid':
        literal_keys |= grid_metadata_keys(source)
    catalog_keys = set().union(*[set(c) for c in catalogs.values()])
    # Source-keyed format messages have a dedicated catalog context. A literal
    # call without that storage detail must not create a second phantom key.
    literal_keys = {('@msg', text) if (context, text) not in catalog_keys and ('@msg', text) in catalog_keys else (context, text)
                    for context, text in literal_keys}
    # A known visible raw caption is missing in every target language even before
    # a developer wraps it in a lookup; moving it into the catalog cannot hide debt.
    direct_keys = {('@msg' if ('@msg', row['text']) in catalog_keys else '', row['text']) for row in direct}
    keys = catalog_keys | literal_keys | direct_keys
    rows = {}
    for lang in LANGUAGES:
        exceptions = OFFICIAL_NAMES.get(app, set()) | reviewed_exceptions(app, lang)
        data = {key: key[1] for key in keys} if lang == 'en' else catalogs.get(lang, {})
        missing = sorted(keys - data.keys())
        empty, mismatch, unchanged = [], [], []
        for key, value in data.items():
            context, english = key
            if not str(value).strip():
                empty.append(list(key))
            if context != '@id' and context not in ('@commands', '@menu'):
                # Invariant-noun languages use a single plural form.
                expected = placeholders(english.split('|')[0] if context == '@plural' else english)
                if any(placeholders(form) != expected for form in (value.split('|') if context == '@plural' else [value])):
                    mismatch.append(list(key))
            if lang != 'en' and value == english and key not in exceptions and re.search('[A-Za-z]{3}', english):
                unchanged.append(list(key))  # review queue, including legitimate official names
        rows[lang] = {'keys': len(data), 'missing': len(missing), 'empty': len(empty), 'placeholderErrors': len(mismatch), 'sameAsEnglishReview': len(unchanged), 'missingKeys': [list(k) for k in missing], 'emptyKeys': empty, 'placeholderKeys': mismatch, 'unchangedKeys': unchanged}
    complete = bool(keys) and not direct and not parse_errors and all(not (r['missing'] or r['empty'] or r['placeholderErrors'] or r['sameAsEnglishReview']) for r in rows.values())
    return {'id': app, 'sourceAvailable': True, 'catalogKeyUnion': len(keys), 'catalogFiles': inputs, 'parseErrors': parse_errors, 'languages': rows, 'directUiReview': direct, 'complete': complete, 'guiTested': False, 'officialNameExceptions': [list(k) for k in sorted(OFFICIAL_NAMES.get(app, set()))]}


def finding_id(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def finding_inventory(app):
    """Stable identities let existing debt be visible without permitting new debt."""
    issues = {}
    for lang, row in app.get('languages', {}).items():
        for field in ('missingKeys', 'emptyKeys', 'placeholderKeys', 'unchangedKeys'):
            issues[lang + ':' + field] = sorted(finding_id(key) for key in row[field])
    issues['directUiReview'] = sorted({finding_id({'path': row['path'], 'text': row['text']}) for row in app.get('directUiReview', [])})
    issues['parseErrors'] = sorted(finding_id(row) for row in app.get('parseErrors', []))
    if not app.get('sourceAvailable'):
        issues['sourceUnavailable'] = [finding_id(app['id'])]
    return issues


def regressions(app, baseline):
    known = baseline.get('apps', {}).get(app['id'])
    if known is None:
        return {'unreviewedApplication': [app['id']]}
    return {category: sorted(new) for category, values in finding_inventory(app).items()
            if (new := set(values) - set(known.get(category, [])))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--app', choices=(*APPS, 'all'), default='all')
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--baseline', type=Path, help='Fail for new findings relative to reviewed existing debt; does not assert completeness')
    args = parser.parse_args()
    apps = [audit_app(app, args.root / ('.work/launcher/source' if app == 'launcher' else '.work/full-native/' + app + '/source')) for app in (APPS if args.app == 'all' else (args.app,))]
    report = {'schemaVersion': 1, 'languages': list(LANGUAGES), 'method': 'catalog union plus literal lookups; direct UI calls require contextual review; static coverage does not prove screen or native execution', 'apps': apps}
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
        if baseline.get('schemaVersion') != 1 or baseline.get('languages') != list(LANGUAGES):
            raise ValueError('Localization baseline schema or required language order changed')
        for app in apps:
            app['regressions'] = regressions(app, baseline)
        report['noNewFindings'] = all(not app['regressions'] for app in apps)
        report['baselineSha256'] = hashlib.sha256(args.baseline.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for app in apps:
        print(app['id'], 'keys', app.get('catalogKeyUnion', 0), 'missing', {k: v['missing'] for k, v in app.get('languages', {}).items()}, 'directUIReview', len(app.get('directUiReview', [])), 'complete', app['complete'])
    return int((args.require_complete and not all(a['complete'] for a in apps)) or report.get('noNewFindings') is False)


if __name__ == '__main__':
    sys.exit(main())
