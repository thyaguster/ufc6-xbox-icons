"""Desktop UI for imported keyboard bindings and reversible icon styles."""
from pathlib import Path
import queue
import threading

import input_icons
from keyboard_bindings import DEFAULTS,defaults,from_controls,load,save


def gui(app_dir,version,license_text):
    import tkinter as tk
    from tkinter import filedialog,messagebox,simpledialog,ttk
    window=tk.Tk();window.title('UFC 6 Controller Icons')
    window.geometry('960x790');window.minsize(880,720)
    frame=ttk.Frame(window,padding=20);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='UFC 6 Controller Icons',font=('Segoe UI',20,'bold')).pack(anchor='w')
    ttk.Label(frame,text='PPSA23566  |  01.006.000  |  '+version).pack(anchor='w',pady=(2,12))
    row=ttk.Frame(frame);row.pack(fill='x')
    ttk.Label(row,text='Extracted game folder:').pack(side='left')
    game=tk.StringVar();field=ttk.Entry(row,textvariable=game);field.pack(side='left',fill='x',expand=True,padx=8)
    events=queue.Queue();busy=[False];bindings=[defaults()];controls=[]
    def append(text):
        output.configure(state='normal');output.insert('end',text+'\n');output.see('end');output.configure(state='disabled')
    def scan_portheon(root):
        candidates=set()
        for parent in [root,*list(root.parents)[:3],app_dir,*list(app_dir.parents)[:2]]:
            for rel in ['games/UFC6/UFC6.ini','PORTHEON/games/UFC6/UFC6.ini','UFC6.ini']:
                p=parent/rel
                if p.is_file():candidates.add(p.resolve())
        if len(candidates)==1:
            try:bindings[0]=load(next(iter(candidates)));refresh();append('Loaded nearby PORTHEON keyboard settings. Review the bindings below.')
            except Exception as exc:append('Could not import nearby settings: '+str(exc))
    def choose_game():
        value=filedialog.askdirectory(parent=window,title='Choose extracted UFC 6 game folder')
        if value:game.set(value);scan_portheon(Path(value).resolve())
    browse=ttk.Button(row,text='Browse…',command=choose_game);browse.pack(side='left');controls.extend([field,browse])
    row=ttk.Frame(frame);row.pack(fill='x',pady=(12,8))
    ttk.Label(row,text='Icon style:').pack(side='left')
    choices={'Xbox':'xbox','Keyboard / mouse':'keyboard','Original PlayStation':'playstation'}
    style=ttk.Combobox(row,values=list(choices),state='readonly',width=26);style.set('Xbox');style.pack(side='left',padx=8)
    controls.append(style)
    ttk.Label(row,text='Close UFC 6 before install/restore. Runs offline.').pack(side='left',padx=8)
    kb=ttk.LabelFrame(frame,text='Keyboard labels — import your actual controls',padding=10);kb.pack(fill='both',expand=True,pady=(0,10))
    source=tk.StringVar();ttk.Label(kb,textvariable=source,wraplength=850).pack(anchor='w')
    row=ttk.Frame(kb);row.pack(fill='x',pady=8)
    def use_defaults():bindings[0]=defaults();refresh()
    def import_bindings(folder=False):
        value=filedialog.askdirectory(parent=window,title='Choose PORTHEON installation or UFC6 folder') if folder else filedialog.askopenfilename(parent=window,title='Load UFC6.ini or Kyty keymap/launch settings',filetypes=[('Settings and launch files','*.ini *.json *.txt *.cmd *.bat *.ps1 *.lnk'),('All files','*.*')])
        if not value:return
        try:
            bindings[0]=load(value);refresh();style.set('Keyboard / mouse')
            append('Bindings imported read-only. Launcher settings were not changed.')
        except Exception as exc:messagebox.showerror('Could not load bindings',str(exc),parent=window)
    def export():
        value=filedialog.asksaveasfilename(parent=window,title='Export bindings for standalone Kyty',defaultextension='.json',filetypes=[('Binding JSON','*.json'),('PowerShell argument text','*.txt')])
        if value:
            try:
                if Path(value).suffix.lower()=='.txt':Path(value).write_text(bindings[0].argument()+'\n',encoding='utf-8')
                else:save(value,bindings[0])
                append('Exported bindings. For standalone Kyty, use the matching --keymap argument when launching.')
            except Exception as exc:messagebox.showerror('Export failed',str(exc),parent=window)
    def copy_argument():
        value=bindings[0].argument();window.clipboard_clear();window.clipboard_append(value)
        append('Copied a PowerShell-quoted Kyty --keymap argument.' if value else 'Built-in Kyty defaults selected: omit --keymap when launching.')
    for text,command in [('Kyty defaults',use_defaults),('Load PORTHEON folder…',lambda:import_bindings(True)),('Load settings file…',import_bindings),('Export…',export),('Copy Kyty (PowerShell)',copy_argument)]:
        b=ttk.Button(row,text=text,command=command);b.pack(side='left',padx=(0,6));controls.append(b)
    body=ttk.Frame(kb);body.pack(fill='both',expand=True)
    tree=ttk.Treeview(body,columns=('control','key'),show='headings',height=10,selectmode='browse')
    tree.heading('control',text='Controller action');tree.heading('key',text='Keyboard / mouse binding')
    tree.column('control',width=350);tree.column('key',width=350)
    scroll=ttk.Scrollbar(body,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
    tree.pack(side='left',fill='both',expand=True);scroll.pack(side='left',fill='y')
    names={'Cross':'Cross / Xbox A','Circle':'Circle / Xbox B','Square':'Square / Xbox X','Triangle':'Triangle / Xbox Y',
           'TouchPad':'Touchpad / Select','TouchPadRight':'Touchpad right side','Options':'Options / Pause'}
    def edit(event=None):
        if busy[0]:return
        selected=tree.selection()
        if not selected:return
        control=selected[0]
        value=simpledialog.askstring('Edit icon binding',f'{names.get(control,control)}\nSDL key name or Mouse:Left/Right/Middle/X1/X2.\nBlank means unbound. Export changes for standalone Kyty.',initialvalue=bindings[0].controls[control] or '',parent=window)
        if value is None:return
        try:
            values=dict(bindings[0].controls);values[control]=value
            bindings[0]=from_controls(values,extra=bindings[0].extra,custom=True);refresh()
        except Exception as exc:messagebox.showerror('Invalid binding',str(exc),parent=window)
    tree.bind('<Double-1>',edit)
    edit_button=ttk.Button(kb,text='Edit selected binding…',command=edit);edit_button.pack(anchor='w',pady=(6,3));controls.append(edit_button)
    ttk.Label(kb,text='Changing controls later requires reinstalling keyboard icons. Imports are read-only; edits here only change labels until you use the exported Kyty keymap.',wraplength=850).pack(anchor='w')
    preview=ttk.Label(kb);preview.pack(anchor='w',pady=(6,0));preview_image=[None]
    def refresh():
        source.set('Source: '+bindings[0].source)
        for child in tree.get_children():tree.delete(child)
        for control,key in bindings[0].controls.items():tree.insert('', 'end',iid=control,values=(names.get(control,control),key or 'UNBOUND'))
        try:
            from PIL import Image,ImageDraw,ImageFont,ImageTk
            from keyboard_art import render
            im=Image.new('RGB',(840,40),'#292929');draw=ImageDraw.Draw(im);x=6
            font=ImageFont.truetype(str(app_dir/'keyboard-art/font/BarlowCondensed-Bold.ttf'),20)
            for control,text,width in [('Cross','SELECT',32),('Circle','BACK',32),('Triangle','SIMULATE',32),('L1','PREV TAB',36),('R1','NEXT TAB',36)]:
                pixels=render(width,32,dict(controls=[control],layout='row'),bindings[0])
                icon=Image.frombytes('RGBA',(width,32),pixels);im.paste(icon,(round(x),4),icon);x+=width+7
                draw.text((x,10),text,font=font,fill='#fafafa');x+=draw.textlength(text,font=font)+25
            preview_image[0]=ImageTk.PhotoImage(im,master=window);preview.configure(image=preview_image[0],text='')
        except ImportError:preview.configure(image='',text='Install Pillow for the keyboard preview: python -m pip install -r requirements.txt')
    ttk.Label(frame,text='Keep .ufc6-input-icons-backup.zip and .ufc6-input-icons-state.json in the game folder for restore and mode switching.',wraplength=910).pack(anchor='w',pady=(0,8))
    buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=(0,8))
    output=tk.Text(frame,height=4,wrap='word',state='disabled',font=('Segoe UI',10));output.pack(fill='x')
    def execute(action):
        if not game.get().strip():append('Select your extracted game folder first.');return
        root=game.get().strip();mode=choices.get(style.get());selected=bindings[0]
        if mode is None:append('Select an icon style.');return
        busy[0]=True;saved=[(w,str(w.cget('state'))) for w in controls]
        for widget,_ in saved:widget.configure(state='disabled')
        append(action.capitalize()+'…')
        def worker():
            try:
                message=input_icons.run(action,root,input_icons.load_profile(app_dir),lambda s:events.put(('log',s)),style=mode,bindings=selected)
                events.put(('done',(message,saved)))
            except Exception as exc:events.put(('done',('Could not complete: '+str(exc),saved)))
        threading.Thread(target=worker,daemon=True).start()
    for text,action in [('Check status','status'),('Install selected icons','install'),('Restore original','restore')]:
        b=ttk.Button(buttons,text=text,command=lambda a=action:execute(a));b.pack(side='left',padx=(0,8));controls.append(b)
    def licenses():
        from tkinter.scrolledtext import ScrolledText
        dialog=tk.Toplevel(window);dialog.title('Licenses');dialog.geometry('760x540')
        text=ScrolledText(dialog,wrap='word');text.pack(fill='both',expand=True,padx=12,pady=12)
        text.insert('1.0',license_text());text.configure(state='disabled')
    ttk.Button(buttons,text='Licenses',command=licenses).pack(side='left')
    def poll():
        try:
            while True:
                kind,data=events.get_nowait()
                if kind=='log':append(data)
                else:
                    message,saved=data;append(message);busy[0]=False
                    for widget,state in saved:widget.configure(state=state)
        except queue.Empty:pass
        window.after(75,poll)
    def close():
        if busy[0]:append('Wait for installation and verification to finish.')
        else:window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    refresh();poll();window.update_idletasks()
    # Size from actual themed font metrics: Windows display scaling can make
    # a fixed-height form hide its install buttons or operation log.
    available_height=max(560,window.winfo_screenheight()-100)
    while window.winfo_reqheight()+16>available_height and int(tree.cget('height'))>2:
        tree.configure(height=int(tree.cget('height'))-1);window.update_idletasks()
    if window.winfo_reqheight()+16>available_height:
        output.configure(height=3);frame.configure(padding=16);window.update_idletasks()
    width=min(max(960,window.winfo_reqwidth()+16),window.winfo_screenwidth()-40)
    height=min(max(790,window.winfo_reqheight()+16),available_height)
    window.minsize(min(880,width),min(720,height));window.geometry(f'{width}x{height}')
    window.mainloop()
