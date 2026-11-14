"""Pinned PC-side source composition; no crypto source is installed on device."""
import hashlib
import tarfile
from app_registry import ROOT

def inputs():
    packed=ROOT/'work/bearssl-0.6.tar.gz'
    if hashlib.sha256(packed.read_bytes()).hexdigest()!='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14':
        raise ValueError('Pinned BearSSL input required; run SDK setup --services')
    base=ROOT/'work/external-tls-probe/bearssl-0.6'
    with tarfile.open(packed,'r:gz') as archive:
        for file in [base/'src/ec/ec_c25519_m15.c',base/'src/codec/ccopy.c',base/'src/inner.h',*sorted((base/'inc').glob('*.h'))]:
            expected=archive.extractfile('bearssl-0.6/'+file.relative_to(base).as_posix()).read()
            if file.read_bytes()!=expected:raise ValueError('Pinned crypto source changed: '+str(file))
    # Reuse the SDK's existing MIT-licensed implementation, not a second curve.
    return ['runtime/apps/wireless-remote/pairing_auto.c','runtime/apps/wireless-remote/pairing_curve.c',
            (base/'src/ec/ec_c25519_m15.c').relative_to(ROOT).as_posix(),
            (base/'src/codec/ccopy.c').relative_to(ROOT).as_posix()],['-I'+str(base/'inc'),'-I'+str(base/'src')]

def dependencies():
    base=ROOT/'work/external-tls-probe/bearssl-0.6'
    return ['tools/pairing_crypto.py','runtime/apps/wireless-remote/pairing_auto.h',
            'runtime/apps/wireless-remote/pairing_proof.h',
            (base/'src/inner.h').relative_to(ROOT).as_posix(),
            *[p.relative_to(ROOT).as_posix() for p in sorted((base/'inc').glob('*.h'))]]
