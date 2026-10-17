"""Bayonetta NVN alpha-test lowering; pure MSL transformation."""
import re

def title_depth_bounds(src):
    """Test a GPU snapshot of stored depth before fragment side effects."""
    signature=re.search(r'fragment\s+(?:main0_out|void)\s+main0\(',src)
    if not signature:raise ValueError('depth bounds: unknown fragment signature')
    endmatch=re.search(r'\)\s*\{',src[signature.end():])
    if not endmatch:raise ValueError('depth bounds: unknown body')
    end=signature.end()+endmatch.start();args=src[signature.end():end]
    if '[[buffer(26)]]' in src or '[[texture(0)]]' in src:raise ValueError('depth bounds: resource slot conflict')
    position=re.search(r'float4\s+(\w+)\s*\[\[position\]\]',args)
    extra=[]
    if position:name=position.group(1)
    else:name='dm_depth_position';extra.append('float4 '+name+' [[position]]')
    extra+=['constant float4& dm_depth_range [[buffer(26)]]','texture2d<float> dm_depth_image [[texture(0)]]']
    addition=(', ' if args.strip() else '')+', '.join(extra)
    src=src[:end]+addition+src[end:];start=src.find('{',end+len(addition))
    guard='\n    if(dm_depth_range.x!=0.0f){float stored=dm_depth_image.read(uint2('+name+'.xy)).x;if(!(stored>=dm_depth_range.y && stored<=dm_depth_range.z))discard_fragment();}\n'
    return src[:start+1]+guard+src[start+1:]


def title_alpha_test(src):
    """Apply dynamic alpha test to primary color, before depth/stencil commit."""
    src=src.replace('[[early_fragment_tests]]','')
    signature=re.search(r'fragment\s+(main0_out|void)\s+main0\(',src)
    if not signature:raise ValueError('alpha test: unknown fragment signature')
    endmatch=re.search(r'\)\s*\{',src[signature.end():])
    if not endmatch or '[[buffer(27)]]' in src:raise ValueError('alpha test: signature/slot conflict')
    end=signature.end()+endmatch.start()
    sep=', ' if src[signature.end():end].strip() else ''
    arg=sep+'constant uint2& dm_alpha [[buffer(27)]]'
    src=src[:end]+arg+src[end:]
    member=re.search(r'float4 (\w+) \[\[color\(0\)\]\];',src)
    if member:
        alpha='out.'+member.group(1)+'.w'
        test=f'{{ uint f=dm_alpha.x;float a={alpha},r=as_type<float>(dm_alpha.y);bool pass=f==8 || (f==2 && a<r) || (f==3 && a==r) || (f==4 && a<=r) || (f==5 && a>r) || (f==6 && a!=r) || (f==7 && a>=r);if(!pass)discard_fragment(); }}'
    else:test='{ if(dm_alpha.x==1)discard_fragment(); }'
    start=src.find('{',end+len(arg));depth=1;close=start+1
    while close<len(src) and depth:
        depth+=(src[close]=='{')-(src[close]=='}');close+=1
    if depth:raise ValueError('alpha test: unbalanced entry body')
    body=src[start+1:close-1]
    if signature.group(1)=='void':
        body=body.replace('return;',test+' return;')+'\n    '+test+'\n'
    else:
        if 'return out;' not in body:raise ValueError('alpha test: no output return')
        body=body.replace('return out;',test+'\n    return out;')
    return src[:start+1]+body+src[close-1:]
