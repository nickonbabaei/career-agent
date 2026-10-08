import json
import tempfile
import unittest
from pathlib import Path
from agent.shortlist_outreach import selected_jobs

class JobSelectionTests(unittest.TestCase):
    def test_explicit_selection_supports_assessed_override_only(self):
        job=dict(title='Engineer', company='Example', location='Toronto', description='Build apps', source_url='https://example.com/job')
        report={'found':3,'jobs':[{'id':1,'job':job,'decision':{'is_relevant':True,'reason':'Fit'}},{'id':2,'job':job,'decision':{'is_relevant':False,'reason':'Gap'}},{'id':3,'job':job}],'shortlist':[{'id':1}]}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'results.json'
            path.write_text(json.dumps(report))
            self.assertEqual(selected_jobs(path, job_ids=[2])[0][0], 2)
            for ids in ([],[1,1],[3],[999],[True],['1']):
                with self.assertRaises(ValueError): selected_jobs(path, job_ids=ids)
            self.assertEqual(json.loads(path.read_text()),report)
