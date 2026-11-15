"""Original monochrome keycaps and conservative PS5 BC3 encoding."""
from __future__ import annotations
import functools
import math
from pathlib import Path
import re
import struct

from patcher_core import PatchError, check

ROOT=Path(__file__).resolve().parent


def descriptor(name):
    """Return controls represented by an existing texture or Flash symbol."""
    name=name.rsplit('/',1)[-1].split('.')[-1].lower()
    name=re.sub(r'^btn_|_mc$','',name)
    name=name.replace('_highlight','').replace('_ps','').replace('_xb','')
    name=re.sub(r'^ue_','',name)
    # EA's names follow Cross/A, Circle/B, Triangle/Y, Square/X order.
    # Verified against the original PS and Xbox texture artwork, not enum order.
    direct={'digital_one':['Cross'],'digital_two':['Circle'],'digital_three':['Triangle'],
            'digital_four':['Square'],'left_bumper':['L1'],'right_bumper':['R1'],
            'left_trigger':['L2'],'right_trigger':['R2'],'left_on_trigger':['L2'],
            'right_on_trigger':['R2'],'left_right_bumper':['L1','R1'],
            'left_right_trigger':['L2','R2'],'select':['TouchPad'],'start':['Options'],
            'guide':['Guide']}
    cleaned=re.sub(r'_(?:hold_skip_widget|hold|precanned_message)$','',name)
    if cleaned in direct:return dict(controls=direct[cleaned],layout='row')
    m=re.fullmatch(r'(las|ras|dpad)(?:_(.*))?',name)
    if not m:return None
    family,suffix=m.groups();suffix=suffix or 'a'
    if suffix=='c':return dict(controls=['L3' if family=='las' else 'R3'],layout='row')
    prefix={'las':'LeftStick','ras':'RightStick','dpad':''}[family]
    if suffix.startswith('gesture_'):
        suffix=suffix[len('gesture_'):]
        if suffix in ('advanced_position','submission_attempts'):suffix='a'
    suffix=suffix.replace('_','')
    if suffix in ('a','large'):suffix='uldr'
    dirs={'u':'Up','d':'Down','l':'Left','r':'Right'}
    if not suffix or any(c not in dirs for c in suffix):return None
    controls=[prefix+dirs[c] for c in suffix]
    return dict(controls=controls,layout='cross' if len(controls)>=3 else 'row')


def label(value):
    if not value:return '-'
    special={'Return':'ENTER','Return2':'ENTER','Escape':'ESC','Space':'SPACE',
             'Backspace':'BKSP','CapsLock':'CAPS','PageUp':'PGUP','PageDown':'PGDN',
             'Left Shift':'SHIFT','Right Shift':'SHIFT','Left Ctrl':'CTRL',
             'Right Ctrl':'CTRL','Left Alt':'ALT','Right Alt':'ALT',
             'Left GUI':'WIN','Right GUI':'WIN','PrintScreen':'PRTSC',
             'ScrollLock':'SCRLK','Numlock':'NUM','Application':'MENU',
             'VolumeDown':'VOL-','VolumeUp':'VOL+','Mouse:X1':'M4','Mouse:X2':'M5'}
    if value in special:return special[value]
    if value.startswith('Keypad '):return 'NUM '+value[7:].upper()
    return value.upper()


def pillow():
    try:
        from PIL import Image,ImageDraw,ImageFont
    except ImportError as exc:
        raise PatchError('Keyboard artwork needs Pillow. From the source folder run: python -m pip install -r requirements.txt') from exc
    return Image,ImageDraw,ImageFont


