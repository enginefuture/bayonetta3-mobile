"""Validate captured NVN pairs before classifying or translating code."""
import hashlib
import struct

LAYOUTS={12:0x838,14:0x848,15:0x850,16:0x880}
STAGES={1:'vs',2:'tcs',3:'tes',4:'gs',5:'ps'}

def capture_stage(key,control,code):
    if len(control)<0x24:raise ValueError('short control')
    magic,major,minor=struct.unpack_from('<3I',control)
    declared=struct.unpack_from('<I',control,0x20)[0]
    if magic!=0x98761234 or major!=1 or LAYOUTS.get(minor)!=declared or len(control)!=declared:
        raise ValueError('unknown control layout')
    if hashlib.sha256(control).hexdigest()[:16]!=key:raise ValueError('control hash mismatch')
    c1,total=struct.unpack_from('<2I',control,0x700)
    if not total or total>0x400000 or len(code)!=total or c1>total:
        raise ValueError(f'incomplete code: expected {total}, got {len(code)}')
    if code[:4]==bytes.fromhex('78563412'):
        if len(code)<0x80:raise ValueError('short graphics header')
        kind=(struct.unpack_from('<I',code,0x30)[0]>>10)&15
        if kind not in STAGES:raise ValueError(f'unknown graphics stage {kind}')
        return STAGES[kind]
    if not all(struct.unpack_from('<3I',control,0x748)):raise ValueError('invalid compute workgroup')
    return 'cs'
