import unittest
from unittest.mock import Mock, patch
from agent.research_tools import search_web, read_page, public_url, ResearchToolError


class ResearchToolsTests(unittest.TestCase):
    def test_search_is_basic_and_excludes_linkedin(self):
        response = Mock()
        response.json.return_value = {'results': [
            {'url': 'https://example.com/team', 'title': 'Team', 'content': 'Snippet'},
            {'url': 'https://www.linkedin.com/in/example', 'title': 'Person', 'content': 'Snippet'}]}
        with patch.dict('os.environ', {'TAVILY_API_KEY': 'fake'}), patch('agent.research_tools.requests.post', return_value=response) as post:
            result = search_web('Example engineering team')
        self.assertEqual(len(result), 1)
        self.assertEqual(post.call_args.kwargs['json']['search_depth'], 'basic')
        self.assertNotIn('text', result[0])  # snippets are not inspected pages

    def test_page_must_be_discovered_and_have_content(self):
        with patch('agent.research_tools._post') as post:
            with self.assertRaises(ValueError):
                read_page('https://example.com/unknown', set())
            post.assert_not_called()
            post.return_value = {'results': [], 'failed_results': [{}]}
            with self.assertRaises(ResearchToolError):
                read_page('https://example.com/team', {'https://example.com/team'})
            post.return_value = {'results': [{'url': 'https://example.com/team', 'raw_content': 'Evidence'}]}
            self.assertEqual(read_page('https://example.com/team', {'https://example.com/team'})['text'], 'Evidence')

    def test_rejects_private_and_linkedin_urls(self):
        for url in ('file:///tmp/secret', 'http://127.0.0.1', 'http://localhost', 'https://user:pass@example.com', 'https://linkedin.com/in/test'):
            self.assertFalse(public_url(url), url)

    def test_malformed_search_is_not_no_contact(self):
        with patch('agent.research_tools._post', return_value={'results': [{}]}):
            with self.assertRaises(ResearchToolError): search_web('Company')

    def test_long_page_preserves_directory_and_supports_bounded_sections(self):
        from agent.research_tools import contact_sections, read_section
        url = 'https://example.com/about'
        content = 'Introduction. ' * 1500 + '\nMeet the team\nExample Person - Toronto Recruitment Consultant\n' + 'End. ' * 1000
        with patch('agent.research_tools._post', return_value={'results': [{'url': url, 'raw_content': content}]}):
            page = read_page(url, {url})
        self.assertEqual(page['text'], content)
        self.assertFalse(page['truncated'])
        self.assertTrue(any('Example Person' in s['text'] for s in contact_sections(page)))
        rebuilt = ''.join(read_section(page, s['id'])['text'] for s in page['sections'])
        self.assertEqual(rebuilt, content)
        self.assertTrue(all(len(read_section(page, s['id'])['text']) <= 4000 for s in page['sections']))
        with self.assertRaises(ValueError): read_section(page, 0)

    def test_directory_prioritization_is_stable(self):
        from agent.research_tools import prioritize_pages
        rows = [{'url': 'https://example.com/services'}, {'url': 'https://example.com/about'},
                {'url': 'https://example.com/team'}, {'url': 'https://example.com/articles/teamwork'}]
        self.assertEqual(prioritize_pages(rows), [rows[1], rows[2], rows[0], rows[3]])
