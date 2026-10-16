import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / 'benchmarks' / 'benchmark_eduai.py'
spec = importlib.util.spec_from_file_location('bench_eduai', PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TestMetrics(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(mod.percentile([1, 2, 3, 4, 5], 95), 4.8)
    def test_ns(self):
        self.assertEqual(mod.ns_to_s(2_000_000_000), 2.0)
    def test_summary_retrieval(self):
        measurements = [
            {'test':'retrieval','ok':True,'case_id':'a','wall_s':2,'found':True,'reciprocal_rank':1.0,'stage':'measure'},
            {'test':'retrieval','ok':True,'case_id':'b','wall_s':4,'found':False,'reciprocal_rank':0.0,'stage':'measure'}]
        item = mod.summarize(measurements)['global']
        self.assertEqual(item['hit_at_k'], .5)
        self.assertEqual(item['mrr_at_k'], .5)
    def test_warmup_not_mixed(self):
        measurements = [
            {'test':'ollama','ok':True,'model':'a','stage':'warmup','wall_s':20},
            {'test':'ollama','ok':True,'model':'a','stage':'measure','wall_s':2}]
        item = mod.summarize(measurements)['a']
        self.assertEqual(item['p50_s'], 2)
        self.assertEqual(item['runs'], 1)

if __name__=='__main__':
    unittest.main()
