"""Exercise production reflection with translator resource/MSL fixtures."""
import ast
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'third_party/blade2-mobile/dm/gfx/tools/dmsh_build.py'

class ShaderAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The build entry point invokes external compilers at import time.
        # Load its pure reflection function without running that entry point.
        tree=ast.parse(SOURCE.read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='reflect')
        scope={'re':re,'decode_tex':lambda name:(1,None,0)}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(SOURCE),'exec'),scope)
        cls.reflect=staticmethod(scope['reflect'])

    def test_buffer_write_flag_matches_translator_enum(self):
        for flags,writes in ((0,False),(1,True)):
            msl='struct spvDescriptorSetBuffer0 {\n device Data* fp_s0 [[id(2)]];\n};'
            resource={'sbufs':[{'binding':0,'cb_slot':0,'cb_offset':0x510//4,'flags':flags}]}
            binding=self.reflect('test','ps',msl,resource)[0]
            self.assertEqual((binding['kind'],binding['reg'],binding['rw']),('sbuf',0,writes))

    def test_image_access_reaches_runtime_reflection(self):
        for access,writes in (('read',False),('write',True),('read_write',True)):
            msl='struct spvDescriptorSetBuffer0 {\n texture2d<float, access::'+access+'> fp_i_cb2_4A_ [[id(0)]];\n};'
            binding=self.reflect('test','ps',msl,{'sbufs':[]})[0]
            self.assertEqual((binding['kind'],binding['reg'],binding['rw']),('img',1,writes))
