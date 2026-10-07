"""Offline drafting contract checks; live factual/wording quality needs review."""
import json
import unittest
from unittest.mock import Mock, patch
from agent.drafting import draft_outreach, DraftingError, CONTACT_INSTRUCTIONS
from agent.models import Profile, JobPosting


class ContactDraftingChecks(unittest.TestCase):
    def test_named_and_fallback_greetings_and_source_context(self):
        job = JobPosting('Engineer', 'Example Agency', 'Toronto', 'Recruiting for an unnamed client', 'https://example.com/job')
        profile = Profile('Candidate', ['Engineer'], ['Toronto'], ['Built a prototype'])
        contact = {'name': 'Alex Example', 'title': 'AI Consultant', 'organization': 'Example Agency',
                   'relationship': 'recruiter', 'public_url': 'https://example.com/team',
                   'evidence': [{'url': 'https://example.com/team', 'excerpt': 'Alex Example - AI Consultant'}]}
        for selected, greeting in ((contact, 'Hi Alex Example,'), (None, 'Hi Hiring team,')):
            response = Mock()
            response.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps({'subject': 'Engineer opening', 'body': greeting + '\n\nI built a prototype. Who handles the advertised role?'})}]}}]}
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake'}), patch('agent.drafting.requests.post', return_value=response) as post:
                draft = draft_outreach(job, profile, selected)
            self.assertTrue(draft.body.startswith(greeting))
            context = json.loads(post.call_args.kwargs['json']['contents'][0]['parts'][0]['text'])
            self.assertEqual(context['profile']['experience_bullets'], ['Built a prototype'])
            self.assertEqual('contact' in context, selected is not None)
        self.assertIn('unnamed client', CONTACT_INSTRUCTIONS)
        self.assertIn('authored a page', CONTACT_INSTRUCTIONS)
