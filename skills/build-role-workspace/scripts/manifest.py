"""Inventory authorized local files. Never follow symlinks or execute file content."""
import argparse
import hashlib
import json
from pathlib import Path

TEXT = {'.txt', '.md', '.csv', '.tsv', '.json', '.jsonl'}


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def scan(root, exclude=(), max_bytes=8 * 1024 * 1024):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Source must be an existing non-symlink directory')
    root = root.resolve()
    excluded = [Path(p).resolve() for p in exclude]
    seen, result = {}, []

    def is_excluded(path):
        for blocked in excluded:
            if path.resolve().is_relative_to(blocked):
                return True
            # Filesystem identities handle case aliases on macOS/Windows.
            if blocked.exists():
                for ancestor in [path, *path.parents]:
                    if ancestor == root.parent:
                        break
                    try:
                        if ancestor.samefile(blocked):
                            return True
                    except OSError:
                        pass
        return False

    def visit(directory):
        for path in sorted(directory.iterdir()):
            if path.name.startswith('.') or path.name == '__pycache__':
                continue
            rel = str(path.relative_to(root))
            item = {'manifest_item_id': hashlib.sha256(rel.encode()).hexdigest()[:24],
                    'path': rel, 'sha256': None, 'bytes': None}
            if path.is_symlink():
                item['status'] = 'blocked_symlink'
            elif is_excluded(path):
                continue
            elif path.is_dir():
                visit(path)
                continue
            elif path.is_file():
                try:
                    item['bytes'] = path.stat().st_size
                    item['sha256'] = sha256(path)
                    if item['sha256'] in seen:
                        item.update(status='duplicate', canonical_item_id=seen[item['sha256']])
                    elif path.suffix.lower() not in TEXT:
                        item['status'] = 'requires_host_extraction'
                    elif item['bytes'] > max_bytes:
                        item['status'] = 'size_limit'
                    else:
                        text = path.read_text(encoding='utf-8-sig')
                        item['status'] = 'ready' if text.strip() else 'empty_extraction'
                    seen.setdefault(item['sha256'], item['manifest_item_id'])
                except (OSError, UnicodeError):
                    item['status'] = 'unreadable'
            else:
                item['status'] = 'unsupported_object'
            result.append(item)
    visit(root)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    args = parser.parse_args()
    try:
        print(json.dumps(scan(args.root), ensure_ascii=False, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
