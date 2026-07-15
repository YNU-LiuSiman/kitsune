import csv
import importlib.util
import tempfile
import unittest
import subprocess
import sys
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
S = importlib.util.spec_from_file_location("runner", ROOT / "scripts" / "run_uci_experiment.py")
R = importlib.util.module_from_spec(S); S.loader.exec_module(R)

def make(folder, index=None, labels=1, header=False, quoted=False, bad=None, rows=8):
    f,l=folder/'f.csv',folder/'l.csv'
    with f.open('w',newline='') as a,l.open('w',newline='') as b:
        fw,lw=csv.writer(a),csv.writer(b)
        if header: fw.writerow((['idx'] if index is not None else [])+[f'f{i}' for i in range(115)]);lw.writerow(['idx','label'] if labels==2 else ['label'])
        for i in range(rows):
            x=[float(i)]*115
            if bad=='nan' and i==0:x[0]=float('nan')
            if bad=='inf' and i==0:x[0]=float('inf')
            fw.writerow(([i+index] if index is not None else [])+x)
            y=1 if bad=='poison' and i==0 else 0
            lw.writerow([i, f'"{y}"' if quoted else y] if labels==2 else [f'"{y}"' if quoted else y])
    return f,l

class TestPrecheck(unittest.TestCase):
    def test_115_dim_all_index_and_label_forms(self):
        for idx in (None,0,1):
            for labels in (1,2):
                with self.subTest(idx=idx,labels=labels),tempfile.TemporaryDirectory() as d:
                    f,l=make(Path(d),idx,labels,idx is not None,labels==2);c=R.precheck(f,l)
                    self.assertEqual((c['actual_feature_dim'],c['feature_rows'],c['label_rows'],c['index_col_detected']),(115,8,8,idx))
    def test_quotes_nan_inf_poison_and_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);f,l=make(p,labels=1,quoted=True);self.assertEqual(R.precheck(f,l)['unique_labels'],[0.0,1.0])
            f,l=make(p,bad='nan');self.assertGreater(R.precheck(f,l)['nan_count'],0)
            f,l=make(p,bad='inf');self.assertGreater(R.precheck(f,l)['inf_count'],0)
            f,l=make(p,bad='poison');self.assertEqual(R.precheck(f,l)['attack_in_first_55001'],1)
            with l.open('a') as x:x.write('0\n')
            with self.assertRaises(ValueError):R.precheck(f,l)

class TestRunnerIntegration(unittest.TestCase):
    def test_smoke_full_isolation_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); f,l=make(p,rows=55200,header=True)
            # execution period has both classes, but training period is all benign.
            with l.open('a',newline='') as z: pass
            with l.open('r',newline='') as z: data=list(csv.reader(z))
            for i in range(R.GRACE_ROWS+50,55200): data[i+1][-1]='1'
            with l.open('w',newline='') as z: csv.writer(z).writerows(data)
            out=p/'out'; runner=ROOT/'scripts'/'run_uci_experiment.py'
            def call(phase):
                env=os.environ.copy();env['KITSUNE_SYNTHETIC_TEST']='1'
                return subprocess.run([sys.executable,str(runner),'--attack','synthetic','--feature',str(f),'--labels',str(l),'--phase',phase,'--output-dir',str(out),'--no-overwrite'],capture_output=True,text=True,env=env)
            for phase,expected,rows in [('smoke-1000','smoke_passed',1000),('smoke-10000','smoke_passed',10000),('full','completed',55200)]:
                r=call(phase);self.assertEqual(r.returncode,0,r.stderr)
                folder=out/'uci'/'synthetic'/phase; status=json.loads((folder/'status.json').read_text()); metrics=json.loads((folder/'metrics.json').read_text())
                self.assertEqual(status['status'],expected);self.assertEqual((status['attack'],status['phase']),('synthetic',phase));self.assertEqual(metrics['total_rows'],rows)
                self.assertTrue(all((folder/x).exists() for x in ['manifest.json','config.json','precheck.json','status.json','metrics.json','source_hashes.json','raw/rmse.csv','raw/rmse_with_labels.csv','raw/sanitized_run_log.txt']))
                if phase.startswith('smoke'): self.assertEqual(metrics['execution_rows'],0);self.assertIsNone(metrics['roc_auc'])
                else:
                    self.assertEqual(metrics['execution_rows'],199);self.assertTrue(all(math.isfinite(metrics[x]) for x in ['roc_auc','pr_auc']));self.assertEqual(metrics['score_direction'],'higher_is_more_anomalous')
                    self.assertNotIn('accuracy',metrics);self.assertEqual(len((folder/'raw/rmse.csv').read_text().splitlines())-1,199);self.assertEqual(len((folder/'raw/rmse_with_labels.csv').read_text().splitlines())-1,199)
            before=(out/'uci'/'synthetic'/'smoke-1000'/'metrics.json').read_text();self.assertEqual(call('smoke-1000').returncode,0);self.assertEqual(before,(out/'uci'/'synthetic'/'smoke-1000'/'metrics.json').read_text())

if __name__=='__main__':unittest.main()
