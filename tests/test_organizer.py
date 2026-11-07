import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from organizer import ConfigError, folder_for, load_config, safe_folder, validate_url


class OrganizerTests(unittest.TestCase):
    def test_exact_and_subdomain_rules(self):
        rules = {'github.com': 'GitHub', 'docs.github.com': 'Documentation'}
        self.assertEqual(folder_for('github.com', rules, 'Other'), 'GitHub')
        self.assertEqual(folder_for('docs.github.com', rules, 'Other'), 'Documentation')
        self.assertEqual(folder_for('gist.github.com', rules, 'Other'), 'GitHub')
        self.assertEqual(folder_for('notgithub.com', rules, 'Other'), 'Other')

    def test_folder_traversal_rejected(self):
        for name in ('../secrets', '/tmp', 'A/B', '', '..'):
            with self.assertRaises(ConfigError):
                safe_folder(name)

    def test_unsafe_urls_rejected(self):
        for url in ('http://example.com', 'https://localhost/', 'https://127.0.0.1/',
                    'file:///etc/passwd', 'https://user:pass@example.com', 'https://example.com:8443'):
            with self.assertRaises(ConfigError):
                validate_url(url)

    def test_example_config(self):
        config = load_config(Path(__file__).resolve().parents[1] / 'config.example.json')
        self.assertIn('github.com', config['rules'])


if __name__ == '__main__':
    unittest.main()
