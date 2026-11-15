"""Read-only PORTHEON/Kyty keymap import; never execute a launch script."""
from __future__ import annotations
import configparser
import json
from pathlib import Path
import re
import struct
from dataclasses import dataclass

from patcher_core import PatchError, check

DEFAULTS = dict(Cross='J', Circle='L', Square='K', Triangle='I', L1='Q', R1='E',
               L2='Z', R2='C', L3='Left Shift', R3='Left Ctrl', Options='Return',
               TouchPad='Backspace', TouchPadRight='Tab', Up='Up', Down='Down',
               Left='Left', Right='Right', LeftStickUp='W', LeftStickDown='S',
               LeftStickLeft='A', LeftStickRight='D', RightStickUp='T',
               RightStickDown='G', RightStickLeft='F', RightStickRight='H')
PAD_DEFAULTS = dict(Cross='South', Circle='East', Square='West', Triangle='North',
                    L1='LeftShoulder', R1='RightShoulder', L2='LeftTrigger', R2='RightTrigger',
                    L3='LeftStick', R3='RightStick', Options='Start', TouchPad='Touchpad',
                    Up='DpadUp', Down='DpadDown', Left='DpadLeft', Right='DpadRight')
PAD_SOURCES = (
    'South', 'East', 'West', 'North',
    'LeftShoulder', 'RightShoulder', 'LeftTrigger', 'RightTrigger',
    'LeftStick', 'RightStick', 'Start', 'Touchpad', 'Back', 'Guide', 'Misc1',
    'DpadUp', 'DpadDown', 'DpadLeft', 'DpadRight',
    'LeftPaddle1', 'RightPaddle1', 'LeftPaddle2', 'RightPaddle2',
)
SOURCE_TO_CONTROL = dict(
    South='Cross', East='Circle', West='Square', North='Triangle',
    LeftShoulder='L1', RightShoulder='R1', LeftTrigger='L2', RightTrigger='R2',
    LeftStick='L3', RightStick='R3', Start='Options', Touchpad='TouchPad',
    Back='TouchPad', Guide='Guide', Misc1='TouchPad',
    DpadUp='Up', DpadDown='Down', DpadLeft='Left', DpadRight='Right',
    LeftPaddle1='L1', RightPaddle1='R1', LeftPaddle2='L2', RightPaddle2='R2',
)
PAD_ALIASES = {
    'a': 'South', 'cross': 'South', 'xbox a': 'South', 'a / cross': 'South',
    'b': 'East', 'circle': 'East', 'xbox b': 'East', 'b / circle': 'East',
    'x': 'West', 'square': 'West', 'xbox x': 'West', 'x / square': 'West',
    'y': 'North', 'triangle': 'North', 'xbox y': 'North', 'y / triangle': 'North',
    'lb': 'LeftShoulder', 'l1': 'LeftShoulder', 'lb / l1': 'LeftShoulder',
    'rb': 'RightShoulder', 'r1': 'RightShoulder', 'rb / r1': 'RightShoulder',
    'lt': 'LeftTrigger', 'l2': 'LeftTrigger', 'lt / l2': 'LeftTrigger',
    'rt': 'RightTrigger', 'r2': 'RightTrigger', 'rt / r2': 'RightTrigger',
    'l3': 'LeftStick', 'ls': 'LeftStick', 'left stick': 'LeftStick',
    'r3': 'RightStick', 'rs': 'RightStick', 'right stick': 'RightStick',
    'options': 'Start', 'menu': 'Start', 'start': 'Start',
    'select': 'Back', 'share': 'Back', 'view': 'Back', 'back': 'Back',
    'touchpad': 'Touchpad', 'touch pad': 'Touchpad',
    'up': 'DpadUp', 'dpad up': 'DpadUp', 'd-pad up': 'DpadUp',
    'down': 'DpadDown', 'dpad down': 'DpadDown', 'd-pad down': 'DpadDown',
    'left': 'DpadLeft', 'dpad left': 'DpadLeft', 'd-pad left': 'DpadLeft',
    'right': 'DpadRight', 'dpad right': 'DpadRight', 'd-pad right': 'DpadRight',
}
RESERVED = {'Escape','F1','F2','F7','F8','F11'}
EXTRA = {'SpeakerVolume','VibrationIntensity','TriggerEffectIntensity','GyroToggle','TouchPadMode'}
KEY_NAMES = {'Return','Return2','Escape','Space','Tab','Backspace','CapsLock',
             'Left Shift','Right Shift','Left Ctrl','Right Ctrl','Left Alt','Right Alt',
             'Left GUI','Right GUI','Up','Down','Left','Right','Insert','Delete','Home',
             'End','PageUp','PageDown','Numlock','PrintScreen','ScrollLock','Pause',
             'Application','Menu','Clear','Help','Undo','Cut','Copy','Paste','Find',
             'Mute','VolumeUp','VolumeDown','Select','Execute','Stop','Again'}
