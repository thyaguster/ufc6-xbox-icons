"""Replace controller artwork inside existing Flash bitmap definitions only."""
from __future__ import annotations
import struct
import zlib

from patcher_core import check,decode_swf,swf_symbols,swf_tags,unframe
from keyboard_art import descriptor,render


def records(data,start,end):
    while start+2<=end:
        tag_start=start
        word=struct.unpack_from('<H',data,start)[0];start+=2
        kind,size=word>>6,word&63
        if size==63:size=struct.unpack_from('<I',data,start)[0];start+=4
        check(start+size<=end,'Invalid nested Flash tag.')
        yield kind,start,size,tag_start
        start+=size
        if kind==0:break


def skip_rect(data,pos):
    n=data[pos]>>3
    return pos+(5+4*n+7)//8


def skip_matrix(data,pos):
    bit=pos*8
    def take(n):
        nonlocal bit
        value=0
        for _ in range(n):value=(value<<1)|((data[bit//8]>>(7-bit%8))&1);bit+=1
        return value
    if take(1):n=take(5);take(2*n)
    if take(1):n=take(5);take(2*n)
    n=take(5);take(2*n)
    return (bit+7)//8


def bitmap_for_shape(data,pos,size):
    pos=skip_rect(data,pos+2)
    count=data[pos];pos+=1
    if count==255:count=struct.unpack_from('<H',data,pos)[0];pos+=2
    check(1<=count<=8,'Unexpected controller shape fill count.')
    bitmaps=[]
    for _ in range(count):
        kind=data[pos];pos+=1
        check(kind in (0x40,0x41,0x42,0x43),'Controller artwork is not a bitmap shape.')
        bitmap=struct.unpack_from('<H',data,pos)[0];pos=skip_matrix(data,pos+2)
        if bitmap!=65535:bitmaps.append(bitmap)
    check(len(set(bitmaps))==1,'Unexpected controller bitmap reference count.')
    return bitmaps[0]


def library_map(before,with_shapes=False):
    tags=list(swf_tags(before));definitions={}
    for kind,pos,size in tags:
        if kind in (2,22,32,39,20,36):definitions[struct.unpack_from('<H',before,pos)[0]]=(kind,pos,size)
    mapped={};shapes={}
    for name,cid,_ in swf_symbols(before):
        if not name.startswith('buttons.'):continue
        desc=descriptor(name)
        if not desc:continue
        kind,pos,size=definitions[cid]
        check(kind==39,'Unexpected exported controller definition.')
        chars=[]
        for tag,p,n,_ in records(before,pos+4,pos+size):
            if tag==26:
                flags=before[p]
                check(flags&2 and not flags&128,'Unexpected controller placement.')
                chars.append(struct.unpack_from('<H',before,p+3)[0])
        check(len(chars)==1,'Unexpected controller sprite structure.')
        shape,sp,sn=definitions[chars[0]]
        check(shape==2,'Unexpected controller shape version.')
        bitmap=bitmap_for_shape(before,sp,sn)
        state='pressed' if 'highlight' in name.lower() else 'normal'
        value=(desc,state)
        check(bitmap not in mapped or mapped[bitmap]==value,'A shared Flash bitmap has conflicting controller meanings.')
        mapped[bitmap]=value
        shapes[chars[0]]=(bitmap,desc,state)
    return (mapped,shapes) if with_shapes else mapped



def patch(original,bindings,expected):
    payload,frames=unframe(original);before=decode_swf(payload)
    mapping=library_map(before)
    check(len(mapping)==expected,'The keyboard Flash bitmap inventory changed.')
    after=bytearray(before);changed=0
    for kind,pos,size in swf_tags(before):
        if kind!=36 or size<7:continue
        cid=struct.unpack_from('<H',before,pos)[0]
        if cid not in mapping:continue
        check(before[pos+2]==5,'Unexpected controller bitmap storage format.')
        width,height=struct.unpack_from('<HH',before,pos+3)
        desc,state=mapping[cid]
        rgba=render(width,height,desc,bindings,state)
        compressed=None
        # Preserve the original format 5 ARGB bitmap, tag length, tag offset,
        # definition ID, dimensions, every shape and all ActionScript. Prefer
        # antialiasing; reduce color precision only to fit the existing slot.
        for alpha_levels,shades in [(8,(36,107,179,250)),(4,(36,107,179,250)),(2,(36,107,179,250)),(2,(36,250))]:
            pixels=bytearray(len(rgba))
            for i in range(0,len(rgba),4):
                gray= min(shades,key=lambda c:abs(c-rgba[i]))
                alpha=round(round(rgba[i+3]*(alpha_levels-1)/255)*255/(alpha_levels-1))
                value=(gray*alpha+127)//255
                pixels[i:i+4]=bytes((alpha,value,value,value))
            candidate=zlib.compress(pixels,9)
            if len(candidate)<=size-7:
                compressed=candidate;break
        check(compressed is not None,f'Key label does not fit bitmap {cid}. Nothing was written.')
        after[pos+7:pos+size]=compressed+b'\0'*(size-7-len(compressed))
        changed+=1
    check(changed==expected,'Not all keyboard bitmaps were generated.')
    check(list(swf_tags(before))==list(swf_tags(after)),'Flash tag offsets or lengths changed.')
    for kind,pos,size in swf_tags(before):
        cid=struct.unpack_from('<H',before,pos)[0] if size>=2 else -1
        if kind==36 and cid in mapping:
            check(before[pos:pos+7]==after[pos:pos+7],'Keyboard patch changed bitmap identity/dimensions.')
        else:check(before[pos:pos+size]==after[pos:pos+size],'Keyboard patch changed authored graphics or ActionScript.')
    rebuilt=payload[:8]+zlib.compress(after[8:],9)
    check(len(rebuilt)<=len(payload),'Keyboard bitmaps exceed the existing UI allocation. Nothing was written.')
    rebuilt+=b'\0'*(len(payload)-len(rebuilt))
    check(decode_swf(rebuilt)==after,'Keyboard Flash recompression failed verification.')
    result=bytearray(original)
    for stored,plain,length in frames:result[stored:stored+length]=rebuilt[plain:plain+length]
    check(unframe(result)[0]==rebuilt,'Keyboard Flash reframing failed verification.')
    return bytes(result)
