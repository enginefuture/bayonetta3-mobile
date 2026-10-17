import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_run import frame_metrics, gpu_passes


class RunAnalysisTests(unittest.TestCase):
    def test_frame_statistics_ignore_missing_and_malformed_samples(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'frames.tsv'
            p.write_text('# capped capture\nframe\tname\tms\n'
                         '1\t@frame_ms\t16\n2\t@frame_ms\t48\n'
                         '3\t@frame_ms\t-1\n4\t@frame_ms\tnan\n'
                         '5\t@frame_ms\tbad\n6\tdraw\t100\npartial\n')
            self.assertEqual(frame_metrics(p),{'@frame_ms':{'samples':2,'p50':32,'p95':48,'max':48}})

    def test_overlapping_passes_are_ranked_without_summing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'passes.tsv'
            p.write_text('# precise diagnostic\nframe\tsubmission\tkind\tspan_ms\n'
                         '60\t1\tR\t8\n60\t1\tC\t5\n60\t1\tR\t-1\n'
                         '60\t1\tR\tNaN\n60\t1\tR\tinf\n')
            result=gpu_passes(p)
            self.assertEqual(result['rows'],5)
            self.assertEqual(result['unavailable_spans'],3)
            self.assertEqual([r['span_ms'] for r in result['largest_observed_spans']],[8,5])
            self.assertNotIn('total_ms',result)
