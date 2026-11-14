"""Compilation metadata is read-only input; syntax checks must not emit objects."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_core2_syntax as syntax


class Core2SyntaxCommandTests(unittest.TestCase):
    def test_compile_and_dependency_outputs_are_removed(self):
        command = ['cross-g++', '-c', '-MMD', '-MP', '-MF', 'main.d', '-MTmain.o',
                   '-o', 'main.o', '-std=gnu++20', '-Iinclude', 'main.cpp']
        checked = syntax.syntax_arguments(command)
        self.assertEqual(checked, ['cross-g++', '-std=gnu++20', '-Iinclude',
                                   'main.cpp', '-fsyntax-only'])

    def test_unreviewed_output_modes_are_rejected(self):
        for extra in ('@response.txt', '-save-temps', '-save-temps=obj', '-o'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                syntax.syntax_arguments(['cross-g++', extra])

    def test_existing_database_is_read_without_running_platformio(self):
        parent = ROOT / 'work/core2-syntax-command-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            root = Path(directory)
            project = root / 'project'
            (project / 'src').mkdir(parents=True)
            source = project / 'src/main.cpp'
            source.write_text('int main() { return 0; }\n')
            compiler = root / 'cross-g++.exe'
            compiler.write_bytes(b'not executed')
            database = root / 'compile_commands.json'
            entry = {'directory': str(project), 'file': str(source), 'command': 'fixture'}
            database.write_text(json.dumps([entry]), encoding='utf-8')
            before = database.read_bytes()
            arguments = [str(compiler), '-c', str(source), '-o', 'main.o']
            with patch.object(syntax, 'PROJECT', project), \
                 patch.object(syntax, 'windows_arguments', return_value=arguments), \
                 patch.object(syntax.subprocess, 'run') as run:
                selected, command = syntax.load_command(database)
                self.assertEqual(selected, entry)
                self.assertEqual(command, [str(compiler), str(source), '-fsyntax-only'])
                run.assert_not_called()
            self.assertEqual(database.read_bytes(), before)
            database.write_text(json.dumps([entry, entry]), encoding='utf-8')
            with patch.object(syntax, 'PROJECT', project), self.assertRaises(ValueError):
                syntax.load_command(database)


if __name__ == '__main__':
    unittest.main()
