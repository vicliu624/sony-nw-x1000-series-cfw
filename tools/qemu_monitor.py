"""Read complete replies from the local QEMU human monitor."""


def read_prompt(channel, limit=1024 * 1024):
    data = bytearray()
    while not data.endswith(b'(qemu) '):
        chunk = channel.recv(4096)
        if not chunk:
            raise EOFError('QEMU monitor closed before its final prompt')
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError('QEMU monitor reply exceeds its bound')
    return bytes(data)