KEY_NAMES |= {f'F{i}' for i in range(1,25)}
KEY_NAMES |= {f'Keypad {i}' for i in range(10)}
KEY_NAMES |= {'Keypad '+s for s in ['+','-','*','/','.',',','=','Enter','(',')','Tab','Backspace','Clear','ClearEntry']}
KEY_NAMES |= {'Mouse:'+s for s in ['Left','Middle','Right','X1','X2']}
ALIASES = {'enter':'Return','esc':'Escape','spacebar':'Space','page up':'PageUp',
           'page down':'PageDown','caps lock':'CapsLock','left control':'Left Ctrl',
           'right control':'Right Ctrl','mouse left':'Mouse:Left','mouse right':'Mouse:Right',
           'mouse middle':'Mouse:Middle','leftshift':'Left Shift','leftctrl':'Left Ctrl'}


def key_name(value):
    value=str(value).strip()
    if not value or value.casefold() in ('unbound','none','disabled'):
        return None
    if len(value)==1 and value.isprintable() and value!=';':
        return value.upper() if value.isalpha() else value
    if value.casefold() in ALIASES:return ALIASES[value.casefold()]
    for name in KEY_NAMES:
        if name.casefold()==value.casefold():return name
    raise PatchError(f'Unsupported key name: {value!r}. Use an SDL key name or a mouse button.')


