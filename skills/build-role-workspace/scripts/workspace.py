"""Small local workspace index, separate from business records and legacy v1 schemas."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from manifest import scan, sha256

ROLES = ['video_analysis', 'director_script', 'ecommerce_operations',
         'advertising_operations', 'finance_reconciliation', 'administration',
         'customer_service', 'sales_crm', 'human_resources', 'procurement',
         'warehouse_logistics', 'project_delivery', 'business_analytics', 'it_service_desk']
STAGES = ['intake', 'workflow_mapping', 'rule_elicitation', 'sample_calibration',
          'working_result', 'workflow_acceptance', 'automation_assessment',
          'automation_build', 'completed_manual', 'completed_assisted', 'ready_for_scoped_run']


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Workspace:
    def __init__(self, root):
        raw = Path(root).absolute()
        if raw.is_symlink():
            raise ValueError('Workspace root must not be a symlink')
        # Resolve platform aliases such as macOS /var -> /private/var once.
        # Paths created beneath this explicit root are still checked for links.
        self.root = raw.resolve()
        self.path = self.root / 'workspace.json'

    @contextmanager
    def locked(self):
        # Kernel releases this lock after a crash; do not invent stale-lock timeouts.
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / '.lock'
        if lock.is_symlink() or self.path.is_symlink():
            raise ValueError('Index or lock is a symlink')
        with lock.open('a+b') as handle:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                if os.name == 'nt':
                    handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def initialize(self, role, goal):
        if role not in ROLES or not goal.strip():
            raise ValueError('Known runtime role and non-empty goal required')
        with self.locked():
            if self.path.exists():
                raise ValueError('Workspace already initialized; resume it')
            (self.root / 'results').mkdir(exist_ok=True)
            state = dict(format_version=1, record_type='workspace_index',
                         project_id=uuid.uuid4().hex, role_ids=[role], goal=goal,
                         revision=1, stage='intake', sources={}, artifacts={}, rules={},
                         tasks={}, feedback=[], events=[], next_action='Inspect authorized inputs', updated_at=now())
            atomic_json(self.path, state)
        return state

    def read(self):
        if self.path.is_symlink():
            raise ValueError('Index is a symlink')
        state = json.loads(self.path.read_text(encoding='utf-8'))
        if state.get('format_version') != 1 or state.get('record_type') != 'workspace_index':
            raise ValueError('Unsupported index version; keep original and migrate explicitly')
        return state

    def _write(self, state):
        state['revision'] += 1; state['updated_at'] = now()
        atomic_json(self.path, state)

    def inspect(self):
        state = self.read()
        for name, artifact in state['artifacts'].items():
            refs = artifact['source_refs']
            sources = [state['sources'].get(ref) for ref in refs]
            if any(s and s['status'] == 'revoked' for s in sources):
                artifact['status'] = 'restricted'
            elif any(not s or not self._current(s) for s in sources):
                artifact['status'] = 'stale'
            target = self.root / 'results' / name
            if not target.is_file():
                artifact['disk_state'] = 'missing'
            elif any(p.is_symlink() for p in [target, *target.parents]):
                artifact['disk_state'] = 'unsafe_link'
            else:
                artifact['disk_state'] = 'current' if sha256(target) == artifact['sha256'] else 'modified_by_user'
            if artifact['status'] == 'current' and artifact['disk_state'] != 'current':
                artifact['status'] = artifact['disk_state']
        for rule in state['rules'].values():
            rule['effective_status'] = rule['status']
            if any(ref not in state['sources'] or not self._current(state['sources'][ref]) for ref in rule['source_refs']):
                rule['effective_status'] = 'needs_review'
        # Index may contain sensitive extracted text. Status only needs metadata.
        for source in state['sources'].values():
            source['current_on_disk'] = self._current(source)
            source.pop('text', None)
        return state

    def update(self, fields, expected_revision):
        allowed = {'stage', 'next_action', 'goal', 'tasks'}
        if set(fields) - allowed or ('stage' in fields and fields['stage'] not in STAGES):
            raise ValueError('Invalid update or stage')
        with self.locked():
            state = self.read()
            if state['revision'] != expected_revision:
                raise ValueError('Revision conflict; reread and merge user changes')
            state.update(fields); self._write(state)
        return state

    def _invalidate(self, state, refs, status):
        for artifact in state['artifacts'].values():
            if set(artifact['source_refs']) & set(refs):
                artifact['status'] = status
        for rule in state['rules'].values():
            if set(rule['source_refs']) & set(refs):
                rule['status'] = 'needs_review'

    def ingest(self, root):
        original = Path(root).absolute()
        if original.is_symlink():
            raise ValueError('Source root must not be a symlink')
        root = original.resolve()
        previous = self.read()
        # Bind case aliases of an existing directory to its established scope.
        for source in previous['sources'].values():
            try:
                if root.samefile(source['root']):
                    root = Path(source['root']); break
            except OSError:
                pass
        denied = {s['identity']: s for s in previous['sources'].values() if s['status'] == 'revoked'}
        denied_paths = [Path(s['root']) / s['path'] for s in denied.values()]
        rows = scan(root, exclude=[self.root, *denied_paths])
        for source in denied.values():
            if Path(source['root']) == root:
                rows.append(dict(manifest_item_id=source['manifest_item_id'], path=source['path'],
                                 sha256=None, bytes=None, status='revoked'))
        # Read before locking; verify hashes again before admitting an extraction.
        prepared = []
        for row in rows:
            item = dict(row, root=str(root), observed_at=now())
            if row['status'] == 'ready':
                file = root / row['path']
                item['text'] = file.read_text(encoding='utf-8-sig')
                if sha256(file) != row['sha256']:
                    item.pop('text'); item['status'] = 'changed_during_read'
            prepared.append(item)
        with self.locked():
            state = self.read()
            for item in prepared:
                identity = hashlib.sha256((str(root) + '/' + item['path']).encode()).hexdigest()[:24]
                ref = identity + ':' + str(item['sha256'])
                for old_ref, old in state['sources'].items():
                    if old['identity'] == identity and old_ref != ref and old['status'] != 'revoked':
                        old['status'] = 'superseded'
                        self._invalidate(state, [old_ref], 'stale')
                # Revoked permission is never reinstated by an import.
                if identity in denied or any(s['identity'] == identity and s['status'] == 'revoked'
                                            for s in state['sources'].values()):
                    continue
                item['identity'] = identity; item['source_ref'] = ref
                state['sources'][ref] = item
            state['events'].append({'kind': 'ingest', 'count': len(rows), 'at': now()})
            self._write(state)
        return rows

    def _current(self, source):
        p = Path(source['root']) / source['path']
        try:
            if any(x.is_symlink() for x in [p, *p.parents]):
                return False
            return source['status'] == 'ready' and sha256(p) == source['sha256']
        except OSError:
            return False

    def search(self, query, limit=20):
        terms = query.casefold().split()
        if not terms:
            raise ValueError('Non-empty query required')
        hits = []
        for ref, source in self.read()['sources'].items():
            if not self._current(source):
                continue
            for number, line in enumerate(source.get('text', '').splitlines(), 1):
                if all(t in line.casefold() for t in terms):
                    hits.append(dict(source_ref=ref, path=source['path'], sha256=source['sha256'],
                                     line=number, quote=line))
                    if len(hits) >= limit:
                        return hits
        return hits

    def revoke(self, source_ref):
        with self.locked():
            state = self.read(); identity = state['sources'][source_ref]['identity']
            affected = []
            for ref, source in state['sources'].items():
                if source['identity'] == identity:
                    source['status'] = 'revoked'; source.pop('text', None); affected.append(ref)
            self._invalidate(state, affected, 'restricted'); self._write(state)

    def save_artifact(self, name, text, source_refs=(), expected_hash=None):
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0].casefold() == '.history':
            raise ValueError('Relative result filename required')
        name = rel.as_posix()
        target = self.root / 'results' / rel
        if any(p.is_symlink() for p in [target, *target.parents]):
            raise ValueError('Result path contains a symlink')
        with self.locked():
            state = self.read()
            if target.exists():
                for known_name in state['artifacts']:
                    known = self.root / 'results' / known_name
                    if known.exists() and known.samefile(target):
                        name = known_name; target = known; break
            for ref in source_refs:
                if ref not in state['sources'] or not self._current(state['sources'][ref]):
                    raise ValueError('Source missing, stale, unsupported or revoked')
            if target.exists() and (expected_hash is None or sha256(target) != expected_hash):
                raise ValueError('Existing result: reread and pass current expected_hash to replace')
            old = state['artifacts'].get(name)
            history = list(old.get('history', [])) if old else []
            if target.exists():
                archive = self.root / 'results' / '.history'
                if archive.is_symlink():
                    raise ValueError('History directory is a symlink')
                archive.mkdir(exist_ok=True)
                snapshot = archive / (uuid.uuid4().hex + '.txt')
                snapshot.write_bytes(target.read_bytes())
                prior = {k:v for k,v in (old or {}).items() if k != 'history'}
                prior.update(snapshot=str(snapshot.relative_to(self.root)), sha256=sha256(snapshot))
                history.append(prior)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name('.' + target.name + '.' + uuid.uuid4().hex)
            temp.write_text(text, encoding='utf-8'); os.replace(temp, target)
            state['artifacts'][name] = dict(sha256=sha256(target), source_refs=list(source_refs),
                                            status='current', updated_at=now(), history=history)
            self._write(state)
        return str(target)

    def put_rule(self, rule_id, text, status='candidate', source_refs=(), owner=None, scope=None, approval_ref=None):
        if status not in ['candidate', 'active', 'needs_review', 'retired']:
            raise ValueError('Unknown rule status')
        if status == 'active' and not all([owner, scope, approval_ref, source_refs]):
            raise ValueError('Activation requires owner, scope, real approval reference and sources')
        with self.locked():
            state = self.read()
            for ref in source_refs:
                if ref not in state['sources'] or not self._current(state['sources'][ref]):
                    raise ValueError('Rule source is not current')
            old = state['rules'].get(rule_id)
            history = (old.get('history', []) + [{k:v for k,v in old.items() if k!='history'}]) if old else []
            state['rules'][rule_id] = dict(text=text, status=status, source_refs=list(source_refs),
                                          owner=owner, scope=scope, approval_ref=approval_ref,
                                          version=(old['version']+1 if old else 1), history=history)
            self._write(state)

    def feedback(self, issue, layer, affected):
        if layer not in ['source','extraction','retrieval','rule','calculation','answer','execution','unknown']:
            raise ValueError('Unknown repair layer')
        with self.locked():
            state=self.read();state['feedback'].append(dict(issue=issue, layer=layer, affected=affected,
                                                          status='open', at=now()));self._write(state)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['init','ingest','status','search','revoke','save','feedback','update','rule'])
    p.add_argument('--workspace', required=True); p.add_argument('--role'); p.add_argument('--goal')
    p.add_argument('--root'); p.add_argument('--query'); p.add_argument('--ref'); p.add_argument('--name')
    p.add_argument('--input'); p.add_argument('--expected-hash'); p.add_argument('--revision', type=int)
    p.add_argument('--issue'); p.add_argument('--layer', default='unknown')
    a=p.parse_args();w=Workspace(a.workspace)
    try:
        if a.command=='init':result=w.initialize(a.role or '',a.goal or '')
        elif a.command=='ingest':result=w.ingest(a.root)
        elif a.command=='status':result=w.inspect()
        elif a.command=='search':result=w.search(a.query or '')
        elif a.command=='revoke':w.revoke(a.ref);result={'revoked':a.ref}
        elif a.command=='save':result=w.save_artifact(a.name,Path(a.input).read_text(),[a.ref] if a.ref else [],a.expected_hash)
        elif a.command=='feedback':w.feedback(a.issue,a.layer,[a.ref] if a.ref else []);result={'recorded':True}
        elif a.command=='rule':
            data=json.loads(Path(a.input).read_text());w.put_rule(**data);result={'recorded':True}
        else:result=w.update(json.loads(Path(a.input).read_text()),a.revision)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        p.exit(2,str(error)+'\n')


if __name__=='__main__':main()
