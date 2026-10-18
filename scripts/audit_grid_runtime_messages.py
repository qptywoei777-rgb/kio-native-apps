#!/usr/bin/env python3
"""Inventory Grid engine diagnostics reaching native messages, without user data.

This is an additional release gate, not a replacement for the catalog audit.
Literal error descriptions can use the UI's exact-key presentation boundary.
Formatted diagnostics need an explicitly reviewed route preserving opaque values.
Nested XLSX/library/OS errors still require separate review; never call this a
complete inventory of every possible runtime diagnostic.
"""
import argparse
import json
from pathlib import Path
import re
import audit_localization as audit

ROOT = Path(__file__).resolve().parents[1]
RULES = {
    'bad-parameters': re.compile(r'\bbad\(\s*[^,\n]+,\s*(?P<format>format!\s*\(\s*)?(?P<text>' + audit.RSTRING + ')'),
    'engine-other': re.compile(r'\bEngineError::Other\(\s*(?P<format>format!\s*\(\s*)?(?P<text>' + audit.RSTRING + ')'),
    'engine-error-display': re.compile(r'#\[error\(\s*(?P<text>' + audit.RSTRING + ')'),
}


def inventory(source):
    entries = {}
    for path in sorted((source / 'crates/engine/src').rglob('*.rs')):
        if path.name in ('tests.rs',) or 'tests' in path.relative_to(source).parts:
            continue
        text = path.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        tokens = re.compile(audit.RSTRING + r'|//[^\n]*|/\*.*?\*/', re.S)
        code = tokens.sub(lambda m: ' ' * len(m[0]) if m[0].startswith(('//', '/*')) else m[0], text)
        for rule, pattern in RULES.items():
            for match in pattern.finditer(code):
                message = audit.literal(match['text'])
                if not message.strip():
                    continue
                dynamic = bool(match.groupdict().get('format')) or (rule == 'engine-error-display' and bool(audit.placeholders(message)))
                key = (message, dynamic)
                entry = entries.setdefault(key, {'source': message, 'dynamic': dynamic, 'locations': []})
                entry['locations'].append({'path': path.relative_to(source).as_posix(), 'line': code.count('\n', 0, match.start()) + 1, 'rule': rule})
    return sorted(entries.values(), key=lambda row: (row['source'], row['dynamic']))


def report(source):
    catalogs, _, errors = audit.collect_catalogs(source)
    available = (source/'crates/engine/src').is_dir() and bool(catalogs.get('en'))
    rows = inventory(source)
    for row in rows:
        key = ('', row['source'])
        row['missingLanguages'] = [code for code in audit.LANGUAGES if code != 'en' and not catalogs.get(code, {}).get(key, '').strip()]
        # Formatting whose entire content is opaque values has no translatable
        # prose. Keep it visible for nesting review, not as a translated caption.
        fixed = re.sub(r'\{[^{}]*\}', '', row['source'])
        row['opaqueOnly'] = row['dynamic'] and not any(char.isalpha() for char in fixed)
        row['pending'] = not row['opaqueOnly'] and bool(row['dynamic'] or row['missingLanguages'])
    pending = [row for row in rows if row['pending']]
    return {'app': 'grid', 'scope': __doc__.strip(), 'sourceAvailable': available, 'catalogParseErrors': errors,
            'inventoriedTemplates': len(rows), 'pendingTemplates': len(pending),
            'opaqueOnlyTemplates': sum(row['opaqueOnly'] for row in rows),
            'complete': available and not pending and not errors, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'.work/full-native/grid/source')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    result = report(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Grid runtime diagnostics: {result['inventoriedTemplates']} templates, {result['pendingTemplates']} pending, complete={result['complete']}")
    return int(args.require_complete and not result['complete'])


if __name__ == '__main__':
    raise SystemExit(main())
