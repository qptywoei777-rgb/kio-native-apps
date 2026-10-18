#!/usr/bin/env python3
"""Apply a hash-pinned development localization patch to pristine prepared source.

This never modifies release locks/prepared receipts, packages installers, publishes
artifacts, or marks an incomplete localization complete. Normal release packaging
continues to reject this changed tree. Used only by candidate native test jobs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import full_native as native

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ('photo','vector','film','pdf','word','cad','deck','sound','grid')


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def relative_patch_path(patch, root):
    return patch.relative_to(root).as_posix()


def allowed(app, path):
    native.common.safe_relative(path)
    if path.startswith('crates/ui-egui/src/i18n/') and path.endswith('.tsv'):
        return True
    if app not in ('deck','sound','grid'):
        return False
    if path == 'docs/localization-parity.md':
        return True
    return path.endswith('.rs') and path.startswith(('crates/ui-egui/src/', f'apps/{app}craft/src/', f'apps/{app}craft-web/src/'))


def apply_candidate(app):
    lock=native.load_lock(app)
    _, source, _, prepared=native.prepared(lock)
    meta=json.loads((ROOT/f'patches/localization-candidates/{app}.json').read_text(encoding='utf-8'))
    native.require(meta['schema']=='kio.localization-development-patch.v1' and meta['programId']==app and meta['status']=='incomplete-not-release-approved','Invalid candidate identity')
    native.require(meta['basePreparedTreeSha256']==prepared['sourceTreeSha256'],'Candidate base differs from prepared original')
    patch=ROOT/f'patches/localization-candidates/{app}.patch'
    native.require(meta['patch']['path']==relative_patch_path(patch, ROOT) and checksum(patch.read_bytes())==meta['patch']['sha256'] and patch.stat().st_size==meta['patch']['bytes'],'Candidate patch bytes changed')
    entries=meta['files'];paths={row['path'] for row in entries}
    native.require(len(paths)==len(entries) and paths and all(allowed(app,p) for p in paths),'Unreviewed candidate file scope')
    before={name:checksum(path.read_bytes()) for name,path in native.source_files(lock,source)}
    for row in entries:
        value=row['before'];native.require((value is None and row['path'] not in before) or (value is not None and before.get(row['path'])==value['sha256']),'Candidate input hash mismatch')
    subprocess.run(['git','apply','--check',str(patch)],cwd=source,check=True)
    subprocess.run(['git','apply',str(patch)],cwd=source,check=True)
    after={name:checksum(path.read_bytes()) for name,path in native.source_files(lock,source)}
    native.require({p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)}==paths,'Candidate changed files outside its manifest')
    for row in entries:
        value=row['after'];native.require((value is None and row['path'] not in after) or (value is not None and after.get(row['path'])==value['sha256']),'Candidate output hash mismatch')
    output=ROOT/'dist'/f'{app}-candidate-source.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'program':app,'status':'development-not-release-approved','patchSha256':meta['patch']['sha256'],'files':len(paths),'sourceTreeSha256':native.source_fingerprint(lock,source),'protectedOriginalFilesUnchanged':True},indent=2)+'\n',encoding='utf-8')
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',choices=CANDIDATES,required=True)
    apply_candidate(parser.parse_args().app)
