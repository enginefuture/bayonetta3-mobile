#!/usr/bin/env python3
"""Prepare an isolated AVC cache for original VP9/WebM cutscenes; keep originals."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def probe(p):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-count_frames','-show_entries','stream=codec_name,width,height,nb_read_frames,r_frame_rate,color_space,color_range:format=duration',
        '-of','json',str(p)],text=True))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--cache',type=Path,default=ROOT/'work/media')
    a=p.parse_args();source=a.input.resolve()
    if not source.is_file():p.error('input must be an existing local movie')
    a.cache.mkdir(parents=True,exist_ok=True);sha=digest(source);out=a.cache/(sha+'.mp4')
    if not out.exists():
        temp=a.cache/(sha+'.partial.mp4')
        subprocess.run(['ffmpeg','-v','error','-i',str(source),'-c:v','h264_videotoolbox','-b:v','20M',
            '-pix_fmt','yuv420p','-fps_mode','passthrough','-c:a','aac','-b:a','256k','-movflags','+faststart','-y',str(temp)],check=True)
        temp.rename(out)
    original,converted=probe(source),probe(out)
    x,y=original['streams'][0],converted['streams'][0]
    if x.get('codec_name')!='vp9' or x.get('color_space')!='bt709' or x.get('color_range')!='tv':
        p.exit(1,'Current native movie adapter requires VP9 BT.709 studio range; source profile differs\n')
    if y['codec_name']!='h264' or any(x[k]!=y[k] for k in ('width','height','nb_read_frames','r_frame_rate')):
        p.exit(1,'Converted video shape/frame timing mismatch; cache not verified\n')
    if abs(float(original['format']['duration'])-float(converted['format']['duration']))>0.05:
        p.exit(1,'Converted movie duration differs by more than 50 ms\n')
    receipt={'source':str(source),'source_sha256':sha,'output_sha256':digest(out),
        'original':original,'converted':converted,'method':'AVC VideoToolbox 20 Mbps; AAC audio; original frame cadence'}
    (a.cache/(sha+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'Prepared {out}; {y["nb_read_frames"]} frames. Original retained; this is codec conversion, not game execution evidence.')
if __name__=='__main__':main()
