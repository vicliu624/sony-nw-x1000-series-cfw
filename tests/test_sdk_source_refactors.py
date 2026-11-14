"""Structural splits need current semantic checks, never an implicit old-byte pass."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import audit_sdk_adoption as adoption
from sdk_services import service_files


class SourceRefactorTests(unittest.TestCase):
    def test_current_contract_records_every_split_source(self):
        report = adoption.audit(apps=['dictionary'])
        self.assertTrue(report['passed'], report['errors'])
        for targets in adoption.source_refactors().values():
            for target in targets:
                self.assertIn(target, report['source_hashes'])

    def test_split_is_not_claimed_as_historical_byte_equivalence(self):
        report = adoption.audit(check_logic=True, apps=['dictionary'])
        self.assertFalse(report['passed'])
        self.assertTrue(any('structural refactor requires semantic acceptance' in error
                            for error in report['errors']))

    def test_missing_or_escaped_targets_are_rejected(self):
        original = next(iter(adoption.source_refactors()))
        for target in ('runtime/platform/text/' + 'not-present.c', '../outside.c'):
            with self.subTest(target=target), patch.dict(
                    adoption.POLICY, {'source_refactors': {original: [target]}}):
                with self.assertRaises(ValueError):
                    adoption.source_refactors()

    def test_new_font_client_does_not_compile_lexicon_or_input(self):
        sources = service_files(['bitmap-font'])
        self.assertIn('runtime/platform/text/bitmap_font.c', sources)
        self.assertNotIn('runtime/platform/text/lexicon.c', sources)
        self.assertFalse(any(path.startswith('runtime/apps/') for path in sources))
        header = (ROOT / 'runtime/platform/text/bitmap_font.h').read_text(encoding='utf-8')
        self.assertNotIn('dx_open(', header)
        self.assertNotIn('dx_input', header)
        self.assertIn('runtime/platform/text/lexicon.c', service_files(['unicode-font']))


if __name__ == '__main__':
    unittest.main()
