"""Prevent new stage pairings from depending on encounter order or stale caches."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('interfaces',ROOT/'tools/shader_interfaces.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Interfaces(unittest.TestCase):
    def test_unseen_pair_requires_complete_union(self):
        vs={'old':{1:'float4',3:'float4'}}
        fs={'previous':{1:'float4'},'unseen':{3:'float4',4:'float4'}}
        with self.assertRaisesRegex(ValueError,'old.*4'):m.check_coverage(vs,fs)
        vs['old'][4]='float4'
        self.assertEqual(m.check_coverage(vs,fs),{1:'float4',3:'float4',4:'float4'})
        fs['wrong_type']={4:'uint4'}
        with self.assertRaisesRegex(ValueError,'type conflict'):m.check_coverage(vs,fs)

    def test_parser_direction_qualifiers_and_no_inputs(self):
        src='struct main0_out { float4 uv [[user(locn4)]]; float4 p [[position]]; };\nstruct main0_in { uint4 v [[user(locn1), flat]]; };'
        self.assertEqual(m.varyings(src,'out'),{4:'float4'})
        self.assertEqual(m.varyings(src,'in'),{1:'uint4'})
        self.assertEqual(m.varyings('', 'in'),{})
        with self.assertRaisesRegex(ValueError,'Duplicate'):m.varyings('struct main0_in { float4 a [[user(locn1)]]; float4 b [[user(locn1)]]; };','in')

    def test_receipt_rejects_stale_or_mixed_chain_libraries(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            for key,stage,direction in [('vertex','vs','out'),('fragment','ps','in')]:
                (d/(key+'.json')).write_text(json.dumps({'stage':stage,'chain':'test'}))
                (d/(key+'.metal')).write_text('struct main0_'+direction+' { float4 v [[user(locn4)]]; };')
                (d/(key+'.metallib')).write_bytes(b'synthetic test bytes')
            (d/'_b_build.json').write_text('[]');(d/'_varying_scan.json').write_text('{}')
            self.assertEqual(m.build_receipt(d,'test')['vertices'],1)
            self.assertEqual(m.verify_receipt(d,'test')['fragments'],1)
            extra=d/'new.json';extra.write_text(json.dumps({'stage':'vs'}))
            with self.assertRaisesRegex(ValueError,'Unverified'):m.verify_receipt(d,'test')
            extra.unlink()
            variant=d/'fragment_bf.metallib';variant.write_bytes(b'unverified variant')
            with self.assertRaisesRegex(ValueError,'Unverified'):m.verify_receipt(d,'test')
            variant.unlink()
            (d/'vertex.metallib').write_bytes(b'old cache')
            with self.assertRaisesRegex(ValueError,'stale'):m.verify_receipt(d,'test')
            with self.assertRaisesRegex(ValueError,'chain'):m.build_receipt(d,'other')
