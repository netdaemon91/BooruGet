import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from booruget.config import load_credentials, save_credentials, user_config_dir
from booruget.models import Credentials


class ConfigTests(unittest.TestCase):
    def test_roundtrip_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "booruget.ini"
            original = Credentials("dan", "dk", "123", "gk")
            save_credentials(original, path)
            self.assertEqual(load_credentials(path), original)

    def test_windows_config_uses_appdata(self):
        with patch("booruget.config.sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": r"C:\\Users\\Test\\AppData\\Roaming"}):
            value = str(user_config_dir())
            self.assertIn("BooruGet", value)
            self.assertIn("AppData", value)


if __name__ == "__main__":
    unittest.main()
