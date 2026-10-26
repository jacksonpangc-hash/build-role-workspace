"""Install a verified local Skill archive to a new directory. Never replace an existing Skill or user workspace."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile


def install(package,destination,expected_sha256):
    package=Path(package);destination=Path(destination).absolute()
    if any(p.is_symlink() for p in [package,*package.parents,destination,*destination.parents]):raise ValueError('Linked path')
    if destination.exists():raise ValueError('Destination already exists; preserve it and choose a new staging path')
    if package.stat().st_size>64*1024*1024:raise ValueError('Oversized package')
    raw=package.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Archive hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or len(names)>1000 or sum(i.file_size for i in infos)>64*1024*1024:raise ValueError('Ambiguous or oversized archive')
        for i in infos:
            p=PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or ':' in i.filename or not i.filename.startswith('build-role-workspace/') or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Unsafe archive entry')
        manifest_name='build-role-workspace/PACKAGE_MANIFEST.json'
        manifest=json.loads(z.read(manifest_name));expected={'build-role-workspace/'+r['path']:r for r in manifest['files']}
        if len(expected)!=len(manifest['files']) or set(names)!=(set(expected)|{manifest_name}):raise ValueError('Archive does not match manifest')
        for name,row in expected.items():
            data=z.read(name)
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Member hash mismatch')
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=Path(tempfile.mkdtemp(prefix='.brw-install-',dir=destination.parent))
        try:
            for name in names:
                target=temporary/PurePosixPath(name).relative_to('build-role-workspace')
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
            # mkdir reserves the destination without overwriting a concurrently-created folder.
            destination.mkdir()
            try:
                for child in temporary.iterdir():shutil.move(str(child),str(destination/child.name))
            except Exception:
                # Retain partial destination for inspection; no blanket deletion of user files.
                raise
        finally:shutil.rmtree(temporary)
    return dict(version=manifest['version'],destination=str(destination),discovery='NOT_RUN: refresh host and test separately')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package');p.add_argument('destination');p.add_argument('--sha256',required=True);a=p.parse_args()
    try:print(json.dumps(install(a.package,a.destination,a.sha256),ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,zipfile.BadZipFile) as error:p.exit(2,str(error)+'\n')
