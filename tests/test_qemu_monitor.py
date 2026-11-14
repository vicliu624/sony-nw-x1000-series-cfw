"""A readline command echo is not the final HMP prompt."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from qemu_monitor import read_prompt


class Channel:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.reads = 0

    def recv(self, size):
        self.reads += 1
        return next(self.chunks, b'')


class MonitorTests(unittest.TestCase):
    def test_command_echo_does_not_finish_reply(self):
        chunks = [b'\r(qemu) s\x1b[K', b'creendump file\r\n', b'(qem', b'u) ']
        channel = Channel(chunks)
        self.assertEqual(read_prompt(channel), b''.join(chunks))
        self.assertEqual(channel.reads, len(chunks))

    def test_disconnect_does_not_accept_an_incomplete_echo(self):
        with self.assertRaises(EOFError):
            read_prompt(Channel([b'\r(qemu) screendump']))

    def test_reply_is_bounded(self):
        with self.assertRaises(ValueError):
            read_prompt(Channel([b'x' * 8]), limit=4)


if __name__ == '__main__':
    unittest.main()
