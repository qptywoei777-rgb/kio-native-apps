#!/usr/bin/env python3
"""Regenerate the explicitly incomplete Grid overlay from original rows and exact donors.

Prepare all suite workspaces first. No network or translation service is called.
Only exact keys and reviewed punctuation/shortcut variants are reused; missing
translations stay missing and the strict release audit must continue to fail.
"""
from pathlib import Path
import json,sys,collections
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
import audit_localization as audit,reuse_six_language_catalogs as reuse,seed_editor_catalogs as seed
source=root/'.work/full-native/grid/source';data=root/'patches/localization-shared';out=root/'dist';out.mkdir(exist_ok=True)
catalogs,_,_=audit.collect_catalogs(source);keys=set().union(*(set(v) for v in catalogs.values()));literals,direct=audit.source_literals(source);keys|=literals;keys|=audit.grid_metadata_keys(source)
keys|={('',x['text']) for x in direct}
keys.add(('','Follow system language'))
# Exact original Grid rows always win over a generic donor.
allowed={(e.get('context',''),e['source']) for e in json.loads((data/'official-exceptions.json').read_text())['entries']}
donors=collections.defaultdict(set)
for app in (*reuse.APPS,'launcher'):
 if app=='grid':continue
 src=root/('.work/launcher/source' if app=='launcher' else '.work/full-native/'+app+'/source')
 for row in reuse.read_app(app,src)['rows']:
  if row['language']=='en' or row['context'] or row['kind']!='plain' or reuse.invalid_reason(row,allowed):continue
  donors[row['source'],row['language']].add(row['translation'])
pool={k:next(iter(v)) for k,v in donors.items() if len(v)==1}
for row in reuse.read_supplement(data/'common-software-terms.json'):pool[row['source'],row['language']]=row['translation']
for k,v in seed.authored_rows(data/'editor-interface.tsv').items():
 for code,text in v.items():pool[k,code]=text
scoped=data/'grid-interface.tsv';authored=seed.authored_rows(scoped) if scoped.exists() else {};keys|={('',key) for key in authored}
folder=source/'crates/ui-egui/src/i18n';report={'app':'grid','keys':len(keys),'scope':'Development inventory includes static UI, command/form metadata and function help. Engine error messages and additional dynamic captions still require review. Never count missing fallback as translated.','languages':{}}
escape=lambda v:v.replace('\\','\\\\').replace('\n','\\n').replace('\t','\\t')
import re
report['derivedEntries']=[]
def derive(key, known):
 trimmed=key.strip()
 if trimmed != key and trimmed in known:
  return key[:len(key)-len(key.lstrip())]+known[trimmed]+key[len(key.rstrip()):], 'outer whitespace'
 for suffix in ('…','...',':'):
  if key.endswith(suffix) and key[:-len(suffix)] in known:
   return known[key[:-len(suffix)]]+suffix, 'trailing punctuation'
 shortcut=re.fullmatch(r'(.+) (\([⌘⇧⌥⌃A-Za-z0-9+]+\))',key)
 if shortcut and shortcut[1] in known:
  return known[shortcut[1]]+' '+shortcut[2], 'unchanged shortcut'
 for prefix in ('↑  ','↓  ','+ '):
  if key.startswith(prefix) and key[len(prefix):] in known:
   return prefix+known[key[len(prefix):]], 'unchanged decoration'
 return None
for code in reuse.LANGUAGES:
 values={};missing=[]
 for context,key in sorted(keys):
  value=key.rsplit('|',1)[-1] if code=='en' else authored.get(key,{}).get(code) or catalogs.get(code,{}).get((context,key)) or pool.get((key,code))
  if value:values[key]=value
 for context,key in sorted(keys):
  if key not in values:
   result=derive(key,values)
   if result and reuse.placeholders(result[0])==reuse.placeholders(key):
    values[key]=result[0];report['derivedEntries'].append({'language':code,'source':key,'translation':result[0],'rule':result[1]})
  if key not in values:missing.append(key)
 rows=['\t'.join(map(escape,(context,key,values[key]))) for context,key in sorted(keys) if key in values]
 (folder/(code+'.tsv')).write_text('# KIO Grid interface overlay; original extra language catalogs remain intact.\n'+'\n'.join(rows)+'\n')
 report['languages'][code]={'keys':len(rows),'missing':len(missing),'missingKeys':missing}
(data/'grid-source-keys.json').write_text(json.dumps({'keys':sorted(k for c,k in keys),'scope':report['scope']},ensure_ascii=False,indent=2)+'\n')
(out/'grid-source-progress.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'app':report['app'],'keys':report['keys'],'derivedEntries':len(report['derivedEntries']),'languages':{k:{n:v for n,v in row.items() if n!='missingKeys'} for k,row in report['languages'].items()}},ensure_ascii=False))
