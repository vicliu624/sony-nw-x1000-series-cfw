"""Compose private C manifests for the Sony wireless owner."""
import hashlib
import json
import re
import tarfile


def stock_header(root):
    with root.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':
            raise ValueError('Unexpected Sony 1.11 root for the stock radio manifest')
    paths = ('/bin/busybox', '/usr/local/bin/wlan_load_driver.sh', '/usr/local/bin/wlanapi.sh',
             '/usr/local/bin/nvp', '/usr/local/bin/iwpriv', '/usr/local/bin/iwconfig',
             '/usr/local/bin/wlanconfig', '/etc/hostcmd.conf',
             *('/lib/modules/' + name for name in ('sd8686.ko', 'mp200_sdio.ko', 'wlan_pm_register.ko',
                                                   'wlan_pwr_ctrl.ko', 'sd8686.bin', 'helper_sd.bin')))
    links = ('/bin/sh', '/bin/grep', '/sbin/insmod', '/sbin/rmmod', '/sbin/lsmod')
    files = ['struct stock_input {const char *path;unsigned bytes;unsigned char sha[32];};',
             'static const struct stock_input stock_inputs[]={']
    aliases = ['struct stock_link {const char *path,*target;};',
               'static const struct stock_link stock_links[]={']
    with tarfile.open(root, 'r:gz') as archive:
        if './usr/local/bin/wlanapi.inc' in archive.getnames():
            raise ValueError('Unexpected Sony Wi-Fi override')
        for path in paths:
            member = archive.getmember('.' + path)
            if not member.isfile() or not 0 < member.size <= 1048576:
                raise ValueError('Invalid Sony wireless file: ' + path)
            files.append(file_initializer(path, archive.extractfile(member).read()))
        for path in links:
            member = archive.getmember('.' + path)
            if not member.issym():
                raise ValueError('Invalid Sony wireless link: ' + path)
            aliases.append('{' + json.dumps(path) + ',' + json.dumps(member.linkname) + '},')
    return '\n'.join([*files, '};', *aliases, '};']) + '\n'


def file_initializer(path, data):
    digest = hashlib.sha256(data).digest()
    return '{' + json.dumps(path) + ',' + str(len(data)) + ',{' + ','.join(map(str, digest)) + '}},'


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
