"""Read-only folder/ZIP discovery and explicit single-member copying. No macros or commands execute."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import time
import zipfile

from manifest import sha256


def safe_member(name):
    p=PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and '\x00' not in name


def discover(root, max_depth=2, max_members=10000, max_total_bytes=256*1024*1024,
             max_member_bytes=64*1024*1024, max_seconds=30, exclude=()):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Existing non-link authorized folder required')
    root=root.resolve(); excluded=[Path(x).resolve() for x in exclude]
    started=time.monotonic(); rows=[]; seen={}; count=0; used=0

    def add(path,content_hash=None,**fields):
        item=dict(path=path,sha256=content_hash,**fields)
        if content_hash:
            if content_hash in seen:item['duplicate_of']=seen[content_hash]
            else:seen[content_hash]=path
        rows.append(item);return item

    def archive(handle, prefix, container_hash, depth):
        nonlocal count,used
        if depth>max_depth:
            add(prefix,status='depth_limit',container_sha256=container_hash);return
        try:
            with zipfile.ZipFile(handle) as z:
                # zipfile parses the central directory; this cap limits processing, not parser allocation.
                infos=z.infolist(); duplicates=Counter(i.filename for i in infos)
                for index,info in enumerate(infos):
                    if count>=max_members:
                        add(prefix,status='member_limit',remaining=len(infos)-index,container_sha256=container_hash);break
                    if time.monotonic()-started>max_seconds:
                        add(prefix,status='time_limit',remaining=len(infos)-index,container_sha256=container_hash);break
                    count+=1;path=prefix+'!'+info.filename
                    common=dict(container_sha256=container_hash,member=info.filename,bytes=info.file_size,depth=depth)
                    if not safe_member(info.filename):add(path,status='blocked_path',**common);continue
                    mode=info.external_attr>>16
                    if stat.S_ISLNK(mode):add(path,status='blocked_symlink',**common);continue
                    if info.is_dir():add(path,status='directory',**common);continue
                    if duplicates[info.filename]>1:add(path,status='ambiguous_member',**common);continue
                    if info.flag_bits&1:add(path,status='encrypted',**common);continue
                    if info.file_size>max_member_bytes or used+info.file_size>max_total_bytes:
                        add(path,status='size_limit',**common);continue
                    if mode and stat.S_IFMT(mode) and not stat.S_ISREG(mode):
                        add(path,status='unsupported_object',**common);continue
                    try:
                        with z.open(info) as f:content=f.read(min(max_member_bytes,max_total_bytes-used)+1)
                        used+=len(content)
                        if len(content)!=info.file_size or len(content)>max_member_bytes or used>max_total_bytes:
                            add(path,status='size_limit',**common);continue
                        h=hashlib.sha256(content).hexdigest()
                        add(path,h,status='container_indexed' if info.filename.lower().endswith('.zip') else 'awaiting_extraction',**common)
                        if info.filename.lower().endswith('.zip'):archive(io.BytesIO(content),path,h,depth+1)
                    except (OSError,RuntimeError,ValueError,zipfile.BadZipFile,NotImplementedError):
                        add(path,status='unreadable_member',**common)
        except (OSError,ValueError,zipfile.BadZipFile,zipfile.LargeZipFile):
            add(prefix,status='unreadable_archive',container_sha256=container_hash)

    def visit(directory):
        try: children=sorted(directory.iterdir())
        except OSError:add(str(directory.relative_to(root)),status='unreadable_directory');return
        for path in children:
            rel=path.relative_to(root).as_posix()
            if path.is_symlink():add(rel,status='blocked_symlink');continue
            if any(path.resolve().is_relative_to(p) for p in excluded):continue
            if time.monotonic()-started>max_seconds:
                add(rel,status='time_limit');continue
            if path.is_dir():visit(path);continue
            if not path.is_file():add(rel,status='unsupported_object');continue
            try:
                h=sha256(path); size=path.stat().st_size
                add(rel,h,bytes=size,status='container_indexed' if path.suffix.lower()=='.zip' else 'awaiting_extraction')
                if path.suffix.lower()=='.zip':archive(path,rel,h,1)
            except OSError:add(rel,status='unreadable')
    visit(root)
    return dict(format_version=1,items=rows,counts=dict(Counter(x['status'] for x in rows)),
                processed_member_bytes=used,limits=dict(depth=max_depth,members=max_members,total_bytes=max_total_bytes,
                member_bytes=max_member_bytes,seconds=max_seconds),
                limitation='Hashes prove byte identity only. Indexed is not read. Time checked between files/members; OS reads and ZIP central-directory allocation are not hard resource-isolated.')


def extract_member(archive_path, member, destination, expected_sha256, max_bytes=64*1024*1024,
                   expected_container_sha256=None):
    """Copy exactly one safe ZIP member to a new, explicit work file; never overwrite."""
    source=Path(archive_path);dest=Path(destination)
    if not safe_member(member):raise ValueError('Unsafe member path')
    if any(p.is_symlink() for p in [source,*source.parents,dest,*dest.parents]):raise ValueError('Linked path')
    before=sha256(source)
    if expected_container_sha256 and before!=expected_container_sha256:raise ValueError('Container changed')
    with zipfile.ZipFile(source) as z:
        matches=[i for i in z.infolist() if i.filename==member]
        if len(matches)!=1:raise ValueError('Missing or ambiguous member')
        i=matches[0]
        mode=i.external_attr>>16
        if i.is_dir() or stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) and not stat.S_ISREG(mode)) or i.flag_bits&1 or i.file_size>max_bytes:
            raise ValueError('Blocked member')
        with z.open(i) as stream:content=stream.read(max_bytes+1)
    if len(content)>max_bytes or hashlib.sha256(content).hexdigest()!=expected_sha256 or sha256(source)!=before:
        raise ValueError('Size limit or source changed')
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(content)
    return dict(container_sha256=before,member=member,sha256=expected_sha256,destination=str(dest))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('scan');a.add_argument('root');a.add_argument('--exclude',action='append',default=[])
    a=s.add_parser('extract');a.add_argument('archive');a.add_argument('member');a.add_argument('destination');a.add_argument('--sha256',required=True);a.add_argument('--container-sha256',required=True)
    a=p.parse_args()
    try:
        result=discover(a.root,exclude=a.exclude) if a.command=='scan' else extract_member(a.archive,a.member,a.destination,a.sha256,expected_container_sha256=a.container_sha256)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,zipfile.BadZipFile) as error:p.exit(2,str(error)+'\n')
