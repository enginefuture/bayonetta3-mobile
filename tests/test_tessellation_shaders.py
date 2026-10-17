"""Synthetic interfaces and cache corruption must fail without game inputs."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from tessellation_shaders import canonical, execution_modes, lower, verify_receipt,prepare_tes_subgroups,initialize_tes_subgroup


class TessellationShaders(unittest.TestCase):
    def test_lane_lowering_preserves_original_load_and_shuffle(self):
        def ins(op,*args):return [(len(args)+1)<<16|op,*args]
        words=[0x07230203,0x10300,0,14,0]
        instructions=[ins(15,2,10,0x6e69616d,0,7),ins(71,7,11,41),ins(19,1),
          ins(21,2,32,0),ins(32,3,1,2),ins(59,3,7,1),ins(33,4,1),ins(43,2,8,3),
          ins(43,2,9,0),ins(54,1,10,0,4),ins(248,11),ins(61,2,12,7),
          ins(345,2,13,8,12,9),ins(253),ins(56)]
        original=words+[w for x in instructions for w in x]
        output,enabled=prepare_tes_subgroups(struct.pack('<%dI'%len(original),*original));self.assertTrue(enabled)
        changed=list(struct.unpack('<%dI'%(len(output)//4),output));decoded=[];i=5
        while i<len(changed):n=changed[i]>>16;decoded.append(changed[i:i+n]);i+=n
        self.assertIn(ins(61,2,12,7),decoded);self.assertIn(ins(345,2,13,8,12,9),decoded)
        self.assertNotIn(ins(71,7,11,41),decoded);self.assertIn(ins(59,14,7,6),decoded)
        self.assertEqual(next(x for x in decoded if x[0]&65535==15),ins(15,2,10,0x6e69616d,0))
        again,enabled=prepare_tes_subgroups(output);self.assertFalse(enabled);self.assertEqual(again,output)
        text='using namespace metal;\nvoid main0(){uint dm_subgroup_lane;float result=sin(2.0f)*3.0f;}'
        result=initialize_tes_subgroup(text);self.assertIn('float result=sin(2.0f)*3.0f;',result)
        self.assertIn('uint dm_subgroup_lane = dm_tess_lane_id();',result)
        with self.assertRaises(ValueError):initialize_tes_subgroup(text.replace('dm_subgroup_lane','unknown'))

    def test_sparse_control_points_share_locations_and_preserve_math(self):
        source='struct main0_out {float4 position0; float4 gl_Position;};\n'
        source=source.replace('position0','value')+'''kernel void main0(uint3 gl_GlobalInvocationID [[thread_position_in_grid]], uint3 spvDispatchBase [[grid_origin]], device main0_out* spvOut [[buffer(28)]])
{
    device main0_out& out = spvOut[gl_GlobalInvocationID.x];
    out.value = float4(2.0, 3.0, 4.0, 5.0) * 0.75;
}
'''
        result=lower(source,{'outputs':[{'name':'value','type':'vec4','location':7}]},'vs')
        self.assertIn('out.dm_v7 = float4(2.0, 3.0, 4.0, 5.0) * 0.75;',result)
        self.assertIn('out = {};',result)
        self.assertIn('dm_params[3]',result)
        self.assertIn('[[buffer(2)]]',result)
        self.assertEqual(result.count('float4 dm_v'),32)
        for reflection in ({'outputs':[{'name':'value','type':'vec3','location':7}]},
                           {'outputs':[{'name':'value','type':'vec4','location':32}]}):
            with self.assertRaises(ValueError):lower(source,reflection,'vs')
        with self.assertRaises(ValueError):canonical('struct main0_out {float4 gl_Position; uint gl_Layer;};',{},'outputs')
        with self.assertRaises(ValueError):lower(source.replace('out.value =','uint gl_VertexIndex = 0; out.value ='),{},'vs')

    def test_tes_addresses_patch_per_instance_and_retains_output_interface(self):
        source='''struct main0_in {float4 value; float4 gl_Position;};
struct main0_out {float4 value [[user(locn7)]]; float4 gl_Position [[position]];};
[[ patch(triangle, 0) ]]
vertex main0_out main0(device const main0_in* spvIn [[buffer(22)]], uint gl_PrimitiveID [[patch_id]])
{
    const device main0_in* gl_in = &spvIn[gl_PrimitiveID * 0];
    uint gl_PatchVerticesIn = 0;
    main0_out out = {};
    out.value = gl_in[2].value;
    return out;
}
'''
        result=lower(source,{'inputs':[{'name':'value','type':'vec4','location':7}]},'tes')
        self.assertIn('[[ patch(triangle, 3) ]]',result)
        self.assertIn('((dm_instance - dm_params[3]) * dm_params[2] + gl_PrimitiveID) * 3',result)
        self.assertIn('out.value = gl_in[2].dm_v7;',result)
        for i in range(14):self.assertEqual(result.count(f'[[user(locn{i})]]'),1)
        with self.assertRaises(ValueError):lower(source.replace('triangle','quad'),{},'tes')
        with self.assertRaises(ValueError):lower(source,{},'tes',4)

    def test_spirv_modes_reject_truncation_and_bad_instruction(self):
        header=[0x07230203,0x10000,0,10,0]
        valid=struct.pack('<9I',*header,(4<<16)|16,1,26,3)
        self.assertEqual(execution_modes(valid),{26:[3]})
        for data in (b'',valid[1:],valid[:-4],struct.pack('<6I',*header,16),struct.pack('<7I',*header,(2<<16)|16,1)):
            with self.assertRaises(ValueError):execution_modes(data)

    def test_receipt_requires_complete_combinations_and_unchanged_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);keys=['1'*16,'2'*16,'3'*16];files={}
            for key,suffix in zip(keys,('tv','tc','te')):
                for ext in ('.metal','.metallib','.json'):
                    name=key+'_'+suffix+ext;(directory/name).write_text('synthetic artifact\n')
                    files[name]=hashlib.sha256((directory/name).read_bytes()).hexdigest()
            report={'schema':1,'chain':'fixture','pairs':[keys],'files':files,
                    'builder_sha256':hashlib.sha256((ROOT/'tools/build_tessellation.py').read_bytes()).hexdigest(),
                    'lowering_sha256':hashlib.sha256((ROOT/'tools/tessellation_shaders.py').read_bytes()).hexdigest()}
            receipt=directory/'_tessellation.json';receipt.write_text(json.dumps(report))
            self.assertEqual(verify_receipt(directory,'fixture')['pairs'],[keys])
            name=next(iter(files));(directory/name).write_text('changed')
            with self.assertRaises(ValueError):verify_receipt(directory,'fixture')
            (directory/name).write_text('synthetic artifact\n')
            (directory/'extra.metallib').touch()
            with self.assertRaises(ValueError):verify_receipt(directory,'fixture')
            (directory/'extra.metallib').unlink()
            del report['files'][name];receipt.write_text(json.dumps(report))
            with self.assertRaises(ValueError):verify_receipt(directory,'fixture')


if __name__=='__main__':unittest.main()