def pad_source_name(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.casefold() in ('unbound', 'none', 'disabled'):
        return None
    low = value.casefold()
    if low in PAD_ALIASES:
        return PAD_ALIASES[low]
    for src in PAD_SOURCES:
        if src.casefold() == low:
            return src
    raise PatchError(f'Unsupported controller button: {value!r}. Choose a standard gamepad button.')


def conflict_name(key):
    return key.replace('Right Shift','Left Shift').replace('Right Ctrl','Left Ctrl').replace('Right Alt','Left Alt').replace('Right GUI','Left GUI')


@dataclass
class Bindings:
    controls: dict
    source: str = 'Kyty built-in defaults'
    custom: bool = False
    extra: tuple = ()

    def validate(self):
        check(set(self.controls)==set(DEFAULTS),'Incomplete keyboard binding table.')
        for control,value in self.controls.items():
            normal=key_name(value) if value is not None else None
            check(normal==value,f'Noncanonical binding for {control}.')
            check(normal not in RESERVED,f'{normal} is reserved by Kyty and cannot bind {control}.')
        active=[conflict_name(v) for v in self.controls.values() if v]
        check(len(active)==len(set(active)),'Two controls share a key. Kyty normalizes left/right modifiers; choose distinct bindings.')
        check(all(isinstance(s,str) and not any(c in s for c in '\r\n\0;') for s in self.extra) and sum(map(len,self.extra))<=32*1024,
              'Invalid additional Kyty input settings.')
        return self

    def pad_controls(self):
        """Return effective controller (Pad:) mapping following Kyty's InputMap rules."""
        custom_pad = False
        source_owner = {}
        for entry in self.extra:
            if entry == 'Pad=Disabled':
                custom_pad = True
                source_owner.clear()
                continue
            if entry.startswith('Pad:') and '=' in entry:
                rest = entry[4:]
                ctrl, src = rest.split('=', 1)
                ctrl, src = ctrl.strip(), src.strip()
                if ctrl in PAD_DEFAULTS and src in PAD_SOURCES:
                    custom_pad = True
                    for k, v in list(source_owner.items()):
                        if v == ctrl:
                            del source_owner[k]
                    source_owner[src] = ctrl
        if not custom_pad:
            return dict(PAD_DEFAULTS)
        result = {k: None for k in PAD_DEFAULTS}
        for src, ctrl in source_owner.items():
            if ctrl in result:
                result[ctrl] = src
        return result

    def has_custom_pad(self):
        return self.pad_controls() != PAD_DEFAULTS

    def argument(self):
        if not self.custom and self.controls==DEFAULTS and not self.extra:return ''
        parts=list(self.extra)
        if self.custom:
            keys=[f'{k}={v}' for k,v in self.controls.items() if v]
            parts+=keys or ['Keyboard=Disabled']
        # Explicit PowerShell literal quoting keeps imported path/key text data,
        # including $, backticks, ampersands and quotes. No command is executed.
        return "--keymap '"+';'.join(parts).replace("'","''")+"'"

    def digest_data(self):
        return dict(controls=self.controls,custom=self.custom,extra=list(self.extra))


def defaults():return Bindings(dict(DEFAULTS))


def from_pad_controls(pad_map, base=None, source='Edited controller bindings'):
    base = base or defaults()
    check(set(pad_map) <= set(PAD_DEFAULTS), 'Unknown controller action in pad settings.')
    normalized = {k: pad_source_name(pad_map.get(k)) for k in PAD_DEFAULTS}
    active = [v for v in normalized.values() if v is not None]
    check(len(active) == len(set(active)), 'Two controller actions share the same physical button; choose distinct buttons.')
    retained = [
        e for e in base.extra
        if e != 'Pad=Disabled' and not (e.startswith('Pad:') and e[4:].split('=', 1)[0].strip() in PAD_DEFAULTS)
    ]
    if normalized != PAD_DEFAULTS:
        pad_entries = [f'Pad:{k}={v}' for k, v in normalized.items() if v is not None]
        retained = retained + (pad_entries or ['Pad=Disabled'])
    return Bindings(dict(base.controls), source, base.custom, tuple(retained)).validate()


def parse_keymap(text,source='Kyty keymap'):
    check(len(text)<=32*1024,'Keymap is too long.')
    values={k:None for k in DEFAULTS};custom=False;extra=[]
    for entry in filter(None,(p.strip() for p in text.split(';'))):
        check('=' in entry,f'Invalid keymap entry: {entry!r}')
        name,value=entry.split('=',1);name=name.strip();value=value.strip()
        if name=='Keyboard':
            check(value=='Disabled','Unknown Keyboard setting.');custom=True;continue
        if name=='Pad' or name.startswith('Pad:') or name in ('MouseSensitivity','TouchParticleSkin','TouchCursorImage'):
            extra.append(entry);continue
        check(name in DEFAULTS or name in EXTRA,f'Unknown Kyty control: {name!r}')
        key=key_name(value)
        check(key is not None,f'Empty key for {name}; omit an unbound control.')
        check(key not in RESERVED,f'{key} is reserved by Kyty.')
        custom=True
        # Kyty's Add replaces both an older binding for this control and an
        # older control occupying the same normalized host key.
        for previous,bound in values.items():
            if bound and conflict_name(bound)==conflict_name(key):values[previous]=None
        if name in values:values[name]=key
        else:extra.append(name+'='+key)
    return Bindings(values if custom else dict(DEFAULTS),source,custom,tuple(extra)).validate()


def from_controls(controls,source='Edited icon bindings',extra=(),custom=None):
    check(set(controls)<=set(DEFAULTS),'Unknown control in keyboard settings.')
    result={k:key_name(controls.get(k)) for k in DEFAULTS}
    return Bindings(result,source,result!=DEFAULTS if custom is None else custom,tuple(extra)).validate()


def read_text(path):
    check(path.stat().st_size<=2*1024*1024,'Settings file is too large.')
    raw=path.read_bytes()
    if raw[:2] in (b'\xff\xfe',b'\xfe\xff'):return raw.decode('utf-16')
    try:return raw.decode('utf-8-sig')
    except UnicodeDecodeError:return raw.decode('cp1252')


def load(path):
    path=Path(path).expanduser().resolve()
    if path.is_dir():
        options=[path/'games/UFC6/UFC6.ini',path/'UFC6.ini']
        matches=[p for p in options if p.is_file()]
        check(len(matches)==1,'Select PORTHEON\'s UFC6.ini, its UFC6 folder, or its installation folder.')
        path=matches[0]
    if path.suffix.lower()=='.exe':return load(path.parent)
    if path.suffix.lower()=='.lnk':
        # Read Shell Link StringData directly. Never hand an imported path or
        # script to a shell, COM object, or executable.
        data=path.read_bytes()
        check(76<=len(data)<=2*1024*1024 and struct.unpack_from('<I',data)[0]==76,'Invalid Windows shortcut.')
        flags=struct.unpack_from('<I',data,20)[0];pos=76
        if flags&1:pos+=2+struct.unpack_from('<H',data,pos)[0]
        if flags&2:pos+=struct.unpack_from('<I',data,pos)[0]
        text=None
        for flag in (4,8,16,32,64):
            if not flags&flag:continue
            count=struct.unpack_from('<H',data,pos)[0];pos+=2
            size=count*(2 if flags&128 else 1)
            check(pos+size<=len(data),'Truncated Windows shortcut.')
            value=data[pos:pos+size].decode('utf-16-le' if flags&128 else 'cp1252');pos+=size
            if flag==32:text=value
        check(text is not None,'This shortcut has no Kyty arguments.')
    else:text=read_text(path)
    if path.suffix.lower()=='.json':
        obj=json.loads(text)
        check(isinstance(obj,dict),'Settings JSON must be an object.')
        if 'controls' in obj:
            extra=obj.get('extra',[])
            check(isinstance(extra,list),'Additional Kyty entries must be a JSON list.')
            result=from_controls(obj['controls'],str(path),extra=extra)
            if 'custom' in obj:
                check(isinstance(obj['custom'],bool),'Invalid custom/default keymap flag.')
                core_defaults=result.controls==DEFAULTS
                check(obj['custom'] or core_defaults,'A non-default map cannot disable the custom flag.')
                result.custom=obj['custom']
            return result
        keymap=obj.get('keymap',obj.get('Keymap'))
        check(isinstance(keymap,(str,list)),'JSON has no keymap or controls property.')
        if isinstance(keymap,list):
            check(all(isinstance(p,str) for p in keymap),'Invalid JSON keymap list.')
            keymap=';'.join(keymap)
        return parse_keymap(keymap,str(path))
    if re.search(r'^\s*\[',text,re.M):
        ini=configparser.ConfigParser(interpolation=None,strict=False,inline_comment_prefixes=None)
        ini.read_string(text)
        if ini.has_section('UFC6'):return parse_keymap(ini['UFC6'].get('keymap',''),str(path))
        matches=[section for section in ini.sections() if 'keymap' in ini[section]]
        if len(matches)==1:return parse_keymap(ini[matches[0]]['keymap'],str(path))
        if ini.has_section('Launch') and ini['Launch'].get('mode','').casefold()=='custom':
            text=ini['Launch'].get('arguments','')
            if text.startswith('raw:'):text=text[4:]
        else:raise PatchError('Select a configuration with a keymap, UFC6 section, or custom Launch/Arguments containing --keymap.')
    matches=list(re.finditer(r'--keymap(?:\s*=\s*|\s+)(?:"([^"\r\n]*)"|\x27((?:[^\x27\r\n]|\x27\x27)*)\x27|([^\s\r\n]+))',text))
    if matches:
        parts=[m.group(1) if m.group(1) is not None else m.group(2).replace("''","'") if m.group(2) is not None else m.group(3) for m in matches]
        return parse_keymap(';'.join(parts),str(path))
    check(not re.search(r'\b(?:powershell|cmd|start|python)\b',text,re.I),
          'No --keymap argument found. Select Kyty defaults explicitly if no custom mapping is used.')
    if re.fullmatch(r'[\w\s:;=+/*.,()\-]+',text.strip()) and '=' in text:
        return parse_keymap(text.strip(),str(path))
    raise PatchError('No readable keymap found. Load UFC6.ini, keymap JSON, a launch script/shortcut with --keymap, or choose Kyty defaults.')


def save(path,bindings):
    bindings.validate()
    Path(path).write_text(json.dumps(dict(schema=1,**bindings.digest_data()),indent=2)+'\n',encoding='utf-8')
