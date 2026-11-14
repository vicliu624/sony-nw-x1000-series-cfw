"""Public service implementations must not pull in an application's private source."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from sdk_services import inputs, manifest, resolve


class SharedDependencyTests(unittest.TestCase):
    def test_all_public_implementation_and_header_inputs_are_app_independent(self):
        modules = manifest()
        for name, module in modules.items():
            for path in module['sources'] + list(module.get('exports', {}).values()):
                self.assertFalse(path.startswith('runtime/apps/'), (name, path))
        dependencies = inputs({'resolved_modules': resolve(list(modules))})
        self.assertFalse([path.relative_to(ROOT).as_posix() for path in dependencies
                          if path.is_relative_to(ROOT / 'runtime/apps')])

    def test_audio_and_fm_have_distinct_implementation_owners(self):
        modules = manifest()
        self.assertEqual(modules['audio-route']['sources'], ['runtime/platform/audio/fm_audio.c'])
        self.assertTrue(all(path.startswith('runtime/platform/fm/')
                            for path in modules['fm']['sources']))
        self.assertIn('audio-route', resolve(['pcm']))
        self.assertIn('audio-route', resolve(['fm']))


if __name__ == '__main__':
    unittest.main()
