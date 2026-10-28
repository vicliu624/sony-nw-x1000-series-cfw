"""Regenerate original launcher icons and Noto ASCII UI bitmap (PC only).

Requires Pillow 13.0.0 and the pinned Noto input from ci_bootstrap/build_release.
Normal builds consume committed output and do not need Pillow or an SVG decoder.
"""
from pathlib import Path
import hashlib, json, math
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
def artwork_items():
    from app_registry import applications
    return [(i, m["title"], m["artwork"]["subtitle"], m["artwork"]["color"], m["artwork"]["kind"])
            for i, m in applications().items() if "artwork" in m] + [("default", "Application", "Open application", "#74869b", "default")]

ITEMS = artwork_items()

def make_icon(color, kind):
    scale = 4
    im = Image.new('RGBA', (64*scale, 64*scale))
    d = ImageDraw.Draw(im)
    shapes = []
    def line(points, fill='#ffffff', width=3):
        d.line([(round(x*scale), round(y*scale)) for x,y in points], fill=fill, width=width*scale, joint='curve')
        for x,y in (points[0],points[-1]):
            r=width/2; d.ellipse(((x-r)*scale,(y-r)*scale,(x+r)*scale,(y+r)*scale),fill=fill)
        shapes.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{fill}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
    def box(x,y,w,h,r=0,fill='#ffffff'):
        d.rounded_rectangle((x*scale,y*scale,(x+w)*scale,(y+h)*scale),radius=r*scale,fill=fill)
        shapes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"/>')
    def circle(x,y,r,fill='#ffffff'):
        d.ellipse(((x-r)*scale,(y-r)*scale,(x+r)*scale,(y+r)*scale),fill=fill)
        shapes.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>')
    dark='#253f53'; pale='#e8f4f5'; white='#ffffff'
    # Original, small-screen silhouettes; no downloaded brand artwork.
    if kind=='bag':
        box(16,24,32,27,5,pale);line([(24,25),(24,20),(28,16),(36,16),(40,20),(40,25)],white,3)
        line([(32,31),(32,43)],color,3);line([(27,38),(32,43),(37,38)],color,3)
    elif kind=='player':
        box(21,12,22,40,5,pale);box(24,17,16,20,2,dark);circle(32,44,4,color);line([(29,23),(35,27),(29,31)],pale,2)
    elif kind=='pulse':
        box(12,17,40,30,5,pale);line([(17,33),(23,33),(27,24),(33,40),(38,29),(42,33),(47,33)],color,3)
    elif kind in ('book','dictionary'):
        box(13,16,18,33,3,pale);box(33,16,18,33,3,white)
        line([(32,18),(32,50)],color,2)
        for y in (25,31,37):line([(18,y),(26,y)],color,2);line([(38,y),(46,y)],color,2)
        if kind=='dictionary':box(39,12,8,13,1,'#f7d17d')
    elif kind=='radio':
        line([(21,22),(43,10)],pale,3);box(11,23,42,28,5,pale);box(16,28,32,6,2,dark)
        for x in (18,23,28):line([(x,39),(x,45)],color,2)
        circle(42,42,5,color);circle(42,42,2,pale)
    elif kind=='gameboy':
        box(19,10,27,44,6,pale);box(23,16,19,17,2,dark);box(26,19,13,10,1,'#a4c49c')
        line([(24,42),(32,42)],color,3);line([(28,38),(28,46)],color,3);circle(39,40,2,color);circle(42,45,2,color)
    elif kind=='graphics':
        box(14,17,35,32,5,pale);circle(25,28,5,'#f2c86e');line([(18,43),(28,33),(35,40),(42,31),(46,43)],color,3)
        circle(48,17,7,'#f1b4cf')
    elif kind=='wave':
        box(12,16,40,29,8,pale);line([(21,45),(21,51),(30,45)],pale,3)
        circle(24,29,2,color);circle(40,29,2,color);line([(26,35),(32,38),(38,35)],color,2)
    elif kind=='keys':
        box(14,20,36,28,8,pale);line([(20,33),(31,33)],color,3);line([(25.5,27.5),(25.5,38.5)],color,3)
        circle(40,29,3,color);circle(43,37,3,color)
    elif kind=='language':
        circle(32,32,20,pale);circle(32,32,17,color)
        line([(15,32),(49,32)],pale,2);line([(19,23),(45,23)],pale,2);line([(19,41),(45,41)],pale,2)
        line([(32,15),(24,23),(22,32),(24,41),(32,49),(40,41),(42,32),(40,23),(32,15)],pale,2)
    elif kind=='music':
        circle(32,33,21,pale);circle(45,19,7,'#ffda63')
        green='#159958'
        line([(28,40),(28,23),(41,20),(41,36)],green,4);line([(28,28),(41,25)],green,3)
        circle(23,42,6,green);circle(36,38,6,green)
    elif kind=='egg':
        circle(32,34,19,pale);box(18,18,28,27,12,pale);circle(26,31,2,color);circle(38,31,2,color)
        line([(28,39),(32,42),(36,39)],color,2);circle(23,37,3,'#efb9be');circle(41,37,3,'#efb9be')
    elif kind=='terminal':
        box(10,17,44,32,5,dark);box(13,20,38,3,1,pale);line([(18,30),(24,35),(18,40)],pale,3);line([(30,40),(39,40)],'#9be1c6',3)
        circle(46,12,2,pale);line([(40,8),(46,6),(52,8)],pale,2)
    elif kind=='pet':
        # Original monitor-robot silhouette with a dark edge for small displays.
        line([(32,17),(36,10),(42,10)],dark,3);circle(44,10,3,'#9be4ff')
        box(14,19,38,29,7,dark);box(13,17,38,29,7,pale)
        box(17,21,30,21,4,'#057dc5');box(23,27,3,5,1,dark);box(38,27,3,5,1,dark)
        circle(22,36,2,'#f5a5c9');circle(42,36,2,'#f5a5c9');line([(29,36),(32,38),(35,36)],pale,2)
        box(24,47,16,9,3,pale);box(28,49,8,4,1,color)
        line([(25,56),(22,59)],dark,3);line([(39,56),(42,59)],dark,3)
    else:
        for y in (19,35):
            for x in (19,35):box(x,y,11,11,3,pale)
    # Same SVG geometry, rasterized for the device without a runtime image decoder.
    tile=Image.new('RGBA',im.size)
    td=ImageDraw.Draw(tile); rgb=tuple(bytes.fromhex(color[1:]));
    for y in range(64*scale):
        f=y/(64*scale-1); tint=tuple(round(c+(255-c)*.12*(1-f)-c*.12*f) for c in rgb)
        td.line((0,y,64*scale,y),fill=(*tint,255))
    mask=Image.new('L',im.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,64*scale-1,64*scale-1),radius=14*scale,fill=255)
    tile.putalpha(mask);tile.alpha_composite(im)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="g" x2="0" y2="1"><stop stop-color="{color}"/><stop offset="1" stop-color="{color}" stop-opacity=".78"/></linearGradient></defs><rect width="64" height="64" rx="14" fill="url(#g)"/>'+''.join(shapes)+'</svg>\n'
    return tile,svg

