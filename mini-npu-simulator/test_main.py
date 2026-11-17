import contextlib
import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
import main

ROOT = Path(__file__).parent


class SimulatorTests(unittest.TestCase):
    def test_mac_reference(self):
        a,b=main.generate(3)
        self.assertEqual(main.mac(a,a),5)
        self.assertEqual(main.mac(a,b),1)
        self.assertEqual(main.decide(1,5,('A','B')),'B')

    def test_labels(self):
        for source,target in [('+','Cross'),('cross','Cross'),('Cross','Cross'),(' x ','X'),('X','X')]:
            self.assertEqual(main.normalize(source),target)
        with self.assertRaises(ValueError): main.normalize('unknown')

    def test_epsilon(self):
        self.assertEqual(main.decide(0.1+0.2,0.3),'UNDECIDED')
        self.assertEqual(main.decide(0,0.999e-9),'UNDECIDED')
        self.assertEqual(main.decide(0,1e-9),'X')

    def test_matrix_validation(self):
        for invalid in ([], [[1]], [[1,2],[3]], [[True,0],[0,1]], [[float('nan'),0],[0,1]], [['1',0],[0,1]]):
            with self.assertRaises(ValueError): main.matrix(invalid,2)

    def test_all_sizes_and_flatten(self):
        for n in (3,5,13,25):
            a,b=main.generate(n)
            self.assertEqual(main.mac(a,a),2*n-1)
            self.assertEqual(main.mac(a,b),1)
            self.assertEqual(main.mac(a,b),main.mac_flat(sum(a,[]),sum(b,[])))

    def test_sample_counts(self):
        with contextlib.redirect_stdout(io.StringIO()):
            rows=main.analyze(json.loads((ROOT/'data.json').read_text(encoding='utf-8')))
        self.assertEqual(len(rows),8)
        self.assertEqual(sum(r[1] for r in rows),7)
        self.assertEqual([r[0] for r in rows if not r[1]],['size_13_3'])

    def test_invalid_case_continuation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            rows=main.analyze(json.loads((ROOT/'fixtures/invalid.json').read_text()))
        self.assertEqual([r[1] for r in rows],[False,False,False,True,False])

    def test_filter_error_continuation(self):
        doc=json.loads((ROOT/'data.json').read_text())
        doc['filters']['size_5']['cross']=[[0]]
        with contextlib.redirect_stdout(io.StringIO()): rows=main.analyze(doc)
        self.assertFalse(rows[0][1])
        self.assertTrue(rows[2][1])

    def test_interactive_retry(self):
        data='1\n1 2\na b c\n0 1 0\n1 1 1\n0 1 0\n1 0 1\n0 1 0\n1 0 1\n1 0 1\n0 1 0\n1 0 1\n'
        p=subprocess.run([sys.executable,str(ROOT/'main.py')],input=data,text=True,capture_output=True,encoding='utf-8',env=dict(__import__('os').environ,PYTHONIOENCODING='utf-8'))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('판정: B',p.stdout)
        self.assertEqual(p.stdout.count('입력 오류:'),2)

    def test_missing_file_and_malformed_json(self):
        p=subprocess.run([sys.executable,str(ROOT/'main.py'),'--mode','2','--data',str(ROOT/'missing.json')],capture_output=True)
        self.assertEqual(p.returncode,2)
        with self.assertRaises(ValueError): main.analyze([])

    def test_numeric_overflow(self):
        with self.assertRaises(ValueError): main.mac([[1e308]],[[1e308]])

    def test_benchmark(self):
        with contextlib.redirect_stdout(io.StringIO()): rows=main.benchmark([3,5,13,25],10)
        self.assertEqual([r[2] for r in rows],[9,25,169,625])


if __name__=='__main__': unittest.main(verbosity=2)
