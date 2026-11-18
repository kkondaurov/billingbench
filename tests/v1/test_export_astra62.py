from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_astra62 import measure_code


class Astra62Export(unittest.TestCase):
    def test_counts_python_billing_worker_as_production(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('lib/app.ex', 'priv/billing/worker.py', 'test/app_test.exs', 'priv/settings.json'):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('one line\n')
            code = measure_code(root)
        self.assertEqual((code['production'], code['test']), (2, 1))
        self.assertEqual(
            {f['path'] for f in code['files'] if f['category'] == 'production'},
            {'lib/app.ex', 'priv/billing/worker.py'},
        )
