"""Parent-side records must survive aborts and distinguish failure from watchdogs."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from run_diagnostics import classify_exit, execute


class RunDiagnostics(unittest.TestCase):
    def test_missing_media_is_not_an_unexplained_abort(self):
        row=classify_exit(-6,'[dm] FATAL prepared H.264 movie missing for source local.webm')
        self.assertEqual(row['reason'],'missing_movie_cache')
        self.assertFalse(row['gameplay_pass'])

    def test_active_tessellation_has_its_own_failure_category(self):
        row=classify_exit(-6,'[dm] [nvn-mtl] FATAL NVN tessellation patch draw unsupported: patch_size=3 TCS=0123456789abcdef TES=fedcba9876543210; original stage translation required')
        self.assertEqual(row['reason'],'unsupported_tessellation')
        self.assertEqual(row['tessellation'],{'patch_size':3,'tcs':'0123456789abcdef','tes':'fedcba9876543210'})
        self.assertFalse(row['gameplay_pass'])
        self.assertEqual(classify_exit(0,'Bound tessellation stage retained')['reason'],'normal_exit')

    def test_tessellation_completion_and_new_failure_modes(self):
        row=classify_exit(0,'[nvn-mtl] [tessellation] frame=2380 draws=1 patches=24 instances=7 VS=1111111111111111_tv TCS=2222222222222222_tc TES=3333333333333333_te GPU=0.071ms')
        self.assertEqual(row['reason'],'normal_exit')
        self.assertEqual(row['completed_tessellation_samples'][0]['instances'],7)
        self.assertEqual(row['completed_tessellation_samples'][0]['gpu_ms'],.071)
        self.assertFalse(row['gameplay_pass'])
        self.assertEqual(classify_exit(-6,'FATAL Invalid tessellation library 1111111111111111_te: missing')['reason'],'unsupported_tessellation')
        self.assertEqual(classify_exit(-6,'FATAL Tessellation GPU failure: timeout')['reason'],'metal_gpu_failure')
        self.assertEqual(classify_exit(-6,'FATAL TES/fragment pipeline mismatch')['reason'],'metal_pipeline_failure')

    def test_watchdog_and_nonfatal_warning(self):
        self.assertEqual(classify_exit(142,'[dm] CRASH sig=14',True)['reason'],'diagnostic_timeout')
        self.assertEqual(classify_exit(-14,'',True)['reason'],'diagnostic_timeout')
        self.assertEqual(classify_exit(0,'[dm] 【红】one warning')['reason'],'normal_exit')
        self.assertEqual(classify_exit(-11,'')['reason'],'signal_SIGSEGV')

    def test_real_child_failure_writes_persistent_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'native.log'
            command=[sys.executable,'-c','import sys; print("FATAL prepared H.264 movie missing",file=sys.stderr); sys.exit(7)']
            self.assertEqual(execute(command,os.environ,log,{},timeout=5),7)
            row=json.loads(log.with_suffix('.summary.json').read_text())
            self.assertEqual(row['reason'],'missing_movie_cache')
            self.assertEqual(row['returncode'],7)
            session=json.loads(log.with_suffix('.session.json').read_text())
            self.assertEqual(session['status'],'exited')
            events=[json.loads(s)['event'] for s in log.with_suffix('.events.jsonl').read_text().splitlines()]
            self.assertEqual(events,['session_start','process_started','process_exited'])


if __name__=='__main__':unittest.main()
