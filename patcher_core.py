"""UFC 6 Xbox Icons: local, asset-free patch generation and reversible writes.

Copyright (c) 2026 UFC6 Xbox Icons contributors. MIT licensed; see LICENSE.
Only Python's standard library is required. No game assets are distributed.
"""
from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import zipfile
import zlib

BACKUP_NAME = '.ufc6-xbox-icons-backup.zip'
PROFILE_NAME = 'PPSA23566-01.006.000.json'
MAX_RANGE = 8 * 1024 * 1024


class PatchError(Exception):
    """An actionable validation or installation error."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check(condition, message):
    if not condition:
        raise PatchError(message)


def load_profile(directory):
    path = Path(directory) / 'profiles' / PROFILE_NAME
    raw = path.read_bytes()
    profile = json.loads(raw)
    check(profile.get('schema') == 1, 'Unsupported patch profile.')
    check(len(profile['entries']) == 430, 'Incomplete patch profile.')
    ids = set()
    spans = {}
    for entry in profile['entries']:
        check(entry['id'] not in ids, 'Duplicate operation in profile.')
        ids.add(entry['id'])
        check(0 < entry['length'] <= MAX_RANGE and entry['offset'] >= 0,
              'Invalid operation range in profile.')
        spans.setdefault(entry['path'], []).append(entry)
    for entries in spans.values():
        entries.sort(key=lambda e: e['offset'])
        for a, b in zip(entries, entries[1:]):
            check(a['offset'] + a['length'] <= b['offset'], 'Overlapping patch ranges.')
    profile['_digest'] = sha256(raw)
    return profile


def inside(root, relative):
    rel = Path(relative)
    check(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe path in patch data.')
    result = (root / rel).resolve()
    check(result.is_relative_to(root), 'A game path links outside the selected folder.')
    return result


def validate_game(root, profile):
    root = Path(root).expanduser().resolve()
    try:
        metadata = json.loads(inside(root, 'sce_sys/param.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise PatchError('Choose the extracted game folder containing sce_sys/param.json and Data.') from exc
    check(metadata.get('titleId') == profile['title_id'],
          'Unsupported title. This release supports PPSA23566 only.')
    check(metadata.get('contentVersion') == profile['content_version'],
          'Unsupported version. This release supports 01.006.000 only.')
    return root


def game_running():
    """Avoid modifying archives while a UFC 6 engine is running on Windows."""
    if os.name != 'nt':
        return False
    from ctypes import wintypes as w
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', ctypes.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
                    ('exe', w.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    check(handle != ctypes.c_void_p(-1).value, 'Cannot check whether the game is running.')
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        ok = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while ok:
            if entry.exe.casefold() in ('ufc 6.exe', 'kyty_emulator.exe', 'ufc 6 parsec.exe'):
                return True
            ok = kernel.Process32NextW(handle, ctypes.byref(entry))
        return False
    finally:
        kernel.CloseHandle(handle)


def open_target(path, writable):
    if os.name != 'nt':
        return path.open('r+b' if writable else 'rb')
    # Deny concurrent writers for the entire validate/write/verify transaction.
    import msvcrt
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                  w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    access = 0x80000000 | (0x40000000 if writable else 0)
    handle = kernel.CreateFileW(str(path), access, 1 if writable else 3, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), f'Cannot open {path.name}. Close the game and check folder permissions.')
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if writable else os.O_RDONLY))
    except Exception:
        kernel.CloseHandle(handle)
        raise
    return os.fdopen(fd, 'r+b' if writable else 'rb')


class GameFiles:
    def __init__(self, root, paths, writable):
        self.root = root
        self.paths = sorted(set(paths))
        self.writable = writable
        self.handles = {}
        self.stack = contextlib.ExitStack()

    def __enter__(self):
        try:
            for relative in self.paths:
                self.handles[relative] = self.stack.enter_context(open_target(inside(self.root, relative), self.writable))
            return self
        except Exception:
            self.stack.close()
            raise

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def read(self, ref):
        check(0 < ref['length'] <= MAX_RANGE and ref['offset'] >= 0, 'Invalid read range.')
        f = self.handles[ref['path']]
        check(ref['offset'] + ref['length'] <= os.fstat(f.fileno()).st_size,
              f"Archive is truncated: {ref['path']}")
        f.seek(ref['offset'])
        data = f.read(ref['length'])
        check(len(data) == ref['length'], 'Short archive read.')
        return data

    def write(self, entry, data):
        check(self.writable and len(data) == entry['length'], 'Invalid write range.')
        f = self.handles[entry['path']]
        f.seek(entry['offset'])
        check(f.write(data) == len(data), 'Short archive write.')

    def flush(self):
        for f in self.handles.values():
            f.flush()
            if self.writable:
                os.fsync(f.fileno())


def unframe(data):
    plain = bytearray()
    frames = []
    pos = 0
    while pos < len(data):
        check(pos + 8 <= len(data), 'Invalid CAS framing.')
        size = ((data[pos + 5] & 15) << 16) | int.from_bytes(data[pos + 6:pos + 8], 'big')
        expected = int.from_bytes(data[pos:pos + 4], 'big') & 0xffffff
        check(data[pos + 4] == 0 and size == expected and pos + 8 + size <= len(data),
              'Unsupported CAS compression in UI library.')
        frames.append((pos + 8, len(plain), size))
        plain.extend(data[pos + 8:pos + 8 + size])
        pos += size + 8
    return bytes(plain), frames


def decode_swf(data):
    check(len(data) >= 12 and data[:3] in (b'CWS', b'FWS'), 'Unsupported UI library format.')
    length = struct.unpack_from('<I', data, 4)[0]
    check(12 <= length <= 8 * 1024 * 1024, 'Invalid UI library size.')
    if data[:3] == b'CWS':
        decoder = zlib.decompressobj()
        body = decoder.decompress(data[8:], length - 7)
        check(decoder.eof and len(body) == length - 8, 'Invalid compressed UI library.')
        plain = data[:8] + body
    else:
        plain = data
    check(len(plain) == length, 'UI library length mismatch.')
    return plain


def swf_tags(data):
    pos = 8 + (5 + 4 * (data[8] >> 3) + 7) // 8 + 4
    while pos + 2 <= len(data):
        word = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        kind, size = word >> 6, word & 63
        if size == 63:
            check(pos + 4 <= len(data), 'Truncated Flash tag.')
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
        check(pos + size <= len(data), 'Invalid Flash tag size.')
        yield kind, pos, size
        pos += size
        if kind == 0:
            break


def swf_symbols(data):
    symbols = []
    for kind, pos, size in swf_tags(data):
        if kind != 76:
            continue
        end = pos + size
        check(pos + 2 <= end, 'Invalid symbol table.')
        count = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        for _ in range(count):
            check(pos + 2 <= end, 'Truncated symbol table.')
            character = struct.unpack_from('<H', data, pos)[0]
            offset = pos
            pos += 2
            stop = data.find(b'\0', pos, end)
            check(stop >= pos, 'Invalid symbol name.')
            symbols.append((data[pos:stop].decode('utf-8'), character, offset))
            pos = stop + 1
        check(pos == end, 'Unexpected symbol table bytes.')
    return symbols


def patch_flash(original, operation):
    payload, frames = unframe(original)
    before = decode_swf(payload)
    after = bytearray(before)
    symbols = swf_symbols(before)
    names = {name: (character, offset) for name, character, offset in symbols}
    count = 0
    for name, character, offset in symbols:
        if '_ps' not in name:
            continue
        xbox = names.get(name.replace('_ps', '_xb'))
        if xbox is not None:
            struct.pack_into('<H', after, offset, xbox[0])
            struct.pack_into('<H', after, xbox[1], character)
            count += 1
    check(count == operation['pairs'], 'Unexpected controller symbol count.')
    check(sha256(after) == operation['decoded_sha256'], 'UI symbol transformation did not match the supported build.')
    for kind, pos, size in swf_tags(before):
        if kind != 76:
            check(before[pos:pos + size] == after[pos:pos + size], 'Unexpected ActionScript/graphics change.')
    rebuilt = payload[:8] + zlib.compress(bytes(after[8:]), 9)
    check(len(rebuilt) <= len(payload), 'This zlib build cannot fit the patched UI into its original archive range.')
    rebuilt += b'\0' * (len(payload) - len(rebuilt))
    check(decode_swf(rebuilt) == after, 'Recompressed UI failed verification.')
    result = bytearray(original)
    for stored, plain, length in frames:
        result[stored:stored + length] = rebuilt[plain:plain + length]
    check(unframe(result)[0] == rebuilt, 'Reframed UI failed verification.')
    return bytes(result)


def paths_for(profile):
    paths = {e['path'] for e in profile['entries']}
    paths.update(e['operation']['source']['path'] for e in profile['entries'] if 'source' in e['operation'])
    return paths


def make_plan(files, profile, log=lambda text: None):
    originals = {}
    known_installed = 0
    for e in profile['entries']:
        data = files.read(e)
        digest = sha256(data)
        if digest == e['known_installed_sha256']:
            known_installed += 1
        else:
            check(digest == e['original_sha256'],
                  f"Unsupported or modified game data: {e['path']} at offset {e['offset']}. No changes were made.")
        originals[e['id']] = data
    if known_installed:
        raise PatchError('An earlier copy of this mod is present without this installer\'s backup. '
                         'Restore it with the previous installer first, then install this release.')
    results = {}
    source_cache = {}
    def source(ref):
        key = (ref['path'], ref['offset'], ref['length'])
        if key not in source_cache:
            data = files.read(ref)
            check(sha256(data) == ref['sha256'], 'An Xbox source asset differs from the supported game build.')
            source_cache[key] = data
        return source_cache[key]
    def result(entry_id):
        if entry_id in results:
            return results[entry_id]
        e = next(x for x in profile['entries'] if x['id'] == entry_id)
        op = e['operation']
        kind = op['type']
        old = originals[entry_id]
        if kind == 'copy':
            new = source(op['source'])
        elif kind == 'dimensions':
            src = source(op['source'])
            new = old[:30] + src[30:34] + old[34:]
        elif kind == 'redirect':
            source(op['source'])
            new = struct.pack('>II', op['source']['offset'], op['source']['length'])
        elif kind == 'sha1_source':
            new = hashlib.sha1(source(op['source'])).digest()
        elif kind == 'sha1_result':
            new = hashlib.sha1(result(op['entry'])).digest()
        elif kind == 'flash':
            log(f"Building {op['pairs']} Flash button mappings from local assets...")
            new = patch_flash(old, op)
        else:
            raise PatchError('Unknown patch operation.')
        check(len(new) == e['length'], 'Generated patch changed an archive range size.')
        # Flash compression can vary between zlib versions. Its decompressed
        # result is checked above against the exact verified transformation.
        if kind != 'flash':
            check(sha256(new) == e['known_installed_sha256'], 'Generated artwork failed verification.')
        results[entry_id] = new
        return new
    return [(e, originals[e['id']], result(e['id'])) for e in profile['entries']]


def create_backup(root, profile, plan):
    target = inside(root, BACKUP_NAME)
    check(not target.exists(), 'A local backup already exists. Use Status or Restore first.')
    temp = inside(root, BACKUP_NAME + '.new')
    check(not temp.exists(), 'An unfinished backup exists. Keep it and inspect the folder before continuing.')
    records = [dict(id=e['id'],path=e['path'],offset=e['offset'],length=e['length'],
                    original_sha256=sha256(old),installed_sha256=sha256(new)) for e,old,new in plan]
    manifest = dict(schema=1,profile_digest=profile['_digest'],title_id=profile['title_id'],
                    content_version=profile['content_version'],entries=records)
    try:
        with temp.open('xb') as stream:
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
                for e, old, _ in plan:
                    archive.writestr(f"ranges/{e['id']:04d}.bin", old)
            stream.flush()
            os.fsync(stream.fileno())
        # Verify the complete backup before changing any game data.
        read_backup(temp, profile)
        os.replace(temp, target)
    except Exception:
        # A failed backup is kept for diagnosis; no archives have changed yet.
        raise
    return target


def read_backup(path, profile):
    check(path.stat().st_size <= 20 * 1024 * 1024, 'Local backup is unexpectedly large.')
    with zipfile.ZipFile(path) as archive:
        check(len(archive.namelist()) == len(set(archive.namelist())) == 431,
              'Local backup has unexpected entries.')
        info = archive.getinfo('manifest.json')
        check(info.file_size < 256 * 1024, 'Local backup manifest is too large.')
        manifest = json.loads(archive.read('manifest.json'))
        check(manifest.get('schema') == 1 and manifest.get('profile_digest') == profile['_digest'],
              'Local backup belongs to another patch profile.')
        check(len(manifest['entries']) == len(profile['entries']), 'Incomplete local backup.')
        restored = []
        for record,e in zip(manifest['entries'],profile['entries']):
            check(all(record.get(k) == e[k] for k in ('id','path','offset','length','original_sha256')),
                  'Local backup metadata does not match the supported profile.')
            name = f"ranges/{e['id']:04d}.bin"
            check(archive.getinfo(name).file_size == e['length'], 'Invalid backup range length.')
            original = archive.read(name)
            check(sha256(original) == e['original_sha256'], 'Local backup integrity check failed.')
            restored.append((e, original, record['installed_sha256']))
        return restored


def verify_backup_state(files, backup):
    states = []
    for entry, old, installed_hash in backup:
        actual = files.read(entry)
        digest = sha256(actual)
        check(digest in (entry['original_sha256'], installed_hash),
              f"Game data changed after installation: {entry['path']} at {entry['offset']}. Nothing was written.")
        states.append((entry, old, actual, digest == installed_hash))
    return states


def transaction(files, writes):
    attempted = []
    try:
        for e, before, after in writes:
            if before == after:
                continue
            attempted.append((e, before))
            files.write(e, after)
        files.flush()
        for e, _, after in writes:
            check(files.read(e) == after, 'Read-back verification failed.')
    except BaseException as failure:
        try:
            for e, before in reversed(attempted):
                files.write(e, before)
            files.flush()
            for e, before in attempted:
                check(files.read(e) == before, 'Rollback verification failed.')
        except BaseException as rollback:
            raise PatchError('Write failed and rollback was incomplete. Keep the local backup; use Restore after resolving the disk error.') from rollback
        raise PatchError(f'Write failed; all attempted writes were restored. {failure}') from failure


def run(action, root, profile, log=lambda text: None):
    check(action in ('status','install','restore'), 'Unknown action.')
    root = validate_game(root, profile)
    if action != 'status':
        check(not game_running(), 'Close UFC 6 before installing or restoring the mod.')
    backup_path = inside(root, BACKUP_NAME)
    with GameFiles(root, paths_for(profile), action != 'status') as files:
        if backup_path.exists():
            backup = read_backup(backup_path, profile)
            states = verify_backup_state(files, backup)
            installed = sum(s[3] for s in states)
            if action == 'status':
                return f'{installed}/430 ranges installed. Verified local restore backup available.'
            if action == 'restore':
                transaction(files, [(e, actual, old) for e,old,actual,_ in states])
                return 'Restored and verified all 430 original ranges. Backup retained locally.'
            if installed == len(states):
                return 'Already installed; all 430 ranges and the local backup verified.'
            # Rebuild from the verified clean originals without touching files:
            # a view substitutes backed-up ranges for the current target spans.
            original_map={(e['path'],e['offset'],e['length']):old for e,old,_,_ in states}
            class OriginalView:
                def read(self, ref):
                    return original_map.get((ref['path'],ref['offset'],ref['length']), None) or files.read(ref)
            plan = make_plan(OriginalView(), profile, log)
            for (_,_,new),(_,_,installed_hash) in zip(plan,backup):
                check(sha256(new) == installed_hash, 'This runtime would produce a different patch from the saved backup. Restore, move the backup aside, and install again.')
            actuals={e['id']:actual for e,_,actual,_ in states}
            transaction(files, [(e,actuals[e['id']],new) for e,_,new in plan])
            return 'Installed and verified all 430 ranges. Restart the game to load Xbox icons.'
        check(action != 'restore', 'No local restore backup found. Nothing was changed.')
        log('Verifying game ranges and local Xbox source assets...')
        plan = make_plan(files, profile, log)
        if action == 'status':
            return 'Compatible original build verified. Ready to install.'
        create_backup(root, profile, plan)
        log('Original ranges backed up and verified. Installing...')
        transaction(files, plan)
        return 'Installed and verified all 430 ranges. Restart the game to load Xbox icons.'
