from io import BytesIO
import unittest
from unittest.mock import patch
from pypdf import PdfWriter
from agent.resume import extract_text, propose_background, validate_background
from agent.research_runtime import ResearchError

class ResumeTests(unittest.TestCase):
    def test_invalid_and_blank_pdfs_never_call_model(self):
        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        stream = BytesIO()
        writer.write(stream)
        with patch('agent.resume.model_json') as model:
            for raw in (b'not a PDF', stream.getvalue(), b'%PDF-' + b'x' * (5*1024*1024)):
                with self.assertRaises(ValueError):
                    propose_background(raw, 'fake')
            model.assert_not_called()

    def test_preview_only_contains_background(self):
        value = dict(name='Example', work_experience=[], projects=['Built a demo'], education=[], skills=[], experience_bullets=[])
        with patch('agent.resume.extract_text', return_value='Example built a demo'), patch('agent.resume.model_json', return_value=value) as model:
            result = propose_background(b'pdf', 'fake')
        self.assertEqual(result['background'], value)
        self.assertNotIn('target_roles', result['background'])
        self.assertEqual(model.call_args.kwargs['api_key'], 'fake')

    def test_malformed_output_retries_once(self):
        with patch('agent.resume.extract_text', return_value='Resume text'), patch('agent.resume.model_json', return_value={}) as model, patch('agent.research_runtime.time.sleep'):
            with self.assertRaises(ResearchError):
                propose_background(b'pdf', 'fake')
        self.assertEqual(model.call_count, 2)

    def test_encrypted_pdf_rejected(self):
        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        writer.encrypt('password')
        stream = BytesIO()
        writer.write(stream)
        with self.assertRaisesRegex(ValueError, 'password'):
            extract_text(stream.getvalue())
