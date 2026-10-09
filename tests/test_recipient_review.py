import json
import os
import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
from agent.models import JobPosting, Profile, Draft
from agent.shortlist_outreach import run as research_run
from agent.reviewed_drafting import validate_choices, run as draft_run


class RecipientReviewTests(unittest.TestCase):
    def test_research_stops_then_confirmed_manual_choice_drafts(self):
        job=JobPosting('Engineer','Example','Toronto','Build apps','https://example.com/job')
        profile=Profile('Example',['Engineer'],['Toronto'],['Built a prototype'])
        source={'found':1,'jobs':[{'id':1,'job':asdict(job),'decision':{'is_relevant':True,'reason':'fit'}}],'shortlist':[{'id':1}]}
        cwd=os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path('source.json').write_text(json.dumps(source))
                with patch.dict(os.environ,{'GEMINI_API_KEY':'fake','TAVILY_API_KEY':'fake'}), patch('agent.shortlist_outreach.check_company',return_value={'identity':'unclear','listing':'not_confirmed','concern':'none'}), patch('agent.shortlist_outreach.research_contact',return_value=None) as contacts, patch('agent.shortlist_outreach.draft_outreach') as drafting:
                    directory,report=research_run('source.json',profile,research_only=True)
                contacts.assert_called_once()
                drafting.assert_not_called()
                self.assertEqual(report['stage'],'contact_review')
                with self.assertRaises(ValueError): validate_choices(report,{})
                with self.assertRaises(ValueError): validate_choices(report,{'1':{'mode':'researched'}})
                with self.assertRaises(ValueError): validate_choices(report,{'1':{'mode':'skip'}})
                with self.assertRaises(ValueError): validate_choices(report,{'1':{'mode':'generic'}})
                Path('choices.json').write_text(json.dumps({'1':{'mode':'manual','confirmed':True,'contact':{'name':'Alex','title':'Engineer','organization':'Example','relationship':'employee'}}}))
                with patch('agent.reviewed_drafting.draft_outreach',return_value=Draft(job,'Hello','Hi Hiring team,')) as drafted:
                    output,result=draft_run(directory/'results.json','choices.json',profile)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(drafted.call_args.args[2]['name'],'Alex')
                self.assertEqual(json.loads((directory/'results.json').read_text()),report)
            finally: os.chdir(cwd)

    def test_manual_contact_requires_confirmation_and_remains_unverified(self):
        job=JobPosting('Engineer','Example','Toronto','Build','https://example.com/job')
        report={'stage':'contact_review','status':'completed','jobs':[{'rank':1,'job':asdict(job)}]}
        choice={'mode':'manual','contact':{'name':'Alex','title':'Engineer','organization':'Example','relationship':'employee'}}
        with self.assertRaises(ValueError): validate_choices(report,{'1':choice})
        choice['confirmed']=True
        contact=validate_choices(report,{'1':choice})[0][2]
        self.assertEqual(contact['source'],'user_supplied')
        self.assertEqual(contact['evidence'],[])
        report['jobs'][0]['verification'] = {'concern':'flagged'}
        with self.assertRaisesRegex(ValueError, 'authenticity concern'):
            validate_choices(report, {'1':choice})
