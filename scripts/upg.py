"""Read-only Japanese X1000 1.11 UPG inspection. No device access."""
import hashlib
import struct
if __package__:
    from .upg_crypto import decrypt_verified
else:
    from upg_crypto import decrypt_verified

KEY = b"466c8cd0"
SIGNATURE = b"daefe603"
STOCK_SHA256 = "002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b"

def unpack(data, require_stock=True):
    if len(data) < 64 or len(data) % 8:
        raise ValueError("Invalid container size")
    if hashlib.md5(data[16:]).digest() != data[:16]:
        raise ValueError("UPG MD5 mismatch")
    header = decrypt_verified(data[16:64], KEY)
    if struct.unpack_from("<8sII", header) != (SIGNATURE, 4, 0):
        raise ValueError("Not the Japanese X1000 four-component header")
    entries = [struct.unpack_from("<II", header, 16 + i * 8) for i in range(4)]
    end = 64
    for offset, size in entries:
        if offset < end or offset % 8 or size <= 0:
            raise ValueError("Invalid or overlapping component")
        end = offset + ((size + 7) & ~7)
        if end > len(data):
            raise ValueError("Truncated component")
    if require_stock and hashlib.sha256(data).hexdigest() != STOCK_SHA256:
        raise ValueError("Input is not the pinned Sony Japanese 1.11 UPG")
    return entries, [decrypt_verified(data[o:o + ((n + 7) & ~7)], KEY)[:n] for o, n in entries]
