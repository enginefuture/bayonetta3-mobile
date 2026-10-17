import ast
import os
from pathlib import Path
import shlex
import unittest

PATH=Path(__file__).resolve().parents[1]/'third_party/blade2-mobile/dm/ios/tools/gen_build.py'
tree=ast.parse(PATH.read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='parse_commands')
namespace={'os':os,'shlex':shlex};exec(compile(ast.Module(body=[function],type_ignores=[]),str(PATH),'exec'),namespace)

class IOSInputs(unittest.TestCase):
    def test_incremental_compile_and_link_commands(self):
        output='''mkdir -p objects
clang -I. -DAPP=1 -c one.c -o one.o
clang -I. -DAPP=1 -c main.c -o main.o
clang -I ../include -DOTHER=2 -c ../gfx/metal.m -o metal.o
clang one.o main.o metal.o -framework Cocoa -framework Metal -o host
'''
        src,inc,defs,frameworks=namespace['parse_commands'](output,'/host')
        self.assertEqual(src,['/host/one.c','/host/main.c','/gfx/metal.m'])
        self.assertEqual(inc,['/host','/include'])
        self.assertEqual(defs,['-DAPP=1','-DOTHER=2'])
        self.assertEqual(frameworks,['Cocoa','Metal'])

    def test_original_single_compile_command(self):
        src,_,defs,fw=namespace['parse_commands']('clang -DNAME=\'"Game Name"\' a.c b.m c.S -framework Metal -o host','/host')
        self.assertEqual(src,['/host/a.c','/host/b.m','/host/c.S'])
        self.assertEqual(defs,['-DNAME="Game Name"']);self.assertEqual(fw,['Metal'])
