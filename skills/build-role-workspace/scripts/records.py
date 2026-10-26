"""Private scoped definitions and dependency snapshots; additive sidecar, not a legacy schema migration."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from workspace import Workspace, atomic_json, now
from manifest import sha256

KINDS={'context','gap','definition','report','review','case','source','extraction','metric','rule','artifact','action','handoff','schedule'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


class Records:
    def __init__(self,root,scope):
        if not isinstance(scope,str) or not scope.strip():raise ValueError('Explicit company/project scope required')
        self.workspace=Workspace(root);self.scope=scope
        self.path=self.workspace.root/('records-'+hashlib.sha256(scope.encode()).hexdigest()[:24]+'.json')

    def _read_unredacted(self):
        if self.path.is_symlink():raise ValueError('Linked record file')
        if not self.path.exists():return dict(format_version=1,record_type='private_records',scope=self.scope,records={})
        data=json.loads(self.path.read_text())
        if data.get('scope')!=self.scope or data.get('format_version')!=1 or data.get('record_type')!='private_records':raise ValueError('Scope or version mismatch')
        return data

    def read(self):
        """Display-safe snapshot; unredacted storage is private implementation detail."""
        data=deepcopy(self._read_unredacted());records=data['records']
        for key,history in records.items():
            for item in history:
                item['effective_status']=self._effective(key,records,set(),item['revision'])
        for history in records.values():
            for item in history:
                if item['effective_status']=='restricted':item.update(value={},redacted=True)
        return data

    def key(self,kind,name):
        if kind not in KINDS or not re.fullmatch(r'[\w.-]{1,100}',name):raise ValueError('Known kind and stable name required')
        return kind+':'+name

    def put(self,kind,name,value,dependencies=(),expected_revision=None,provenance_change_ref=None):
        key=self.key(kind,name)
        if not isinstance(value,dict):raise ValueError('Object value required')
        with self.workspace.locked():
            data=self._read_unredacted();records=data['records'];history=records.get(key,[]);old=history[-1] if history else None
            if old and (expected_revision!=old['revision'] or old['revoked']):raise ValueError('Conflict or revoked; read and merge, never revive silently')
            if not old and expected_revision not in (None,0):raise ValueError('Record does not exist')
            if old and self._effective(key,records,set())=='restricted':
                raise ValueError('Restricted record cannot be revised to remove provenance; keep history and create a genuinely independent record')
            removed=set(old['dependencies'])-set(dependencies) if old else set()
            old_file=old['value'].get('file_ref') if old else None
            new_file=value.get('file_ref')
            file_replaced=bool(old_file and (not new_file or old_file.get('path')!=new_file.get('path')))
            if (removed or file_replaced) and not (isinstance(provenance_change_ref,str) and provenance_change_ref.strip()):
                raise ValueError('Removing provenance requires explicit replacement evidence; content must be rederived, not relabeled')
            if len(set(dependencies))!=len(dependencies):raise ValueError('Duplicate dependencies')
            deps={}
            def reaches(candidate,target,visited):
                if candidate==target:return True
                if candidate in visited:return False
                visited.add(candidate)
                return any(reaches(d,target,visited) for d in records[candidate][-1]['dependencies'])
            for dep in dependencies:
                if dep not in records or reaches(dep,key,set()):raise ValueError('Missing dependency or cycle')
                if self._effective(dep,records,set())!='current':raise ValueError('Dependency not current')
                deps[dep]=records[dep][-1]['revision']
            item=dict(revision=len(history)+1,value=deepcopy(value),dependencies=deps,revoked=False,at=now())
            if removed or file_replaced:item['provenance_change_ref']=provenance_change_ref
            item['sha256']=digest(item['value']);records.setdefault(key,[]).append(item)
            atomic_json(self.path,data)
        return item

    def _effective(self,key,records,seen,revision=None):
        """Restrictions outrank staleness across both pinned and current ancestry."""
        history=records[key]
        item=history[-1] if revision is None else next((r for r in history if r['revision']==revision),None)
        if history[-1]['revoked'] or (item and item['revoked']):return 'restricted'
        if item is None:return 'stale'
        identity=(key,item['revision'])
        if identity in seen:return 'stale'
        seen=seen|{identity};states=[]
        for dep,rev in item['dependencies'].items():
            if dep not in records:
                states.append('stale');continue
            # Inspect every branch before evaluating local file state. Historical
            # ancestry cannot be erased by reparenting a newer revision.
            pinned=self._effective(dep,records,seen,rev)
            current=pinned if records[dep][-1]['revision']==rev else self._effective(dep,records,seen)
            if 'restricted' in (pinned,current):states.append('restricted')
            elif pinned!='current' or current!='current' or records[dep][-1]['revision']!=rev:states.append('stale')
            else:states.append('current')
        if 'restricted' in states:return 'restricted'
        file_ref=item['value'].get('file_ref')
        if file_ref:
            try:
                path=Path(file_ref['path'])
                if any(p.is_symlink() for p in [path,*path.parents]) or sha256(path)!=file_ref['sha256']:states.append('stale')
            except (OSError,KeyError,TypeError,ValueError):states.append('stale')
        return 'stale' if 'stale' in states else 'current'

    def observe_file(self,kind,name,path,expected_revision=None):
        path=Path(path).absolute()
        if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('Linked source path')
        return self.put(kind,name,{'file_ref':{'path':str(path),'sha256':sha256(path)}},expected_revision=expected_revision)

    def get(self,kind,name):
        key=self.key(kind,name);records=self._read_unredacted()['records']
        if key not in records:return None
        result=dict(deepcopy(records[key][-1]),effective_status=self._effective(key,records,set()))
        if result['effective_status']=='restricted':result.update(value={},redacted=True)
        return result

    def history(self,kind,name):
        key=self.key(kind,name);records=self._read_unredacted()['records']
        items=deepcopy(records.get(key,[]))
        for item in items:
            item['effective_status']=self._effective(key,records,set(),item['revision'])
            if item['effective_status']=='restricted':item.update(value={},redacted=True)
        return items

    def revoke(self,kind,name):
        key=self.key(kind,name)
        with self.workspace.locked():
            data=self._read_unredacted();old=data['records'][key][-1]
            item=dict(deepcopy(old),revision=old['revision']+1,revoked=True,at=now())
            data['records'][key].append(item);atomic_json(self.path,data)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--scope',required=True)
    p.add_argument('command',choices=['get','put','history','revoke']);p.add_argument('kind',choices=sorted(KINDS));p.add_argument('name')
    p.add_argument('--value');p.add_argument('--depends',action='append',default=[]);p.add_argument('--expected-revision',type=int);p.add_argument('--provenance-change-ref')
    a=p.parse_args()
    try:
        r=Records(a.workspace,a.scope)
        out=r.put(a.kind,a.name,json.loads(Path(a.value).read_text()),a.depends,a.expected_revision,a.provenance_change_ref) if a.command=='put' else getattr(r,a.command)(a.kind,a.name)
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:p.exit(2,str(error)+'\n')
