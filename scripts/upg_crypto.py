"""PC-only Sony DES container codec using OpenSSL3; no fallback or retry.

Same-backend roundtrips check transport and assembly. Independent Rockbox
component comparison remains necessary; roundtrip success is not qualification.
"""
import subprocess


def _transform(data, key, decrypt=False):
    if not isinstance(data, bytes) or len(data) % 8 or len(key) != 8:
        raise ValueError('DES input must be aligned bytes with an eight-byte key')
    command = ['openssl', 'enc', '-des-ecb', '-provider', 'legacy',
               '-provider', 'default', '-K', key.hex(), '-nosalt', '-nopad']
    if decrypt:
        command.append('-d')
    try:
        result = subprocess.run(command, input=data, capture_output=True,
                                timeout=60, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('OpenSSL3 legacy DES failed; no fallback or retry') from error
    if len(result.stdout) != len(data):
        raise ValueError('OpenSSL DES output length mismatch')
    return result.stdout


def encrypt_verified(data, key):
    encoded = _transform(data, key)
    if _transform(encoded, key, True) != data:
        raise ValueError('OpenSSL DES encryption roundtrip mismatch')
    return encoded


def decrypt_verified(data, key):
    decoded = _transform(data, key, True)
    if _transform(decoded, key) != data:
        raise ValueError('OpenSSL DES decryption roundtrip mismatch')
    return decoded
