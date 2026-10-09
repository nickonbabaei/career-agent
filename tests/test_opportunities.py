import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.opportunities import run

class OpportunitiesTests(unittest.TestCase):
    def test_named_only_drafting_and_next_batch(self):
        old=os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                jobs=[{'id':i,'job':{},'decision':{'is_relevant':True}} for i in range(1,6)]
                found=dict(jobs=jobs,ranking=[{'id':i} for i in range(1,6)],found=5,assessed=5,unassessed=0,status='completed')
                researched={'status':'completed','jobs':[
                    {'rank':1,'status':'awaiting_recipient_choice','research':{'contact':{'name':'Alex'}}},
                    {'rank':2,'status':'awaiting_recipient_choice','research':{}},
                    {'rank':3,'status':'flagged','verification':{'concern':'flagged'},'research':{}}]}
                def draft(source,choices,profile):
                    values=json.loads(Path(choices).read_text())
                    self.assertEqual([v['mode'] for v in values.values()],['researched','skip','skip'])
                    return Path('drafts/messages'), {'status':'completed','jobs':[{'rank':1,'draft':{'body':'Hi Alex'},'research':{'contact':{'name':'Alex'}},'status':'drafted_pending_review'}]}
                with patch('agent.opportunities.run_workflow',return_value=(Path('drafts/search'),found)),patch('agent.opportunities.research',return_value=(Path('drafts/research'),researched)) as research,patch('agent.opportunities.draft',side_effect=draft):
                    directory,report=run(None)
                    self.assertEqual(research.call_args.kwargs['job_ids'],[1,2,3])
                    self.assertIn('draft',report['jobs'][0]['outreach'])
                    self.assertNotIn('draft',report['jobs'][1]['outreach'])
                with patch('agent.opportunities.research',return_value=(Path('drafts/research'),{'status':'completed','jobs':[]})) as research,patch('agent.opportunities.run_workflow') as discovery:
                    run(None,source=directory/'results.json')
                    discovery.assert_not_called()
                    self.assertEqual(research.call_args.kwargs['job_ids'],[4,5])
            finally: os.chdir(old)
