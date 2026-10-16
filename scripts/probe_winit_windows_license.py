"""Read-only Windows Cargo checkout + exact winit license-link diagnostic.
No app build, GUI, model, installer or source mutation. Current guard is observed,
never changed; output records its actual result, including the expected failure.
"""
from pathlib import Path
import hashlib,importlib.util,json,os,platform,stat,subprocess,sys,traceback
COMMIT='3d51077fd1a966f84df9ef287839dc84fd5b4ca7'
SOURCE='git+https://github.com/skylartaylor/winit.git?rev='+COMMIT+'#'+COMMIT
COMMON_SHA='454f3f72c081e3f3f17fdbc5e39f44d8b8744264afdd61fcb6aaf4fc3f6aecf2';COMMON_BYTES=89260
LICENSE_SHA='6dc0e068dcf3a5bc8e054205b85b7720e1d49265bbc64bf515d2cf79197df69a';LICENSE_BYTES=11323
LINK_BLOB='ea5b60640b01f74e295037aa8a6b7d4ea278a739';LICENSE_BLOB='ad410e11302107da9aa47ce3d46bd5ad011c4c43'
def need(v,m):
 if not v:raise AssertionError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def command(args,cwd,env,cap=16*1024**2):
 r=subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
 need(len(r.stdout)<=cap and len(r.stderr)<=cap,'Bounded tool output');return r
