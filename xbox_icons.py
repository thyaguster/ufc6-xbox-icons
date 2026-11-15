"""Desktop and command-line entry point for the portable patcher."""
import argparse
import json
from pathlib import Path
import queue
import sys
import threading


VERSION = '1.1.0'
# In a frozen build __file__ points inside the bundled resources, so neither
# the profile nor notices depend on files beside the executable.
APP_DIR = Path(__file__).resolve().parent


def license_text():
    paths = [APP_DIR/'LICENSE', APP_DIR/'THIRD-PARTY-NOTICES.md']
    paths += sorted((APP_DIR/'runtime-licenses').glob('*.txt'))
    paths += [APP_DIR/'keyboard-art/font/OFL.txt']
    return '\n\n'.join(p.name+'\n'+'='*len(p.name)+'\n'+p.read_text(encoding='utf-8') for p in paths)


def gui():
    from input_gui import gui as open_gui
    open_gui(APP_DIR,VERSION,license_text)


def main():
    parser = argparse.ArgumentParser(description='Install Xbox or keyboard prompts, import PORTHEON/Kyty bindings, and restore original icons.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--install',action='store_true')
    group.add_argument('--restore',action='store_true')
    group.add_argument('--status',action='store_true')
    parser.add_argument('--game-dir',type=Path)
    parser.add_argument('--style',choices=['xbox','keyboard','playstation'],default='xbox')
    source=parser.add_mutually_exclusive_group()
    source.add_argument('--bindings',type=Path,help='PORTHEON folder/UFC6.ini, exported JSON, Kyty launch script or shortcut.')
    source.add_argument('--keymap',help='Raw Kyty control=key;control=key mapping.')
    parser.add_argument('--export-bindings',type=Path,help='Export sanitized binding JSON without modifying the game.')
    parser.add_argument('--report',type=Path,help='Write a JSON operation report; useful with the Windows GUI executable.')
    parser.add_argument('--version',action='version',version=VERSION)
    args = parser.parse_args()
    if not (args.install or args.restore or args.status or args.export_bindings):
        gui()
        return 0
    if not args.game_dir and not args.export_bindings:
        parser.error('--game-dir is required for command-line operations')
    log = []
    def emit(text):
        log.append(text)
        if sys.stdout:
            print(text,flush=True)
    success = False
    try:
        from keyboard_bindings import defaults,load,parse_keymap,save
        import input_icons
        bindings=load(args.bindings) if args.bindings else parse_keymap(args.keymap) if args.keymap is not None else defaults()
        if args.export_bindings:
            save(args.export_bindings,bindings)
            emit('Exported keyboard bindings; no game or launcher files were changed.')
        else:
            action = 'install' if args.install else 'restore' if args.restore else 'status'
            emit(input_icons.run(action,args.game_dir,input_icons.load_profile(APP_DIR),emit,style=args.style,bindings=bindings))
        success = True
    except Exception as exc:
        emit('Could not complete: '+str(exc))
    if args.report:
        args.report.write_text(json.dumps(dict(success=success,messages=log),indent=2)+'\n',encoding='utf-8')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