def main():
    output=['/* Generated by tools/build_launcher_art.py. Original app artwork. */',
            '#ifndef HB_APP_ICONS_DATA_H','#define HB_APP_ICONS_DATA_H',
            'struct hb_app_art {const char *id,*title,*subtitle;const unsigned short *pixels;};']
    for ident,title,subtitle,color,kind in ITEMS:
        tile,svg=make_icon(color,kind);small=tile.resize((36,36),Image.Resampling.LANCZOS)
        ((ROOT/'runtime/native/assets' if ident=='default' else ROOT/'runtime/apps'/ident/'assets')/'icon.svg').write_text(svg)
        tile.resize((64,64),Image.Resampling.LANCZOS).save((ROOT/'runtime/native/assets' if ident=='default' else ROOT/'runtime/apps'/ident/'assets')/'icon.png')
        if ident!='default':continue
        values=[]
        for r,g,b,a in small.get_flattened_data():
            values.append(0 if a<128 else max(1,((r>>3)<<11)|((g>>2)<<5)|(b>>3)))
        output.append('static const unsigned short hb_icon_default[1296]={')
        output.extend(','.join(f'0x{x:04x}' for x in values[i:i+36])+',' for i in range(0,len(values),36))
        output.append('};')
    output.extend(['static const struct hb_app_art hb_app_artwork[]={',
                   '{"default","Application","Open application",hb_icon_default},','};','#endif',''])
    (ROOT/'runtime/native/app_icons_data.h').write_text('\n'.join(output))
    source=ROOT/'work/qqmusic-font/NotoSansCJKsc-Regular.otf'
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
    font=ImageFont.truetype(str(source),14)
    header=['/* Noto Sans CJK ASCII raster subset, SIL OFL 1.1. See third_party/qqmusic-stb/Noto-OFL.txt. */',
            '#ifndef HB_UI_FONT_H','#define HB_UI_FONT_H','static const unsigned char hb_ui_font[95][16][8]={']
    for cp in range(32,127):
        image=Image.new('L',(16,16));ImageDraw.Draw(image).text((0,-4),chr(cp),font=font,fill=255)
        header.append('{'+','.join('{'+','.join(str((image.getpixel((x,y))>>4)*16+(image.getpixel((x+1,y))>>4)) for x in range(0,16,2))+'}' for y in range(16))+'},')
    header.extend(['};','static const unsigned char hb_ui_advance[95]={'+','.join(str(round(font.getlength(chr(cp)))) for cp in range(32,127))+'};','#endif',''])
    (ROOT/'runtime/native/ui_font.h').write_text('\n'.join(header))
    print(json.dumps({'icons':len(ITEMS),'device_icon_size':36,'font':'Noto ASCII 14px','hardware_accessed':False}))

if __name__=='__main__':main()
