"""Reversible Xbox/keyboard/original mode switching with a durable write journal."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import zipfile
import zlib

import patcher_core as core
from keyboard_bindings import Bindings, PAD_DEFAULTS, SOURCE_TO_CONTROL, defaults, from_controls

BACKUP='.ufc6-input-icons-backup.zip'
STATE='.ufc6-input-icons-state.json'
PROFILE='PPSA23566-01.006.000-keyboard.json'

_TOKENS = {
    'Cross': 'digital_one',
    'Circle': 'digital_two',
    'Triangle': 'digital_three',
    'Square': 'digital_four',
    'L1': 'left_bumper',
    'R1': 'right_bumper',
    'L2': 'left_trigger',
    'R2': 'right_trigger',
    'L3': 'las_c',
    'R3': 'ras_c',
    'TouchPad': 'select',
    'Options': 'start',
    'Guide': 'guide',
    'Up': 'dpad_u',
    'Down': 'dpad_d',
    'Left': 'dpad_l',
    'Right': 'dpad_r',
}
_TOKEN_TO_CTRL = {v: k for k, v in _TOKENS.items()}


def load_profile(directory):
    directory=Path(directory)
    base=core.load_profile(directory)
    raw=(directory/'profiles'/PROFILE).read_bytes();keyboard=json.loads(raw)
    core.check(keyboard.get('schema')==1 and keyboard.get('base_digest')==base['_digest'],
               'Keyboard profile does not match the bundled Xbox profile.')
    entries=[{k:e[k] for k in ('id','path','offset','length','original_sha256')} for e in base['entries']]
    entries+=keyboard['extra_entries']
    core.check(len(entries)==keyboard.get('total_ranges') and 430<len(entries)<=2048,'Incomplete keyboard patch profile.')
    ids=set();spans={}
    for e in entries:
        core.check(e['id'] not in ids and 0<e['length']<=core.MAX_RANGE and e['offset']>=0,'Invalid keyboard profile range.')
        ids.add(e['id']);spans.setdefault(e['path'],[]).append(e)
    for records in spans.values():
        records.sort(key=lambda e:e['offset'])
        for a,b in zip(records,records[1:]):core.check(a['offset']+a['length']<=b['offset'],'Overlapping keyboard patch ranges.')
    ops={op['id']:op for op in keyboard['operations']}
    core.check(len(ops)==len(keyboard['operations']) and set(ops)<=ids,'Invalid keyboard operations.')
    return dict(base=base,keyboard=keyboard,entries=entries,operations=ops,
                digest=core.sha256((base['_digest']+'\n').encode()+raw))


def paths_for(profile):
    return core.paths_for(profile['base'])|{e['path'] for e in profile['entries']}


class OriginalView:
    def __init__(self,files,entries,originals):
        self.files=files
        self.originals={(e['path'],e['offset'],e['length']):originals[e['id']] for e in entries}
    def read(self,ref):
        key=(ref['path'],ref['offset'],ref['length'])
        if key in self.originals:return self.originals[key]
        return self.files.read(ref)


def _slot_key(name, ctrl):
    tok = _TOKENS[ctrl]
    plat = 'ps' if '/ps/' in name else 'xbox'
    s = name.replace(f'/{plat}/', '/{plat}/')
    s = s.replace('_hold_skip_widget', '_hold').replace('_precanned_message', '')
    if 'left_on_trigger' in s:
        s = s.replace('left_on_trigger', '{tok}_on')
    elif 'right_on_trigger' in s:
        s = s.replace('right_on_trigger', '{tok}_on')
    else:
        s = s.replace(tok, '{tok}')
    return plat, s


def _patch_controller_flash(original, style, pad_map):
    payload, frames = core.unframe(original)
    before = core.decode_swf(payload)
    after = bytearray(before)
    symbols = core.swf_symbols(before)
    names = {name: (character, offset) for name, character, offset in symbols}
    target_plat = '_xb' if style == 'xbox' else '_ps'
    for name, character, offset in symbols:
        if '_ps' not in name:
            continue
        matched_tok = None
        for tok in sorted(_TOKEN_TO_CTRL, key=len, reverse=True):
            if f'_{tok}_' in name:
                matched_tok = tok
                break
        target_name = None
        if matched_tok is not None:
            ctrl = _TOKEN_TO_CTRL[matched_tok]
            src_btn = pad_map.get(ctrl)
            target_ctrl = SOURCE_TO_CONTROL.get(src_btn, ctrl) if src_btn else ctrl
            target_tok = _TOKENS.get(target_ctrl, matched_tok)
            candidate = name.replace(f'_{matched_tok}_', f'_{target_tok}_').replace('_ps', target_plat)
            if candidate in names:
                target_name = candidate
        if target_name is None and style == 'xbox':
            candidate = name.replace('_ps', '_xb')
            if candidate in names:
                target_name = candidate
        if target_name is not None and target_name in names:
            struct.pack_into('<H', after, offset, names[target_name][0])
    rebuilt = payload[:8] + zlib.compress(bytes(after[8:]), 9)
    core.check(len(rebuilt) <= len(payload), 'Patched controller UI exceeds archive allocation.')
    rebuilt += b'\0' * (len(payload) - len(rebuilt))
    core.check(core.decode_swf(rebuilt) == after, 'Recompressed controller UI failed verification.')
    result = bytearray(original)
    for stored, plain, length in frames:
        result[stored:stored + length] = rebuilt[plain:plain + length]
    return bytes(result)


def _apply_controller_remap(result, originals, profile, style, pad_map, log):
    log(f'Applying custom {style} controller button mappings...')
    inv = profile['keyboard'].get('texture_inventory', [])
    entries_by_id = {e['id']: e for e in profile['entries']}
    slot_map = {}
    for item in inv:
        ctrls = item['descriptor']['controls']
        if len(ctrls) == 1 and ctrls[0] in _TOKENS:
            ctrl = ctrls[0]
            plat, s = _slot_key(item['name'], ctrl)
            slot_map[(plat, s, ctrl)] = item

    plat = 'xbox' if style == 'xbox' else 'ps'
    modified_entries = set()
    for item in inv:
        if '/ps/' not in item['name'] or item.get('borrowed'):
            continue
        ctrls = item['descriptor']['controls']
        if len(ctrls) != 1 or ctrls[0] not in _TOKENS:
            continue
        ctrl = ctrls[0]
        src_btn = pad_map.get(ctrl)
        target_ctrl = SOURCE_TO_CONTROL.get(src_btn, ctrl) if src_btn else ctrl
        if target_ctrl == ctrl:
            continue
        _, s = _slot_key(item['name'], ctrl)
        dst_ref = slot_map.get((plat, s, ctrl))
        src_item = slot_map.get((plat, s, target_ctrl))
        if dst_ref and src_item and not src_item.get('borrowed'):
            e_dst = entries_by_id[item['entry']]
            e_src = entries_by_id[src_item['entry']]
            if (dst_ref['width'], dst_ref['height'], e_dst['length']) == (src_item['width'], src_item['height'], e_src['length']):
                result[item['entry']] = originals[src_item['entry']]
                modified_entries.add(item['entry'])

    for op in profile['operations'].values():
        if op['type'] == 'keyboard_sha1' and op['entry'] in modified_entries:
            result[op['id']] = hashlib.sha1(result[op['entry']]).digest()
        elif op['type'] == 'keyboard_flash':
            result[op['id']] = _patch_controller_flash(originals[op['id']], style, pad_map)
    return result


def make_plan(files,profile,originals,style,bindings,log=lambda s:None):
    core.check(style in ('keyboard','xbox','playstation'),'Unknown icon style.')
    bindings = bindings or defaults()
    custom_pad = bindings.has_custom_pad()
    if style=='playstation' and not custom_pad:
        return dict(originals)
    view=OriginalView(files,profile['entries'],originals)
    xbox={e['id']:new for e,old,new in core.make_plan(view,profile['base'],log if style=='xbox' else lambda s:None)}
    result=dict(originals)
    if style in ('xbox','playstation'):
        if style=='xbox':
            result.update(xbox)
        if custom_pad:
            _apply_controller_remap(result, originals, profile, style, bindings.pad_controls(), log)
        return result
    from keyboard_art import texture
    from keyboard_flash import patch as flash
    bindings.validate()
    log('Preparing keyboard artwork from the selected bindings...')
    ops=profile['operations']
    def build(i):
        op=ops.get(i)
        if op is None:return result[i]
        kind=op['type'];old=originals[i]
        if kind=='keyboard_pixels':value=texture(old,op['texture'],bindings)
        elif kind=='keyboard_sha1':value=hashlib.sha1(build(op['entry'])).digest()
        elif kind=='keyboard_flash':
            log('Preparing menu button artwork...')
            value=flash(old,bindings,op['bitmaps'])
        elif kind=='xbox':value=xbox[i]
        else:raise core.PatchError('Unknown keyboard transformation.')
        core.check(len(value)==len(old),'Keyboard transformation changed the archive allocation.')
        result[i]=value
        built.add(i)
        return value
    built=set()
    # Cache dependencies such as manifest hashes referring to texture ranges.
    original_build=build
    def cached(i):return result[i] if i in built else original_build(i)
    build=cached
    for i in ops:build(i)
    return result


def atomic_json(path,value):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix=path.name+'.',suffix='.tmp',delete=False) as f:
            temporary=Path(f.name);json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temporary,path);temporary=None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def write_backup(path,profile,originals):
    core.check(not path.exists(),'A unified restore backup already exists.')
    temp=path.with_name(path.name+'.new')
    core.check(not temp.exists(),'An unfinished unified backup exists. Keep it aside before retrying.')
    manifest=dict(schema=1,profile_digest=profile['digest'],entries=profile['entries'])
    with temp.open('xb') as f:
        with zipfile.ZipFile(f,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('manifest.json',json.dumps(manifest))
            for e in profile['entries']:z.writestr(f"ranges/{e['id']:04d}.bin",originals[e['id']])
        f.flush();os.fsync(f.fileno())
    read_backup(temp,profile)
    os.replace(temp,path)


def read_backup(path,profile):
    core.check(path.stat().st_size<=24*1024*1024,'Unified restore backup is unexpectedly large.')
    result={}
    with zipfile.ZipFile(path) as z:
        core.check(len(z.namelist())==len(set(z.namelist()))==len(profile['entries'])+1,'Unexpected unified backup contents.')
        core.check(z.getinfo('manifest.json').file_size<=512*1024,'Unified backup manifest is too large.')
        m=json.loads(z.read('manifest.json'))
        core.check(m.get('schema')==1 and m.get('profile_digest')==profile['digest'] and m.get('entries')==profile['entries'],
                   'Unified backup does not match this patcher version. Use the installer that created it.')
        for e in profile['entries']:
            name=f"ranges/{e['id']:04d}.bin"
            core.check(z.getinfo(name).file_size==e['length'],'Wrong original range length in unified backup.')
            data=z.read(name)
            core.check(core.sha256(data)==e['original_sha256'],'Unified restore backup integrity check failed.')
            result[e['id']]=data
    return result


def snapshot(profile,data,mode,bindings=None):
    value=dict(mode=mode,hashes={str(e['id']):core.sha256(data[e['id']]) for e in profile['entries']})
    if bindings is not None:value['bindings']=bindings.digest_data()
    return value


def read_state(path,profile):
    core.check(path.is_file(),'The icon state file is missing. Keep it with the unified backup; no files were changed.')
    core.check(path.stat().st_size<=512*1024,'Icon state file is too large.')
    state=json.loads(path.read_text(encoding='utf-8'))
    core.check(state.get('schema')==1 and state.get('profile_digest')==profile['digest'],'Icon state belongs to another patch profile.')
    expected={str(e['id']) for e in profile['entries']}
    for key in ('current','pending'):
        if key not in state:continue
        v=state[key]
        core.check(isinstance(v,dict) and set(v.get('hashes',{}))==expected,'Incomplete icon state journal.')
        core.check(all(isinstance(h,str) and len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in v['hashes'].values()),'Invalid icon state hash.')
    core.check('current' in state,'No committed icon state.')
    return state


def verify_state(files,profile,state):
    actual={};hashes={}
    for e in profile['entries']:
        data=files.read(e);digest=core.sha256(data);i=str(e['id'])
        known={e['original_sha256'],state['current']['hashes'][i]}
        if 'pending' in state:known.add(state['pending']['hashes'][i])
        core.check(digest in known,f"Game data changed outside this installer: {e['path']} at {e['offset']}. Nothing was written.")
        actual[e['id']]=data;hashes[i]=digest
    if 'pending' in state and hashes==state['pending']['hashes']:label=state['pending']['mode']
    elif hashes==state['current']['hashes']:label=state['current']['mode']
    elif all(hashes[str(e['id'])]==e['original_sha256'] for e in profile['entries']):label='playstation'
    else:label='interrupted install (recoverable)'
    return actual,label


def initial_originals(files,root,profile):
    legacy=root/core.BACKUP_NAME
    legacy_originals={}
    if legacy.exists():
        saved=core.read_backup(legacy,profile['base'])
        core.verify_backup_state(files,saved)
        legacy_originals={e['id']:old for e,old,installed in saved}
    originals={};actual={}
    for e in profile['entries']:
        data=files.read(e);actual[e['id']]=data
        old=legacy_originals.get(e['id'],data)
        core.check(core.sha256(old)==e['original_sha256'],
                   'Unrecognized game modifications without a verified original backup. Restore the previous mod first.')
        originals[e['id']]=old
    return originals,actual


def run(action,root,profile,log=lambda s:None,*,style='xbox',bindings=None):
    core.check(action in ('status','install','restore'),'Unknown input icon action.')
    root=core.validate_game(root,profile['base'])
    if action!='status':core.check(not core.game_running(),'Close UFC 6 before installing or restoring icons.')
    backup_path=core.inside(root,BACKUP);state_path=core.inside(root,STATE)
    with core.GameFiles(root,paths_for(profile),action!='status') as files:
        if backup_path.exists():
            originals=read_backup(backup_path,profile)
            if state_path.exists():state=read_state(state_path,profile)
            else:
                # A power loss after the backup rename but before the first
                # state write leaves only original/verified legacy Xbox data.
                # Recover that narrow case without accepting unknown artwork.
                checked,raw=initial_originals(files,root,profile)
                core.check(checked==originals,'Original recovery data differs from the unified backup.')
                label='playstation' if raw==originals else 'xbox / previous install'
                state=dict(schema=1,profile_digest=profile['digest'],current=snapshot(profile,raw,label))
            actual,current=verify_state(files,profile,state)
            actual_hashes={str(i):core.sha256(data) for i,data in actual.items()}
            if state.get('pending',{}).get('hashes')==actual_hashes:committed=state['pending']
            elif state['current']['hashes']==actual_hashes:committed=state['current']
            else:committed=snapshot(profile,actual,current)
            # Preserve the exact verified pre-write state before replacing an
            # old pending journal. A rollback after a second interrupted job
            # must still recognize the bytes that preceded that second job.
            state=dict(schema=1,profile_digest=profile['digest'],current=committed)
        else:
            originals,actual=initial_originals(files,root,profile)
            current='playstation' if actual==originals else 'xbox / previous install'
            state=dict(schema=1,profile_digest=profile['digest'],current=snapshot(profile,actual,current))
        if action=='status':return f'Current icons: {current}. All {len(profile["entries"])} ranges verified.'
        if action=='restore':
            style='playstation'
            bindings=defaults()
        active_bindings = bindings or defaults()
        desired=make_plan(files,profile,originals,style,active_bindings,log)
        if actual==desired:
            if backup_path.exists():atomic_json(state_path,state)
            return f'{style.capitalize()} icons already installed; all ranges verified.'
        # Compute and verify the full next state before creating a backup or
        # touching any archive. The pending journal survives process loss.
        track_bindings = active_bindings if (style=='keyboard' or active_bindings.has_custom_pad()) else None
        pending=snapshot(profile,desired,style,track_bindings)
        if not backup_path.exists():
            write_backup(backup_path,profile,originals)
            atomic_json(state_path,state)
        state['pending']=pending;atomic_json(state_path,state)
        core.check(not core.game_running(),'Close UFC 6 before applying icons; no game writes were made.')
        writes=[(e,actual[e['id']],desired[e['id']]) for e in profile['entries']]
        log(f'Installing {style} icons with verified originals and rollback support...')
        core.transaction(files,writes)
        state=dict(schema=1,profile_digest=profile['digest'],current=pending)
        atomic_json(state_path,state)
        return f'{style.capitalize()} icons installed and verified. Restart UFC 6. Keep the local backup and state file.'
