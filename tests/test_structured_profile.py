import tempfile
import unittest
from pathlib import Path
from dataclasses import asdict
import yaml
from agent.profile import load_profile, ProfileConfigError

class StructuredProfileTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.yaml'
            path.write_text(yaml.safe_dump(data))
            return load_profile(path)

    def test_round_trip_preserves_roles_and_attribution(self):
        data = dict(name='Example', target_roles=['Engineer'], locations=['Toronto'], work_experience=[dict(title='Engineer', company='Example Co', start_date='2024', end_date='2025', achievements=['Built a prototype.'])], education=['Math degree'], projects=['Demo app'], skills=['Python'])
        profile = self.load(data)
        self.assertIn('Engineer at Example Co (2024 – 2025): Built a prototype.', profile.background_facts)
        self.assertEqual(asdict(self.load(asdict(profile))), asdict(profile))
        self.assertEqual(profile.experience_bullets, [])

    def test_legacy_facts_unchanged(self):
        data = dict(name='Example', target_roles=['Engineer'], locations=['Toronto'], experience_bullets=['Original fact'])
        self.assertEqual(self.load(data).background_facts, ['Original fact'])

    def test_invalid_role_rejected(self):
        data = dict(name='Example', target_roles=['Engineer'], locations=['Toronto'], work_experience=[dict(title='Engineer', company='', achievements=[])])
        with self.assertRaises(ProfileConfigError):
            self.load(data)
