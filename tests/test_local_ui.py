import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from server import app
from server import credentials


class LocalUITests(unittest.TestCase):
    def test_run_paths_cannot_escape(self):
        for name in ('../profile/profile.yaml', '/tmp/example', 'run-../../', None):
            with self.assertRaises(ValueError):
                app.run_dir(name)

    def test_active_run_prevents_second_worker(self):
        with patch.object(app, 'PROCESS') as process:
            process.poll.return_value = None
            with self.assertRaises(RuntimeError):
                app.start_run({'mode': 'search'})

    def test_missing_keys_prevent_subprocess(self):
        with patch.object(app, 'PROCESS', None), patch('server.app.load_profile'), patch('server.credentials.saved_keys', return_value={}), patch.dict('os.environ', {}, clear=True), patch('server.app.subprocess.Popen') as worker:
            with self.assertRaises(ValueError):
                app.start_run({'mode': 'search', 'max_jobs': 10})
            worker.assert_not_called()

    def test_keys_persist_merge_and_status_never_returns_values(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(credentials, 'STORE', Path(tmp) / 'private/keys.json'), patch.dict('os.environ', {}, clear=True):
            credentials.save_keys({'GEMINI_API_KEY': 'fictional-gemini'})
            credentials.save_keys({'GEMINI_API_KEY': '', 'TAVILY_API_KEY': 'fictional-tavily'})
            self.assertEqual(credentials.worker_environment()['GEMINI_API_KEY'], 'fictional-gemini')
            self.assertEqual(credentials.key_status(), {'GEMINI_API_KEY': True, 'TAVILY_API_KEY': True, 'OPENWEBNINJA_API_KEY': False})
            self.assertEqual(credentials.STORE.stat().st_mode & 0o777, 0o600)
            before = credentials.STORE.read_text()
            with self.assertRaises(ValueError):
                credentials.save_keys({'UNKNOWN': 'secret'})
            self.assertEqual(credentials.STORE.read_text(), before)
