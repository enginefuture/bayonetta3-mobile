"""The cache chain must identify the stage interfaces actually translated."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_shaders',ROOT/'tools/build_shaders.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class ShaderPairs(unittest.TestCase):
    def test_graphics_edges_are_frozen_and_compute_does_not_change_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'raw';out=Path(tmp)/'snapshot'
            source.write_text('0:vs 1:ps 5:cs1\n0:vs 1:ps 5:cs2\n0:vs 2:gs\n1:orphan\n')
            builder.snapshot_pairs(source,out)
            self.assertEqual(out.read_text(),'0:vs 1:ps\n0:vs 2:gs\n')
            frozen=out.read_bytes();source.write_text('0:vs 1:new_fragment\n')
            self.assertEqual(out.read_bytes(),frozen)
            builder.snapshot_pairs(source,out)
            self.assertNotEqual(out.read_bytes(),frozen)

    def test_chain_hash_changes_with_pair_snapshot(self):
        path=ROOT/'third_party/blade2-mobile/dm/gfx/tools/dmsh_chain.py'
        spec=importlib.util.spec_from_file_location('dmsh_pair_chain',path)
        chain=importlib.util.module_from_spec(spec);spec.loader.exec_module(chain)
        with tempfile.TemporaryDirectory() as tmp:
            old_files,old_gfx=chain.FILES,chain.GFX
            try:
                chain.FILES=['pairs'];chain.GFX=tmp
                p=Path(tmp)/'pairs';p.write_text('0:vs 1:ps\n');first=chain.version()
                p.write_text('0:vs 1:ps\n0:vs 1:other\n')
                self.assertNotEqual(chain.version(),first)
            finally:chain.FILES,chain.GFX=old_files,old_gfx
        self.assertIn('nvn/shader_pairs.tsv',chain.FILES)

if __name__=='__main__':unittest.main()
