"""Create deterministic release archives from an explicit allowlist; no remote operation."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.2.0-rc.4'
REVIEW_FILE='tools/public-content-approvals.json'
PUBLIC_FILES=['LICENSE','THIRD_PARTY_NOTICES.md','CONTRIBUTING.md','SECURITY.md','CHANGELOG.md',
              'docs/user-guide.md','docs/compatibility.md','docs/release/acceptance-report.md',
              'docs/release/support-matrix.md']

def verify_content_review(files):
    """Bind distribution approval to exact bytes, not merely an allowed path.

    A reviewer must classify and inspect changed content before updating this
    manifest. Building never renews approvals. This is not a semantic DLP engine.
    The review manifest itself has a closed schema, avoiding an unchecked notes
    field in generated distribution metadata.
    """
    try:
        review=json.loads(files[REVIEW_FILE].read_text())
        if set(review)!={'format_version','version','files'} or review['format_version']!=1 or review['version']!=VERSION:
            raise ValueError('Invalid content review metadata')
        expected=set(files)-{REVIEW_FILE}
        if not isinstance(review['files'],dict) or set(review['files'])!=expected:
            raise ValueError('Incomplete or extra content review entries')
        for rel in sorted(expected):
            row=review['files'][rel]
            if not isinstance(row,dict) or set(row)!={'sha256','origin'} or row['origin'] not in {'project_owned','synthetic_owned','legacy_contract','apache_license'}:
                raise ValueError('Invalid content review entry: '+rel)
            if row['sha256']!=hashlib.sha256(files[rel].read_bytes()).hexdigest():
                raise ValueError('Changed bytes require fresh content review: '+rel)
    except (OSError,KeyError,TypeError,json.JSONDecodeError) as error:
        raise ValueError('Missing or invalid content review manifest') from error

def collect():
    staged = ROOT/'release-src/README.md'
    files={'README.md':staged if staged.exists() else ROOT/'README.md'}
    for rel in PUBLIC_FILES:files[rel]=ROOT/rel
    inventory = ROOT/'tools/release-files.json'
    for rel in json.loads(inventory.read_text())['files']:
        parts=Path(rel)
        if parts.is_absolute() or '..' in parts.parts:
            raise ValueError('Unsafe allowlist path')
        files[rel]=ROOT/rel
    for rel,path in files.items():
        if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Missing or out-of-root release input: '+rel)
        current=path
        while current!=ROOT:
            if current.is_symlink():raise ValueError('Linked release input or ancestor: '+rel)
            current=current.parent
        if ('/' + 'Users' + '/') in path.read_text(errors='ignore') and path.suffix in ['.md','.json','.py','.yaml']:
            raise ValueError('Local absolute path in release content: '+rel)
    for source,name in [('docs/user-guide.md','USER_GUIDE.md'),('docs/compatibility.md','COMPATIBILITY.md')]:
        if (ROOT/source).read_bytes()!=(ROOT/'skills/build-role-workspace'/name).read_bytes():
            raise ValueError('Packaged user documentation differs from canonical source: '+source)
    verify_content_review(files)
    return files

def archive(path,files,prefix):
    records=[]
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,source in sorted(files.items()):
            content=source.read_bytes()
            info=zipfile.ZipInfo(prefix+'/'+name,(2026,10,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16;z.writestr(info,content)
            records.append(dict(path=name,bytes=len(content),sha256=hashlib.sha256(content).hexdigest()))
        info=zipfile.ZipInfo(prefix+'/PACKAGE_MANIFEST.json',(2026,10,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,json.dumps({'version':VERSION,'files':records},ensure_ascii=False,indent=2))
    return records

def build(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    files=collect();skillprefix='skills/build-role-workspace/'
    selected={k[len(skillprefix):]:v for k,v in files.items() if k.startswith(skillprefix)}
    skill=output/f'build-role-workspace-{VERSION}.skill.zip';source=output/f'build-role-workspace-{VERSION}.source.zip'
    archive(skill,selected,'build-role-workspace');archive(source,files,'build-role-workspace-source')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [skill,source]}
    (output/'SHA256SUMS.txt').write_text(''.join(f'{h}  {n}\n' for n,h in hashes.items()))
    return dict(skill=str(skill),source=str(source),hashes=hashes)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='dist');a=p.parse_args()
    print(json.dumps(build(Path(a.output)),indent=2))