def _cap(size,value,state):
    Image,ImageDraw,ImageFont=pillow()
    w,h=size;im=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(im)
    ink=(36,36,36,255) if state=='normal' else (250,250,250,255)
    face=(250,250,250,255) if state=='normal' else (36,36,36,255)
    edge=max(1,h//24);pad=max(1,h//20)
    draw.rounded_rectangle((pad,pad,w-pad-1,h-pad-1),radius=max(2,h//8),fill=face,
                           outline=ink if state!='normal' else None,width=edge)
    if value in ('Up','Down','Left','Right'):
        pts=[(.5,.23),(.77,.5),(.60,.5),(.60,.77),(.40,.77),(.40,.5),(.23,.5)]
        theta={'Up':0,'Right':90,'Down':180,'Left':270}[value]*math.pi/180
        points=[(((x-.5)*math.cos(theta)-(y-.5)*math.sin(theta)+.5)*w,
                 ((x-.5)*math.sin(theta)+(y-.5)*math.cos(theta)+.5)*h) for x,y in pts]
        draw.polygon(points,fill=ink)
    elif value in ('Mouse:Left','Mouse:Right','Mouse:Middle'):
        x0,y0,x1,y1=.30*w,.15*h,.70*w,.85*h
        draw.rounded_rectangle((x0,y0,x1,y1),radius=max(2,.16*h),outline=ink,width=max(1,h//20))
        draw.line((x0,.46*h,x1,.46*h),fill=ink,width=max(1,h//28))
        draw.line((.5*w,y0,.5*w,.46*h),fill=ink,width=max(1,h//28))
        if value=='Mouse:Middle':draw.rounded_rectangle((.45*w,.23*h,.55*w,.42*h),radius=max(1,h//36),fill=ink)
        else:
            left,right=(.35,.45) if value=='Mouse:Left' else (.55,.65)
            draw.rounded_rectangle((left*w,.24*h,right*w,.39*h),radius=max(1,h//40),fill=ink)
    else:
        text=label(value)
        font=ImageFont.truetype(str(ROOT/'keyboard-art/font/BarlowCondensed-Bold.ttf'),max(6,round(h*.87)))
        box=draw.textbbox((0,0),text,font=font)
        glyph=Image.new('RGBA',(box[2]-box[0]+4,box[3]-box[1]+4))
        ImageDraw.Draw(glyph).text((2-box[0],2-box[1]),text,font=font,fill=ink)
        target_h=round(h*.57);target_w=round(glyph.width*target_h/glyph.height)
        target_w=min(round(w*.78),target_w)
        glyph=glyph.resize((max(1,target_w),max(1,target_h)),Image.Resampling.LANCZOS)
        im.alpha_composite(glyph,((w-glyph.width)//2,(h-glyph.height)//2))
    return im


@functools.lru_cache(maxsize=768)
def _render(width,height,controls,layout,values,state):
    Image,_,_=pillow();factor=4
    w,h=width*factor,height*factor
    image=Image.new('RGBA',(w,h))
    if len(controls)==1:
        image.alpha_composite(_cap((w,h),values[0],state))
    elif layout=='cross':
        cw=max(1,round(w*.42));ch=max(1,round(h*.42))
        for control,value in zip(controls,values):
            direction=next((d for d in ('Up','Down','Left','Right') if control.endswith(d)),None)
            x,y={'Up':((w-cw)//2,0),'Down':((w-cw)//2,h-ch),
                 'Left':(0,(h-ch)//2),'Right':(w-cw,(h-ch)//2)}[direction]
            image.alpha_composite(_cap((cw,ch),value,state),(x,y))
    else:
        gap=max(2,w//30);cw=max(1,(w-gap*(len(controls)-1))//len(controls));ch=min(h,cw)
        for i,value in enumerate(values):image.alpha_composite(_cap((cw,ch),value,state),(i*(cw+gap),(h-ch)//2))
    return image.resize((width,height),Image.Resampling.LANCZOS).tobytes()


def render(width,height,desc,bindings,state='normal'):
    check(0<width<=1024 and 0<height<=1024,'Unsupported icon dimensions.')
    controls=tuple(desc['controls']);values=tuple(bindings.controls.get(c) for c in controls)
    return _render(width,height,controls,desc['layout'],values,state)


def bc3_block(pixels):
    alphas=[p[3] for p in pixels];a0=max(alphas);a1=min(alphas)
    if a0==a1:a1=0 if a0 else 255
    ap=[a0,a1]
    if a0>a1:ap += [((7-i)*a0+i*a1)//7 for i in range(1,7)]
    else:ap += [((5-i)*a0+i*a1)//5 for i in range(1,5)]+[0,255]
    ai=sum(min(range(8),key=lambda k:abs(ap[k]-a))<<(3*i) for i,a in enumerate(alphas))
    # The artwork is monochrome; fixed white/black RGB565 endpoints give four
    # stable gray levels and independent alpha, without a native compressor.
    colors=[255,0,170,85]
    ci=sum(min(range(4),key=lambda k:abs(colors[k]-p[0]))<<(2*i) for i,p in enumerate(pixels))
    return bytes((a0,a1))+ai.to_bytes(6,'little')+struct.pack('<HHI',65535,0,ci)


@functools.lru_cache(maxsize=256)
def _swizzle(width,height,length):
    bw,bh=width//4,height//4
    check(width%4==0 and height%4==0,'Unsupported BC3 dimensions.')
    # PS5 BC3 UI allocations use 16x16-block tiles (64x64 pixels).
    # The two upper intra-tile coordinate bits are Y3 then X3. This was
    # independently checked by reconstructing an existing 84x56 texture.
    pitch=((bw+15)//16)*16
    result=[]
    for y in range(bh):
        for x in range(bw):
            low=sum(v<<p for v,p in zip((x&1,(x>>1)&1,(x>>2)&1,(x>>3)&1,
                                         y&1,(y>>1)&1,(y>>2)&1,(y>>3)&1),(2,3,5,7,0,1,4,6)))
            offset=(((y//16)*(pitch//16)+x//16)*256+low)*16
            check(offset+16<=length,'Icon allocation is too small for its PS5 tile layout.')
            result.append((x,y,offset))
    return result


def texture(original,info,bindings):
    from patcher_core import unframe
    raw,frames=unframe(original)
    w,h=info['width'],info['height']
    rgba=render(w,h,info['descriptor'],bindings,info.get('state','normal'))
    pixels=[tuple(rgba[i:i+4]) for i in range(0,len(rgba),4)]
    # Alpha zero blocks are explicitly transparent in the padded allocation.
    transparent=bc3_block([(0,0,0,0)]*16)
    output=bytearray(transparent*(len(raw)//16))
    for x,y,offset in _swizzle(w,h,len(raw)):
        block=[pixels[(y*4+dy)*w+x*4+dx] for dy in range(4) for dx in range(4)]
        output[offset:offset+16]=bc3_block(block)
    result=bytearray(original)
    for stored,plain,length in frames:result[stored:stored+length]=output[plain:plain+length]
    return bytes(result)
