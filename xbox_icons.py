"""Desktop and command-line entry point for the portable patcher."""
import argparse
import json
from pathlib import Path
import queue
import sys
import threading

from patcher_core import PatchError, load_profile, run

VERSION = '1.0.1'
# In a frozen build __file__ points inside the bundled resources, so neither
# the profile nor notices depend on files beside the executable.
APP_DIR = Path(__file__).resolve().parent


def license_text():
    paths = [APP_DIR/'LICENSE', APP_DIR/'THIRD-PARTY-NOTICES.md']
    paths += sorted((APP_DIR/'runtime-licenses').glob('*.txt'))
    return '\n\n'.join(p.name+'\n'+'='*len(p.name)+'\n'+p.read_text(encoding='utf-8') for p in paths)


def gui():
    import tkinter as tk
    from tkinter import filedialog, ttk
    window = tk.Tk()
    window.title('UFC 6 Xbox Icons')
    window.geometry('680x430')
    window.minsize(620, 400)
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='UFC 6 Xbox Icons', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='PPSA23566  |  Game version 01.006.000  |  Mod '+VERSION).pack(anchor='w', pady=(4,16))
    ttk.Label(frame, text='Choose the extracted game folder containing Data and sce_sys.').pack(anchor='w')
    row = ttk.Frame(frame)
    row.pack(fill='x', pady=(8,12))
    path = tk.StringVar()
    field = ttk.Entry(row, textvariable=path)
    field.pack(side='left', fill='x', expand=True)
    busy = [False]
    events = queue.Queue()
    def choose():
        selected = filedialog.askdirectory(parent=window, title='Select extracted UFC 6 game folder')
        if selected:
            path.set(selected)
    browse = ttk.Button(row, text='Browse...', command=choose)
    browse.pack(side='left', padx=(8,0))
    ttk.Label(frame, text='Close UFC 6 before installing or restoring. Everything runs offline.').pack(anchor='w')
    ttk.Label(frame, text='A restore backup is saved in your game folder. Keep it there.').pack(anchor='w', pady=(3,12))
    buttons = ttk.Frame(frame)
    buttons.pack(fill='x', pady=(0,10))
    output = tk.Text(frame, height=8, wrap='word', state='disabled', font=('Segoe UI',10))
    output.pack(fill='both', expand=True)
    def append(text):
        output.configure(state='normal')
        output.insert('end', text+'\n')
        output.see('end')
        output.configure(state='disabled')
    controls = [field,browse]
    def execute(action):
        if not path.get().strip():
            append('Select your extracted game folder first.')
            return
        selected = path.get().strip()
        busy[0] = True
        for control in controls:
            control.configure(state='disabled')
        append(action.capitalize()+'...')
        def worker():
            try:
                profile = load_profile(APP_DIR)
                message = run(action, selected, profile, lambda text: events.put(('log',text)))
                events.put(('done',message))
            except Exception as exc:
                events.put(('done','Could not complete: '+str(exc)))
        threading.Thread(target=worker, daemon=True).start()
    for action, label in [('status','Check status'),('install','Install Xbox icons'),('restore','Restore original')]:
        button = ttk.Button(buttons, text=label, command=lambda a=action: execute(a))
        button.pack(side='left', padx=(0,8))
        controls.append(button)
    def show_licenses():
        from tkinter.scrolledtext import ScrolledText
        dialog = tk.Toplevel(window)
        dialog.title('Licenses and notices')
        dialog.geometry('760x540')
        text = ScrolledText(dialog, wrap='word', font=('Segoe UI',10))
        text.pack(fill='both',expand=True,padx=12,pady=12)
        text.insert('1.0',license_text())
        text.configure(state='disabled')
    ttk.Button(buttons,text='Licenses',command=show_licenses).pack(side='left')
    def poll():
        try:
            while True:
                kind,text = events.get_nowait()
                append(text)
                if kind == 'done':
                    busy[0] = False
                    for control in controls:
                        control.configure(state='normal')
        except queue.Empty:
            pass
        window.after(75,poll)
    def close():
        if busy[0]:
            append('Please wait for the operation and verification to finish.')
        else:
            window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    poll()
    window.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Install Xbox prompts using assets from your own UFC 6 backup.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--install',action='store_true')
    group.add_argument('--restore',action='store_true')
    group.add_argument('--status',action='store_true')
    parser.add_argument('--game-dir',type=Path)
    parser.add_argument('--report',type=Path,help='Write a JSON operation report; useful with the Windows GUI executable.')
    parser.add_argument('--version',action='version',version=VERSION)
    args = parser.parse_args()
    if not (args.install or args.restore or args.status):
        gui()
        return 0
    if not args.game_dir:
        parser.error('--game-dir is required for command-line operations')
    log = []
    def emit(text):
        log.append(text)
        if sys.stdout:
            print(text,flush=True)
    success = False
    try:
        action = 'install' if args.install else 'restore' if args.restore else 'status'
        emit(run(action,args.game_dir,load_profile(APP_DIR),emit))
        success = True
    except Exception as exc:
        emit('Could not complete: '+str(exc))
    if args.report:
        args.report.write_text(json.dumps(dict(success=success,messages=log),indent=2)+'\n',encoding='utf-8')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
