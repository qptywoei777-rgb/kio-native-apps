#!/usr/bin/env python3
"""Verify KIO Deck's six authored source-keyed catalogs and locale policy.

Deck catalogs use context<TAB>English source<TAB>localized display text. Empty
context is a label; @msg marks a formatted/status/error template. Escapes are
\\n, \\t and \\\\. English is an explicit catalog, not an implicit completeness
fallback. This verifier requires no translation service, GUI or Rust dependencies.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path
LANGUAGES = ('vi','en','ko','ja','zh-TW','zh-CN')
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SOURCE=ROOT/'.work/full-native/deck/source'

def rust_strings(s):
    """Yield ordinary Rust string tokens outside comments/character literals."""
    i=0
    while i<len(s):
        if s.startswith('//',i):
            j=s.find('\n',i);i=len(s) if j<0 else j;continue
        if s.startswith('/*',i):
            depth=1;i+=2
            while i<len(s) and depth:
                if s.startswith('/*',i):depth+=1;i+=2
                elif s.startswith('*/',i):depth-=1;i+=2
                else:i+=1
            continue
        if s[i]=="'":
            m=re.match(r"'(?:\\.|[^'\\\n])'",s[i:])
            if m:i+=len(m[0]);continue
        if s[i]=='"':
            a=i;i+=1
            while i<len(s):
                if s[i]=='\\':i+=2;continue
                if s[i]=='"':
                    i+=1
                    raw=s[a:i]
                    try:value=json.loads(raw)
                    except ValueError:value=raw[1:-1]
                    yield a,i,value
                    break
                i+=1
            continue
        i+=1

def unescape(s):
    return re.sub(r'\\([nt\\])',lambda m:{'n':'\n','t':'\t','\\':'\\'}[m[1]],s)

def read_catalog(path):
    result={}
    for n,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if not line or line.startswith('#'):continue
        parts=line.split('\t')
        if len(parts)!=3:raise ValueError(f'{path}:{n}: expected 3 TSV columns')
        context,key,value=map(unescape,parts)
        if (context,key) in result:raise ValueError(f'{path}:{n}: duplicate {key!r}')
        if not value.strip():raise ValueError(f'{path}:{n}: empty translation for {key!r}')
        result[context,key]=value
    return result

def placeholders(s):
    return sorted(re.findall(r'(?<!\{)\{([^{}]*)\}(?!\})',s))

def verify(source):
    folder=source/'crates/ui-egui/src/i18n'
    catalogs={lang:read_catalog(folder/f'{lang}.tsv') for lang in LANGUAGES}
    english=catalogs['en'];errors=[]
    for lang,cat in catalogs.items():
        if cat.keys()!=english.keys():errors.append(f'{lang}: key mismatch missing {len(english.keys()-cat.keys())}, extra {len(cat.keys()-english.keys())}')
        for (context,key),value in cat.items():
            if placeholders(key)!=placeholders(value):errors.append(f'{lang}: placeholder mismatch {key!r}')
    # Lookups with literal source keys must all be covered.
    for path in (source/'crates/ui-egui/src').rglob('*.rs'):
        if path.name.endswith('_tests.rs'):continue
        text=path.read_text(encoding='utf-8').split('#[cfg(test)]')[0]
        for a,b,key in rust_strings(text):
            prefix=text[max(0,a-70):a]
            if re.search(r'i18n::(?:t|msg)\(\s*$',prefix) and ('',key) not in english and ('@msg',key) not in english:
                if re.search('[A-Za-z]',key):errors.append(f'{path.name}: missing literal lookup {key!r}')
    policy=(folder/'mod.rs').read_text(encoding='utf-8')
    for required in ('AppleLanguages','CurrentUICulture','interface_language','Tiếng Việt','繁體中文','简体中文'):
        if required not in policy:errors.append(f'locale policy missing {required}')
    report={'schemaVersion':1,'app':'deck','format':'context/source/translation TSV; plain and @msg; std-only exact/template runtime','languages':list(LANGUAGES),'catalogKeyUnion':len(english),'catalogs':[{'language':lang,'keys':len(cat),'sha256':hashlib.sha256((folder/f'{lang}.tsv').read_bytes()).hexdigest()} for lang,cat in catalogs.items()],'errors':errors}
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    parser.add_argument('--json',type=Path)
    args=parser.parse_args();report=verify(args.source)
    if args.json:args.json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(bool(report['errors']))
if __name__=='__main__':main()
