"""Framing for PC-only guest USB input, separate from native handoff receipts."""
import struct

FRAME_BYTES = 12


def command(status, request):
    if type(status) is not int or status not in (0, 1, 4):
        raise ValueError('Only disconnect, connect and start-connect events are modeled')
    if type(request) is not int or not 1 <= request <= 0xffffffff:
        raise ValueError('Invalid guest input request')
    return struct.pack('<4sB3xI', b'XWU2', status, request)


def receipt(data, request):
    if not isinstance(data, bytes) or len(data) != FRAME_BYTES:
        raise ValueError('Invalid guest USB receipt size')
    magic, observed, status, access, pending, notification = struct.unpack('<4sI4B', data)
    if magic != b'XWA2' or type(request) is not int or not 1 <= request <= 0xffffffff or observed != request:
        raise ValueError('Uncorrelated guest USB receipt')
    if status not in (0, 1, 4) or access not in (0, 1, 2) or pending > 1 or notification > 1:
        raise ValueError('Guest USB input refused the event')
    return dict(input_accepted=True, request=request, status=status, access=access,
                pending=pending, notification=notification, handoff_acknowledged=False)
