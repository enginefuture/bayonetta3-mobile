"""Guarded SPIRV-Cross ABI lowering for native triangle tessellation.

Preserves translated bodies. Buffer layouts are explicit and independently GPU
checked; unsupported interfaces fail instead of dropping a programmable stage.
"""
import hashlib
import json
import re
import struct

CONTROL_POINT_BYTES=33*16
CANONICAL='\n'+''.join(f'    float4 dm_v{i};\n' for i in range(32))+'    float4 gl_Position;\n'

TES_LANE_HELPER='''
// Exact physical lane: prefix rank indexes the active ballot, including holes.
// Both operations execute at entry, before any original shader divergence.
inline uint dm_tess_lane_id()
{
    ulong active = ulong(simd_vote::vote_t(simd_ballot(true)));
    uint rank = simd_prefix_exclusive_sum(1u);
    for (uint i = 0; i < rank; ++i) active &= active - 1ul;
    return uint(ctz(active));
}
'''

def prepare_tes_subgroups(binary):
    """Move the unsupported TES lane attribute to an entry-initialized private.

    Leaves original loads, arithmetic, control flow and shuffle instructions
    unchanged. SPIRV-Cross then threads the private through helper functions.
    The generated private is initialized from Metal's physical active-lane mask.
    """
    execution_modes(binary) # Validate the instruction stream before editing.
    words=list(struct.unpack('<%dI'%(len(binary)//4),binary));ins=[];i=5
    while i<len(words):
        n=words[i]>>16;ins.append(words[i:i+n]);i+=n
    ids=[x[1] for x in ins if x[0]&65535==71 and len(x)==4 and x[2:]==[11,41]]
    if not ids:return binary,False
    if len(ids)!=1 or any(x[1]!=2 for x in ins if x[0]&65535==15):raise ValueError('Unsupported TES subgroup declaration')
    lane=ids[0];var=next((x for x in ins if x[0]&65535==59 and x[2]==lane),None)
    pointer=next((x for x in ins if x[0]&65535==32 and x[1]==var[1]),None) if var else None
    scalar=next((x for x in ins if x[0]&65535==21 and pointer and x[1]==pointer[3]),None)
    if not var or len(var)!=4 or var[3]!=1 or not pointer or not scalar or scalar[2:]!=[32,0]:raise ValueError('Unsupported subgroup lane type/storage')
    if any(x[0]&65535==62 and x[1]==lane for x in ins):raise ValueError('Subgroup lane is unexpectedly written')
    private_pointer=words[3];words[3]+=1;output=[];named=False
    name=b'dm_subgroup_lane\0';name+=bytes((-len(name))%4)
    name_words=list(struct.unpack('<%dI'%(len(name)//4),name))
    for x in ins:
        op=x[0]&65535
        if op==5 and x[1]==lane:continue
        if not named and op in (71,72,19,20,21,22):
            output.append([(2+len(name_words))<<16|5,lane,*name_words]);named=True
        if op==71 and x[1]==lane:
            if x[2:]!=[11,41]:raise ValueError('Unexpected subgroup lane decoration')
            continue
        if op==15:
            end=3
            while end<len(x) and 0 not in struct.pack('<I',x[end]):end+=1
            if end==len(x):raise ValueError('Unterminated entry name')
            x=x[:end+1]+[v for v in x[end+1:] if v!=lane];x[0]=len(x)<<16|15
        if x is var:
            output.append([4<<16|32,private_pointer,6,pointer[3]])
            x=[4<<16|59,private_pointer,lane,6]
        output.append(x)
    if not named:raise ValueError('Missing SPIR-V declaration section')
    flat=words[:5]+[w for x in output for w in x]
    return struct.pack('<%dI'%len(flat),*flat),True

def initialize_tes_subgroup(source):
    # This local is generated from the private variable introduced above. It
    # must be assigned before any helper using the original lane ID runs.
    source,n=re.subn(r'\buint dm_subgroup_lane(?:\s*=\s*0u)?;',
                     'uint dm_subgroup_lane = dm_tess_lane_id();',source)
    if n!=1:raise ValueError('Unexpected lowered TES subgroup variable')
    index=source.index('using namespace metal;')+len('using namespace metal;')
    return source[:index]+'\n'+TES_LANE_HELPER+source[index:]

def execution_modes(binary):
    if len(binary)<20 or len(binary)%4 or struct.unpack_from('<I',binary)[0]!=0x07230203:raise ValueError('Invalid SPIR-V header')
    words=struct.unpack('<%dI'%(len(binary)//4),binary);modes={};i=5
    while i<len(words):
        size,op=words[i]>>16,words[i]&65535
        if not size or i+size>len(words):raise ValueError('Invalid SPIR-V instruction')
        if op==16:
            if size<3:raise ValueError('Invalid SPIR-V execution mode')
            modes[words[i+2]]=list(words[i+3:i+size])
        i+=size
    return modes

def canonical(source,reflection,direction):
    name='main0_'+('in' if direction=='inputs' else 'out')
    m=re.search(r'struct '+name+r'\s*\{(.*?)\};',source,re.S)
    if not m:raise ValueError('Missing cross-stage structure '+name)
    fields={}
    for v in reflection.get(direction,[]):
        if v.get('type')!='vec4' or not 0<=v.get('location',-1)<32:raise ValueError('Unsupported tessellation interface')
        field='m'+v['name'] if v['name'].startswith('_') else v['name']
        if not re.search(r'\bfloat4 '+re.escape(field)+r'\b',m[1]):raise ValueError('SPIR-V/MSL interface mismatch')
        fields[field]='dm_v'+str(v['location'])
    # Point size has no consumer in this control-point ABI. Never discard clip,
    # cull, layer, viewport or patch outputs that would require a wider layout.
    body=re.sub(r'\[\[.*?\]\]','',m[1]);decls=re.findall(r'\b(\w+)\s+(\w+)\s*;',body)
    allowed=set(fields)|{'gl_Position','gl_PointSize'}
    if len(decls)!=body.count(';') or any(n not in allowed for t,n in decls):raise ValueError('Unsupported tessellation built-in interface')
    source=source[:m.start(1)]+CANONICAL+source[m.end(1):]
    access=r'gl_in\[[^;\n]+?\]' if direction=='inputs' else r'(?:out|gl_out\[[^;\n]+?\])'
    for old,new in fields.items():
        # Input and output structs can reuse a member name at different
        # locations. Rename only accesses to the structure being lowered.
        source=re.sub(r'(\b'+access+r'\.)'+re.escape(old)+r'\b',lambda m:m[1]+new,source)
    if 'gl_PointSize' in body:
        source,n=re.subn(r'\s*out\.gl_PointSize\s*=\s*[^;]+;','',source)
        if 'gl_PointSize' in source:raise ValueError('Point-size tessellation interface is consumed')
    return source

def lower(source,reflection,stage,output_points=3):
    if output_points!=3:raise ValueError('Only verified three-output-point triangle tessellation is supported')
    if stage=='vs':
        if re.search(r'\bgl_Vertex(?:Index|ID)\b',source):raise ValueError('Indexed tessellation vertex-ID reconstruction is not implemented')
        source=canonical(source,reflection,'outputs')
        if 'uint3 spvDispatchBase [[grid_origin]]' in source:
            source=source.replace('uint3 spvDispatchBase [[grid_origin]]','constant uint* dm_params [[buffer(3)]]')
            source=source.replace('\n{\n    device main0_out& out', '\n{\n    uint3 spvDispatchBase=uint3(dm_params[4],dm_params[3],0);\n    device main0_out& out',1)
        pattern=r'(device main0_out& out = spvOut\[[^;]+;)'
        source,n=re.subn(pattern,r'\1\n    out = {};',source)
        if n!=1 or 'kernel void main0' not in source:raise ValueError('Expected vertex-for-tessellation compute output')
    elif stage=='tcs':
        source=canonical(source,reflection,'inputs');source=canonical(source,reflection,'outputs')
        if 'threadgroup_barrier' in source:raise ValueError('Cross-invocation TCS barriers require a separately validated dispatch')
        if 'edgeTessellationFactor[3]' in source or 'insideTessellationFactor[1]' in source:raise ValueError('TCS consumes quad factors')
        source=source.replace('MTLQuadTessellationFactorsHalf','MTLTriangleTessellationFactorsHalf').replace('.insideTessellationFactor[0]','.insideTessellationFactor')
        if 'MTLTriangleTessellationFactorsHalf' not in source:raise ValueError('TCS has no triangle tessellation factors')
        # The multi-patch representation linearizes instances into the buffers.
        # Shader primitive ID itself is local to the instance.
        pattern='uint gl_PrimitiveID = min(gl_GlobalInvocationID.x / 3, spvIndirectParams[1] - 1);'
        if pattern not in source:raise ValueError('Unknown TCS primitive-ID ABI')
        source=source.replace(pattern,'uint dm_patch = min(gl_GlobalInvocationID.x / 3, spvIndirectParams[1] - 1);\n    uint gl_PrimitiveID = dm_patch % spvIndirectParams[2];')
        source=source.replace('spvTessLevel[gl_PrimitiveID]','spvTessLevel[dm_patch]')
    elif stage=='tes':
        source=canonical(source,reflection,'inputs')
        required=['[[ patch(triangle, 0) ]]','&spvIn[gl_PrimitiveID * 0]','uint gl_PatchVerticesIn = 0;']
        if not all(s in source for s in required):raise ValueError('Unknown raw triangle TES ABI')
        source=source.replace(required[0],'[[ patch(triangle, 3) ]]').replace(required[1],'&spvIn[((dm_instance - dm_params[3]) * dm_params[2] + gl_PrimitiveID) * 3]').replace(required[2],'uint gl_PatchVerticesIn = 3;')
        source,n=re.subn(r'(vertex main0_out main0\([^\n]+)(\)\n\{)',r'\1, uint dm_instance [[instance_id]], constant uint* dm_params [[buffer(3)]]\2',source)
        if n!=1:raise ValueError('Unknown TES entry')
        # Same complete output ABI as regular vertices, preserving all original
        # stores; unwritten outputs follow the existing zero initialization.
        m=re.search(r'struct main0_out\s*\{(.*?)\};',source,re.S)
        existing={int(x) for x in re.findall(r'user\(locn(\d+)\)',m[1])}
        extra=''.join(f'    float4 dm_unused{i} [[user(locn{i})]];\n' for i in range(14) if i not in existing)
        source=source[:m.end(1)]+extra+source[m.end(1):]
    else:raise ValueError('Unknown tessellation stage')
    for a,b in ((28,2),(29,3),(26,4),(22,1)):
        source=source.replace(f'[[buffer({a})]]',f'[[buffer({b})]]')
    return source

def bindings(source):
    """Current tessellation corpus has cbufs and sampled resources only."""
    m=re.search(r'struct spvDescriptorSetBuffer0\s*\{(.*?)\};',source,re.S);out=[]
    for ty,name,aid in re.findall(r'^\s*(.+?)\s+(\w+)\s*\[\[id\((\d+)\)\]\];',m[1] if m else '',re.M):
        b={'msl_name':name,'msl_type':ty,'arg_id':int(aid)}
        c=re.fullmatch(r'[a-z]+_c(\d+)',name)
        if c:
            n=int(c[1])
            if 3<=n<=16:b.update(kind='cbuf',reg=n-3)
            elif n==1:b.update(kind='c1')
            else:raise ValueError('Tessellation driver constant bank is not implemented')
        elif name=='support_buffer':b.update(kind='support')
        else:
            # NVN combined handle c2[0x20+8*slot], decoded independently from
            # the original translator resource record (not a hard-coded texture).
            t=re.fullmatch(r'[a-z]+_t_tcb_([0-9A-F]+)(Smplr)?',name)
            if not t:raise ValueError('Unsupported tessellation resource '+name)
            handle=int(t[1],16)
            if handle>>28 or not 0x20<=handle*4<0x120 or (handle*4-0x20)%8:raise ValueError('Unsupported tessellation handle namespace')
            b.update(kind='samp_tex' if t[2] else 'tex',reg=(handle*4-0x20)//8)
        out.append(b)
    return out


def verify_receipt(directory,chain):
    from pathlib import Path
    directory=Path(directory);root=Path(__file__).resolve().parents[1]
    report=json.loads((directory/'_tessellation.json').read_text())
    if report.get('schema')!=1 or report.get('chain')!=chain or not report.get('pairs') or not report.get('files'):raise ValueError('Invalid tessellation receipt')
    for pair in report['pairs']:
        if len(pair)!=3 or any(not re.fullmatch(r'[0-9a-f]{16}',key) for key in pair):raise ValueError('Invalid tessellation stage combination')
        for key,suffix in zip(pair,('tv','tc','te')):
            if key in report.get('unsupported',{}) or any(key+'_'+suffix+ext not in report['files'] for ext in ('.metal','.metallib','.json')):raise ValueError('Incomplete observed tessellation combination')
    for key,path in [('builder_sha256',root/'tools/build_tessellation.py'),('lowering_sha256',Path(__file__))]:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=report.get(key):raise ValueError('Tessellation builder/lowering changed; rebuild supplement')
    for name,digest in report['files'].items():
        if Path(name).name!=name or hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:raise ValueError('Changed/missing tessellation library '+name)
    actual={x.name for x in directory.iterdir() if x.is_file() and not x.name.startswith('_')}
    if actual!=set(report['files']):raise ValueError('Unverified tessellation supplement files')
    return report
