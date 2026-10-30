"""Read-only parsers for the observed Japanese X1000 STX and TGP/TXD resources."""
import struct

STX_MAGIC = b"content-type: text/stx\n\n"

def parse_stx(data):
    if len(data)<56 or not data.startswith(STX_MAGIC):
        raise ValueError("Invalid STX header")
    table,count=struct.unpack_from("<II",data,44)
    if table!=56 or not 0<count<=20000 or table+count*4>len(data):
        raise ValueError("Invalid STX index")
    offsets=struct.unpack_from("<"+str(count)+"I",data,table)
    texts=[]
    for off in offsets:
        if off == 0:
            texts.append("")
            continue
        if off<table+count*4 or off%2 or off>=len(data):
            raise ValueError("Invalid STX text offset")
        end=off
        while end+1<len(data) and data[end:end+2]!=b"\0\0":
            end+=2
        if end+1>=len(data):
            raise ValueError("Unterminated STX text")
        texts.append(data[off:end].decode("utf-16-le",errors="strict"))
    return texts

def append_stx(data, text):
    """Append one indexed string, preserving all original strings and trailing bytes.

    JP1.11 loader uses header+52 for mapping length. Moving the offset table
    requires relocating every nonzero string offset, not overwriting a spare ID.
    """
    original = parse_stx(data)
    if not text or '\0' in text:
        raise ValueError('New STX text must be nonempty and contain no NUL')
    table, count, mapped = struct.unpack_from('<III', data, 44)
    if mapped > len(data) or count >= 20000:
        raise ValueError('Unsupported STX size/count')
    end = table + count * 4
    offsets = struct.unpack_from('<' + str(count) + 'I', data, table)
    encoded = text.encode('utf-16-le') + b'\0\0'
    result = bytearray(data[:table])
    result += struct.pack('<' + str(count + 1) + 'I',
                          *[offset + 4 if offset else 0 for offset in offsets], len(data) + 4)
    result += data[end:] + encoded
    struct.pack_into('<II', result, 48, count + 1, len(result))
    if parse_stx(result) != original + [text]:
        raise ValueError('STX append did not preserve original strings')
    return bytes(result), count

def parse_tgp(data):
    if len(data)<32 or data[:4]!=b"TGP\0" or data[4:8]!=b"\1\0\0\0":
        raise ValueError("Invalid TGP header")
    start,count=struct.unpack_from(">II",data,8)
    total=struct.unpack_from(">I",data,28)[0]
    if start!=32 or count>10000 or total!=len(data):
        raise ValueError("Invalid TGP bounds")
    out=[]
    off=start
    for index in range(count):
        if off+32>len(data) or data[off:off+4]!=b"TXD\0":
            raise ValueError("Invalid TXD record")
        width,height,fmt,_,_,_,size=struct.unpack_from(">7I",data,off+4)
        if not width or not height or width>4096 or height>4096 or off+32+size>len(data):
            raise ValueError("Invalid TXD bounds")
        if fmt in (2,16) and size!=width*height*(2 if fmt==2 else 4):
            raise ValueError("Unexpected raw texture size")
        out.append({"index":index,"offset":off,"width":width,"height":height,"format":fmt,"bytes":size})
        off=(off+32+size+15)&~15
    if off!=len(data):
        raise ValueError("Unexpected TGP trailing data")
    return out

def append_bgra_texture(data, width, height, pixels):
    """Append a raw BGRA8888 TXD; preserve every original texture byte."""
    records=parse_tgp(data)
    if len(pixels)!=width*height*4 or not 0<width<=4096 or not 0<height<=4096:
        raise ValueError('Invalid BGRA texture')
    result=bytearray(data)
    result+=b'TXD\0'+struct.pack('>7I',width,height,16,0,0,0,len(pixels))+pixels
    result+=bytes((-len(result))%16)
    struct.pack_into('>I',result,12,len(records)+1)
    struct.pack_into('>I',result,28,len(result))
    if bytes(result[32:len(data)])!=data[32:] or len(parse_tgp(result))!=len(records)+1:
        raise ValueError('Original texture preservation failed')
    return bytes(result),len(records)