def main():
 need(sys.platform=='win32' and platform.machine().upper() in ('AMD64','X86_64'),'Actual Windows x64 runner only')
 need(not os.environ.get('GH_TOKEN') and not os.environ.get('GITHUB_TOKEN'),'No repository token passed to Cargo or probe')
 root=Path(__file__).resolve().parents[1];base=Path(os.environ['RUNNER_TEMP'])/'kio-winit-license-probe';need(not base.exists() and not base.is_symlink(),'Fresh exact temporary probe directory');base.mkdir(mode=0o700)
 out=root/'winit-license-probe-evidence';need(not out.exists() and not out.is_symlink(),'Fresh exact evidence directory');out.mkdir(mode=0o700)
 report={'schema':'kio.winit-windows-license-link-probe.v1','status':'started','upstreamCommit':COMMIT,'source':SOURCE,'actualPlatform':sys.platform,'machine':platform.machine(),'python':sys.version,'nativeBuildPerformed':False,'guiExecuted':False,'installationPerformed':False,'publicationPerformed':False,'sourceChanged':False,'currentGuardChanged':False,'tokenPassedToCargo':False}
 try:
  common=root/'scripts/kio_native.py';need(common.stat().st_size==COMMON_BYTES and sha(common.read_bytes())==COMMON_SHA,'Exact d4fa current production guard bytes')
  fixture=root/'tests/fixtures/native-contracts'/('winit-'+COMMIT);original=(fixture/'LICENSE').read_bytes();provenance=json.loads((fixture/'provenance.json').read_text());need(len(original)==LICENSE_BYTES and sha(original)==LICENSE_SHA,'Original source-authenticated license fixture')
  need(provenance['originalLicenseLink']=={'path':'dpi/LICENSE','gitMode':'120000','gitBlob':LINK_BLOB,'bytes':10,'target':'../LICENSE','url':'https://github.com/skylartaylor/winit/blob/'+COMMIT+'/dpi/LICENSE'},'Exact original Git symlink fixture metadata')
  crate=base/'minimal';(crate/'src').mkdir(parents=True);manifest='[package]\nname = "kio-winit-license-probe"\nversion = "0.0.0"\nedition = "2021"\n\n[dependencies]\nwinit = { git = "https://github.com/skylartaylor/winit.git", rev = "'+COMMIT+'" }\n';(crate/'Cargo.toml').write_text(manifest,encoding='utf-8');(crate/'src/lib.rs').write_text('// metadata only; this source is never compiled\n',encoding='utf-8')
  cargo=root/'.cache/cargo';need(not cargo.exists() and not cargo.is_symlink(),'Fresh Cargo checkout cache');cargo.mkdir(parents=True)
  env=os.environ.copy();env['CARGO_HOME']=str(cargo);env.pop('GH_TOKEN',None);env.pop('GITHUB_TOKEN',None)
  gitversion=command(['git','--version'],root,env,4096);need(gitversion.returncode==0,'Git available');report['gitVersion']=gitversion.stdout.decode().strip()
  args=['rustup','run','1.95.0','cargo','metadata','--format-version','1','--filter-platform','x86_64-pc-windows-msvc'];r=command(args,crate,env)
  (out/'cargo-metadata.stderr.txt').write_bytes(r.stderr);(out/'cargo-command.json').write_text(json.dumps({'args':args,'exitCode':r.returncode,'stdoutBytes':len(r.stdout),'stdoutSha256':sha(r.stdout),'stderrBytes':len(r.stderr),'stderrSha256':sha(r.stderr)},indent=2)+'\n')
  need(r.returncode==0,'Exact Cargo metadata resolution/fetch must succeed');metadata=json.loads(r.stdout);packages=[p for p in metadata['packages'] if p['name']=='winit' and p['version']=='0.30.13' and p['source']==SOURCE];need(len(packages)==1,'Exactly original winit0.30.13 pinned Git package')
  package=packages[0];folder=Path(package['manifest_path']).parent.resolve(strict=True);need(folder.is_relative_to(cargo.resolve(strict=True)/'git/checkouts'),'Exact Cargo-managed Git checkout only')
  head=command(['git','rev-parse','HEAD'],folder,env,4096);need(head.returncode==0 and head.stdout.strip().decode()==COMMIT,'Actual checkout exact full original commit')
  tree=command(['git','ls-tree','HEAD','dpi/LICENSE','LICENSE'],folder,env,4096);need(tree.returncode==0,'Original Git metadata available');lines=tree.stdout.decode().splitlines();need('120000 blob '+LINK_BLOB+'\tdpi/LICENSE' in lines and '100644 blob '+LICENSE_BLOB+'\tLICENSE' in lines,'Original fixed Git link and legal-file blobs/modes')
  blob=command(['git','show','HEAD:dpi/LICENSE'],folder,env,4096);need(blob.returncode==0 and blob.stdout==b'../LICENSE','Original symlink blob exact10bytes');(out/'git-link-blob.txt').write_bytes(blob.stdout)
  original_root=command(['git','show','HEAD:LICENSE'],folder,env,64*1024);need(original_root.returncode==0 and original_root.stdout==original,'Original Git root legal blob matches exact immutable fixture')
  link=folder/'dpi/LICENSE';target=folder/'LICENSE';need(target.is_file() and not target.is_symlink() and target.stat().st_size<=64*1024,'Bounded real Cargo checkout root license')
  actual_root=target.read_bytes();report['actualRootLicense']={'bytes':len(actual_root),'sha256':sha(actual_root),'matchesOriginalGitAndFixture':actual_root==original}
  info=link.lstat();kind='symlink' if link.is_symlink() else 'regular' if stat.S_ISREG(info.st_mode) else 'other';report['actualLink']={'path':str(link),'kind':kind,'isSymlink':link.is_symlink(),'isFileFollowing':link.is_file(),'lstatMode':info.st_mode,'lstatSize':info.st_size,'windowsFileAttributes':getattr(info,'st_file_attributes',None),'windowsReparseTag':getattr(info,'st_reparse_tag',None)}
  if link.is_symlink():
   raw=os.readlink(link);report['actualLink'].update({'readlink':raw,'readlinkRepr':repr(raw),'resolvedTarget':str(link.resolve(strict=True)),'resolvesToExactOriginalRootLicense':link.resolve(strict=True)==target.resolve(strict=True)})
  elif stat.S_ISREG(info.st_mode):
   need(info.st_size<=64*1024,'Bounded materialized regular link');data=link.read_bytes();report['actualLink'].update({'regularBytes':len(data),'regularHex':data.hex(),'regularSha256':sha(data),'regularBytesRepr':repr(data)})
  report.update({'exactPackage':{k:package[k] for k in ('name','version','source','manifest_path','license','license_file')},'cargoMetadataPackageCount':len(metadata['packages']),'cargoMetadataSha256':sha(r.stdout),'gitTree':lines,'rootLicense':{'bytes':LICENSE_BYTES,'sha256':LICENSE_SHA,'gitBlob':LICENSE_BLOB},'originalLinkBlob':{'bytes':10,'sha256':sha(blob.stdout),'gitBlob':LINK_BLOB,'target':'../LICENSE'},'actualCargoConfig':{'CARGO_HOME':str(cargo),'CARGO_NET_GIT_FETCH_WITH_CLI':env.get('CARGO_NET_GIT_FETCH_WITH_CLI'),'GIT_CONFIG_NOSYSTEM':env.get('GIT_CONFIG_NOSYSTEM')}})
  spec=importlib.util.spec_from_file_location('original_d4fa_kio_native_guard',common);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  try:
   files=module.dependency_source_files(package,folder);report['actualCurrentGuard']={'status':'passed','files':len(files),'exception':None}
  except Exception as error:
   report['actualCurrentGuard']={'status':'rejected','exceptionType':type(error).__name__,'exception':str(error)}
  (out/'winit-root-LICENSE.txt').write_bytes(original);(out/'original-fixture-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');(out/'minimal-Cargo.toml').write_bytes((crate/'Cargo.toml').read_bytes());(out/'minimal-Cargo.lock').write_bytes((crate/'Cargo.lock').read_bytes());(out/'actual-guard-result.json').write_text(json.dumps(report['actualCurrentGuard'],indent=2)+'\n');report['status']='passed-authenticated-original-checkout-and-recorded-current-guard'
 except Exception as error:
  report.update({'status':'failed','error':str(error),'exceptionType':type(error).__name__});(out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8');raise
 finally:
  (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
