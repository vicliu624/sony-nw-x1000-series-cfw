"""Compose private C manifest values from already-qualified local input headers."""
import re


def render(stock_header, candidate_header):
    definitions = (
        'struct stock_input {const char *path;unsigned bytes;unsigned char sha[32];};\n',
        'struct stock_link {const char *path,*target;};\n',
    )
    for definition in definitions:
        if stock_header.count(definition) != 1:
            raise ValueError('Unexpected original input manifest declaration')
        stock_header = stock_header.replace(definition, '')
    for text, names in ((stock_header, ('stock_inputs', 'stock_links')),
                        (candidate_header, ('exchange_inputs',))):
        for name in names:
            if len(re.findall(r'\b' + name + r'\[\]\s*=\s*\{', text)) != 1:
                raise ValueError('Missing/ambiguous input table: ' + name)
    return ('/* Values from explicit, hash-qualified local manifests. */\n'
            '#include "native_environment.h"\n' + stock_header + candidate_header).replace(
                'struct stock_input ', 'struct xnow_native_file ').replace(
                'struct stock_link ', 'struct xnow_native_link ')
