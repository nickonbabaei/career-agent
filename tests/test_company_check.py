import unittest
from agent.company_check import validate_check
from agent.contact_research import eligible_title
from agent.research_runtime import ResearchError

class CompanyCheckTests(unittest.TestCase):
    def test_evidence_and_linked_ats_required(self):
        official='https://example.com/careers'
        ats='https://jobs.example-ats.com/123'
        value=dict(concern='none',concern_url='',concern_quote='',identity='confirmed',listing='confirmed',company_name='Example',official_url=official,company_quote='Example builds apps.',listing_url=ats,listing_quote='Engineer in Toronto',reason='Matching role')
        pages=[{'url':official,'text':'Example builds apps. '+ats},{'url':ats,'text':'Engineer in Toronto'}]
        self.assertEqual(validate_check(value,pages)['listing'],'confirmed')
        pages[0]['text']='Example builds apps.'
        result=validate_check(value,pages)
        self.assertEqual(result['listing'],'not_confirmed')
        self.assertEqual(result['listing_url'],'')
        self.assertTrue(result['validation_notes'])
        missing=validate_check(value,[])
        self.assertEqual(missing['identity'],'unclear')
        self.assertEqual(missing['company_name'],'')
        value.update(listing='not_confirmed',listing_url='',listing_quote='')
        self.assertEqual(validate_check(value,pages)['listing'],'not_confirmed')

    def test_executive_exclusion(self):
        for title in ['CEO','Vice President Engineering','Director of Engineering','Co-founder','CTO']:
            self.assertFalse(eligible_title(title))
        self.assertTrue(eligible_title('Software Engineer'))
        self.assertTrue(eligible_title('Technical Recruiter'))

    def test_concern_requires_inspected_quote(self):
        value=dict(identity='unclear', listing='not_confirmed', company_name='',
                   official_url='', company_quote='', listing_url='', listing_quote='',
                   reason='Official disavowal', concern='flagged',
                   concern_url='https://example.com/notice', concern_quote='This listing impersonates us.')
        with self.assertRaises(ResearchError):
            validate_check(value, [])
        self.assertEqual(validate_check(value, [{'url':value['concern_url'], 'text':value['concern_quote']}])['concern'], 'flagged')
