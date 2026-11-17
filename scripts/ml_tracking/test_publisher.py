import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('publisher',Path(__file__).with_name('publisher.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_allowlist(self):
  x=m.clean({'status':'running','completed':3,'total':10,'metrics':{'loss':1.2,'secret':'token'},'clients':['private'],'pid':123,'transcript':'private'}, {'id':'r','label':'Run'})
  self.assertEqual(x['metrics'],{'loss':1.2});self.assertNotIn('clients',x);self.assertNotIn('pid',x);self.assertNotIn('transcript',x)
 def test_multiple_pipelines(self):
  with tempfile.TemporaryDirectory() as d:
   Path(d,'a.json').write_text(json.dumps({'status':'complete','completed':10,'total':10}))
   cfg={'pipelines':[{'id':p,'label':p,'base_dir':d,'adapter':'summary_json','runs':[{'id':'a','label':'a','path':'a.json'}]} for p in ['first','second']]}
   out=m.snapshot(cfg);self.assertEqual(len(out['pipelines']),2);self.assertTrue(all(p['status']=='complete' for p in out['pipelines']))
 def test_queued_and_interrupted(self):
  with tempfile.TemporaryDirectory() as d:
   spec={'id':'x','label':'x','path':'run','arms':['B','C'],'rounds':100}
   self.assertEqual(m.fl_run(spec,Path(d))['status'],'queued')
   Path(d,'run').mkdir();Path(d,'run/status.json').write_text('{"state":"running","stage":"FL_B","pid":999999999}')
   self.assertEqual(m.fl_run(spec,Path(d))['status'],'interrupted')
if __name__=='__main__':unittest.main()
