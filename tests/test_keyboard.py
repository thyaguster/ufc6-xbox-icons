import json
import os
import random
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import keyboard_bindings as bindings
import keyboard_art as art
import input_icons as icons
import patcher_core as core

APP=Path(__file__).resolve().parents[1]


class BindingTests(unittest.TestCase):
    def test_portheon_utf16_empty_and_custom(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'games/UFC6/UFC6.ini';path.parent.mkdir(parents=True)
            path.write_text('[UFC6]\nkeymap=\nother=100%\n',encoding='utf-16')
            self.assertEqual(bindings.load(d).controls,bindings.DEFAULTS)
            path.write_text('[UFC6]\nkeymap=Cross=Mouse:Left;Circle=Space;Options=Return\n',encoding='utf-16')
            b=bindings.load(d)
            self.assertEqual(b.controls['Cross'],'Mouse:Left')
            self.assertEqual(b.controls['Circle'],'Space')
            self.assertIsNone(b.controls['L1'])  # Custom replaces defaults.

    def test_export_roundtrip_and_exact_defaults_custom_flag(self):
        b=bindings.parse_keymap(';'.join(f'{k}={v}' for k,v in bindings.DEFAULTS.items()))
        self.assertTrue(b.custom)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'map.json';bindings.save(p,b)
            loaded=bindings.load(p)
            self.assertTrue(loaded.custom);self.assertEqual(loaded.controls,b.controls)

    def test_settings_script_is_read_never_run(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'launch.cmd'
            p.write_text('@echo off\necho should-not-run > BAD\n"engine.exe" --keymap "Cross=J;Circle=Mouse:Right"\n')
            with patch('subprocess.run',side_effect=AssertionError('No execution allowed')):
                b=bindings.load(p)
            self.assertEqual(b.controls['Circle'],'Mouse:Right')
            self.assertFalse((Path(d)/'BAD').exists())

    def test_shortcut_parsed_without_shell(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Kyty.lnk';text='--game game --keymap "Cross=J;Circle=L"'
            header=bytearray(76);struct.pack_into('<I',header,0,76);struct.pack_into('<I',header,20,32|128)
            p.write_bytes(header+struct.pack('<H',len(text))+text.encode('utf-16-le'))
            with patch('subprocess.run',side_effect=AssertionError('No shell allowed')):
                b=bindings.load(p)
            self.assertEqual(b.controls['Cross'],'J');self.assertEqual(b.controls['Circle'],'L')

    def test_custom_duplicates_and_normalized_modifiers(self):
        b=bindings.parse_keymap('Cross=Right Shift;Circle=Left Shift;Cross=K')
        self.assertEqual(b.controls['Cross'],'K');self.assertEqual(b.controls['Circle'],'Left Shift')
        values=dict(bindings.DEFAULTS);values['Cross']='Right Shift'
        with self.assertRaises(core.PatchError):bindings.from_controls(values)

    def test_invalid_reserved_and_unbound(self):
        for text in ['Cross=Escape','Circle=F11','Bogus=J','Cross=Ctrl+J','Cross=Mouse:Wheel']:
            with self.subTest(text=text),self.assertRaises(core.PatchError):bindings.parse_keymap(text)
        b=bindings.parse_keymap('Keyboard=Disabled')
        self.assertTrue(all(v is None for v in b.controls.values()))
        self.assertIn('Keyboard=Disabled',b.argument())
        self.assertEqual(bindings.parse_keymap('Pad=Disabled').controls,bindings.DEFAULTS)

    def test_raw_json_and_no_command_keymap(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'map.json';p.write_text(json.dumps(dict(keymap=['Cross=J','Circle=L'])))
            self.assertEqual(bindings.load(p).controls['Circle'],'L')
            p=Path(d)/'launch.cmd';p.write_text('start engine.exe --game foo')
            with self.assertRaises(core.PatchError):bindings.load(p)

    def test_standalone_custom_launcher_ini(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ufc6-quit-menu.ini'
            p.write_text('[Launch]\nMode=Custom\nArguments=raw:--game "my game" --keymap "Cross=Space;Circle=L"\n')
            self.assertEqual(bindings.load(p).controls['Cross'],'Space')

    def test_non_icon_options_are_retained_and_shell_text_is_literal(self):
        original="Pad=Disabled;Pad:Cross=South;MouseSensitivity=1.25;TouchCursorImage=C:/literal $x & 'image'.png;Cross=J;GyroToggle=P"
        b=bindings.parse_keymap(original)
        self.assertIn('MouseSensitivity=1.25',b.extra)
        self.assertIn('GyroToggle=P',b.extra)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'map.json';bindings.save(p,b);loaded=bindings.load(p)
            self.assertEqual(loaded.extra,b.extra)
            p=Path(d)/'argument.txt';p.write_text(b.argument())
            loaded=bindings.load(p)
            self.assertEqual(loaded.controls,b.controls)
            self.assertEqual(loaded.extra,b.extra)
            self.assertIn("''image''",b.argument())
        pad_only=bindings.parse_keymap('Pad=Disabled')
        self.assertFalse(pad_only.custom)
        self.assertEqual(pad_only.controls,bindings.DEFAULTS)
        self.assertIn('Pad=Disabled',pad_only.argument())


class ArtworkTests(unittest.TestCase):
    def test_current_and_legacy_engine_process_names(self):
        for name in ['UFC 6.exe','UFC 6 Parsec.exe','UFC 6 novo.exe','kyty_emulator.exe','Kyty.exe','UFC6.exe']:
            self.assertTrue(core.is_game_process(name),name)
        for name in ['UFC6-Xbox-Icons.exe','python.exe','PORTHEON.exe']:
            self.assertFalse(core.is_game_process(name),name)

    def test_descriptors_use_actual_actions(self):
        self.assertEqual(art.descriptor('buttons.Btn_ue_digital_four_ps_mc')['controls'],['Square'])
        self.assertEqual(art.descriptor('buttons.Btn_ue_digital_three_xb_mc')['controls'],['Triangle'])
        self.assertEqual(art.descriptor('ui/textures/skins/buttons/ps/white/digital_one_hold_skip_widget')['controls'],['Cross'])
        self.assertEqual(art.descriptor('buttons.Btn_las_d_mc')['controls'],['LeftStickDown'])
        self.assertIsNone(art.descriptor('ui/textures/skins/buttons/ps/box_art_ufc6'))

    def test_verified_ps5_address_points_and_allocation(self):
        points={(x,y):offset for x,y,offset in art._swizzle(128,128,16384)}
        self.assertEqual(points[(1,0)],64)
        self.assertEqual(points[(0,1)],16)
        self.assertEqual(points[(8,0)],2048)
        self.assertEqual(points[(0,8)],1024)
        self.assertEqual(points[(16,0)],4096)
        self.assertEqual(points[(0,16)],8192)
        points=art._swizzle(180,180,36864)
        self.assertEqual(len(points),45*45)
        self.assertEqual(len({offset for x,y,offset in points}),45*45)

    def test_transparent_pixels_and_binding_specific_output(self):
        desc=dict(controls=['Cross'],layout='row')
        b=bindings.defaults();a=art.render(32,32,desc,b)
        values=dict(b.controls);values['Cross']='Space';other=bindings.from_controls(values)
        c=art.render(32,32,desc,other)
        self.assertEqual(len(a),32*32*4);self.assertNotEqual(a,c)
        self.assertLess(a[3],255)
        self.assertIn(255,a[3::4]);self.assertIn(0,a[3::4])

    def test_flash_preserves_original_format_offsets_and_unrelated_data(self):
        from keyboard_flash import patch as patch_flash
        def tag(kind,data):
            return (struct.pack('<H',(kind<<6)|len(data)) if len(data)<63 else struct.pack('<HI',(kind<<6)|63,len(data)))+data
        # Entirely synthetic SWF: a generated bitmap, one bitmap-backed shape,
        # one sprite and one export. No game bytes are used by this test.
        rng=random.Random(42)
        pixels=b''.join(bytes((255,*rng.randbytes(3))) for _ in range(32*32))
        bitmap=struct.pack('<HBHH',1,5,32,32)+zlib.compress(pixels,9)
        shape=struct.pack('<H',2)+b'\x08\0'+b'\x01\x41\x01\0\0\0\x10\0'
        sprite=struct.pack('<HH',3,1)+tag(26,b'\x06\x01\0\x02\0\0')+tag(1,b'')+tag(0,b'')
        symbols=struct.pack('<HH',1,3)+b'buttons.Btn_ue_digital_one_ps_mc\0'
        body=b'\x08\0\0\x18\x01\0'+tag(36,bitmap)+tag(2,shape)+tag(39,sprite)+tag(76,symbols)+tag(1,b'')+tag(0,b'')
        payload=b'CWS\x09'+struct.pack('<I',8+len(body))+zlib.compress(body,9)+b'\0'*4096
        original=struct.pack('>IBBH',len(payload),0,0,len(payload))+payload
        transformed=patch_flash(original,bindings.defaults(),1)
        before=core.decode_swf(core.unframe(original)[0]);after=core.decode_swf(core.unframe(transformed)[0])
        self.assertEqual(list(core.swf_tags(before)),list(core.swf_tags(after)))
        self.assertEqual(len(original),len(transformed))
        for kind,pos,size in core.swf_tags(before):
            if kind==36:
                self.assertEqual(before[pos:pos+7],after[pos:pos+7])
                self.assertEqual(after[pos+2],5)
                self.assertEqual(len(zlib.decompress(after[pos+7:pos+size])),4096)
            else:self.assertEqual(before[pos:pos+size],after[pos:pos+size])


@unittest.skipUnless(os.environ.get('UFC6_KEYBOARD_FIXTURE'),'Private disposable keyboard fixture not supplied')
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(os.environ['UFC6_KEYBOARD_FIXTURE']).resolve()
        if not (cls.root/'.disposable-keyboard-fixture').is_file():raise RuntimeError('Only a marked disposable fixture may be modified by these tests.')
        cls.p=icons.load_profile(APP)
        with core.GameFiles(cls.root,icons.paths_for(cls.p),False) as f:
            cls.originals,actual=icons.initial_originals(f,cls.root,cls.p)
            if cls.originals!=actual:raise RuntimeError('Use a fresh clean fixture.')
        cls.default=bindings.defaults()
        values=dict(bindings.DEFAULTS);values['Cross']='Space';values['Square']='Mouse:Left'
        cls.custom=bindings.from_controls(values)

    def setUp(self):
        self.running=patch.object(core,'game_running',return_value=False);self.running.start()
    def tearDown(self):self.running.stop()

    def read_all(self):
        with core.GameFiles(self.root,icons.paths_for(self.p),False) as f:return {e['id']:f.read(e) for e in self.p['entries']}

    def test_01_late_extra_corruption_rejected_before_writes(self):
        e=self.p['entries'][-1];p=self.root/e['path']
        with p.open('r+b') as f:f.seek(e['offset']);old=f.read(e['length']);f.seek(e['offset']);f.write(bytes([old[0]^255])+old[1:])
        try:
            with self.assertRaises(core.PatchError):icons.run('install',self.root,self.p,style='keyboard',bindings=self.default)
            self.assertFalse((self.root/icons.BACKUP).exists())
        finally:
            with p.open('r+b') as f:f.seek(e['offset']);f.write(old)
        self.assertEqual(self.read_all(),self.originals)

    def test_02_migrate_legacy_xbox_backup_and_rollback(self):
        core.run('install',self.root,self.p['base'])
        before=self.read_all();real=core.GameFiles.write;calls=[0]
        def fail(files,entry,data):
            calls[0]+=1
            if calls[0]==5:raise OSError('Simulated disk write error')
            return real(files,entry,data)
        with patch.object(core.GameFiles,'write',fail),self.assertRaisesRegex(core.PatchError,'restored'):
            icons.run('install',self.root,self.p,style='keyboard',bindings=self.default)
        self.assertEqual(self.read_all(),before)
        self.assertTrue((self.root/icons.BACKUP).is_file())
        self.assertIn('verified',icons.run('status',self.root,self.p))
        icons.run('install',self.root,self.p,style='keyboard',bindings=self.default)
        self.assertIn('keyboard',icons.run('status',self.root,self.p))

    def test_03_binding_update_and_switch_back(self):
        before=self.read_all()
        icons.run('install',self.root,self.p,style='keyboard',bindings=self.custom)
        self.assertNotEqual(before,self.read_all())
        self.assertIn('already installed',icons.run('install',self.root,self.p,style='keyboard',bindings=self.custom))
        icons.run('install',self.root,self.p,style='xbox')
        with core.GameFiles(self.root,icons.paths_for(self.p),False) as f:
            core.verify_backup_state(f,core.read_backup(self.root/core.BACKUP_NAME,self.p['base']))
        icons.run('restore',self.root,self.p)
        self.assertEqual(self.read_all(),self.originals)

    def test_04_state_write_interruption_recovery(self):
        state=self.root/icons.STATE;old=state.read_bytes();state.unlink()
        try:
            self.assertIn('playstation',icons.run('status',self.root,self.p))
            icons.run('install',self.root,self.p,style='keyboard',bindings=self.default)
            self.assertIn('keyboard',icons.run('status',self.root,self.p))
            icons.run('restore',self.root,self.p)
        finally:
            if not state.exists():state.write_bytes(old)

    def test_05_unknown_changes_rejected(self):
        icons.run('install',self.root,self.p,style='keyboard',bindings=self.default)
        e=self.p['entries'][-1];p=self.root/e['path']
        with p.open('r+b') as f:f.seek(e['offset']);old=f.read(e['length']);f.seek(e['offset']);f.write(bytes([old[0]^255])+old[1:])
        try:
            with self.assertRaisesRegex(core.PatchError,'outside this installer'):icons.run('restore',self.root,self.p)
        finally:
            with p.open('r+b') as f:f.seek(e['offset']);f.write(old)
        icons.run('restore',self.root,self.p)

    def test_06_running_game_refused_and_guards_preserved(self):
        before=self.read_all()
        with patch.object(core,'game_running',return_value=True),self.assertRaisesRegex(core.PatchError,'Close UFC 6'):
            icons.run('install',self.root,self.p,style='keyboard',bindings=self.default)
        self.assertEqual(before,self.read_all())
        guard=b'FIXTURE: original guard, never modify.'
        for rel in icons.paths_for(self.p):
            with (self.root/rel).open('rb') as f:self.assertEqual(f.read(len(guard)),guard)

    def test_07_commit_failure_then_second_write_failure_recovers(self):
        real=icons.atomic_json;calls=[0]
        def fail_commit(path,value):
            calls[0]+=1
            if calls[0]==2:raise OSError('Simulated state commit failure')
            return real(path,value)
        with patch.object(icons,'atomic_json',fail_commit),self.assertRaises(OSError):
            icons.run('install',self.root,self.p,style='keyboard',bindings=self.custom)
        self.assertIn('keyboard',icons.run('status',self.root,self.p))
        before=self.read_all();real_write=core.GameFiles.write;writes=[0]
        def fail_write(files,entry,data):
            writes[0]+=1
            if writes[0]==4:raise OSError('Second operation write failed')
            return real_write(files,entry,data)
        with patch.object(core.GameFiles,'write',fail_write),self.assertRaises(core.PatchError):
            icons.run('install',self.root,self.p,style='xbox')
        self.assertEqual(self.read_all(),before)
        self.assertIn('keyboard',icons.run('status',self.root,self.p))
        icons.run('restore',self.root,self.p)
        self.assertEqual(self.read_all(),self.originals)


if __name__=='__main__':unittest.main()
