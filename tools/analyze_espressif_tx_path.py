"""Pinned ESP32-S3 archive/relocation review; no target execution or device IO."""
from pathlib import Path
import argparse,hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espressif-tx-path';OUT.mkdir(parents=True,exist_ok=True)
EXPECTED={'libespnow.a':'c7b830e69168339c1d224676180ae048fa2ec47437e2a44d1682b946b962d571','libnet80211.a':'a306384a21ec8b2f93585983a991401ffbfeea9b1a839ff5e089c1ec533fe725','libpp.a':'a8f2109ad1bc86a905d388b5c44e973f02f292ee74c48c7bb0481e11d8ea4242'}
MEMBERS={'espnow.o':'libespnow.a','manatick.o':'libespnow.a','ieee80211_action_vendor.o':'libnet80211.a','ieee80211_output.o':'libnet80211.a','ieee80211_crypto_ccmp.o':'libnet80211.a','pp.o':'libpp.a','lmac.o':'libpp.a','hal_mac.o':'libpp.a','hal_crypto.o':'libpp.a','if_hwctrl.o':'libpp.a'}
MEMBERS['wdev.o']='libpp.a'
MEMBERS['ieee80211_sta.o']='libnet80211.a'

def references(raw,function):
    elf=ELFFile(io.BytesIO(raw));symbols=elf.get_section_by_name('.symtab');matches=[s for s in symbols.iter_symbols() if s.name==function and isinstance(s['st_shndx'],int)];assert len(matches)==1
    symbol=matches[0];index=symbol['st_shndx'];section=elf.get_section(index);rows=[]
    for rel in elf.iter_sections():
        if rel['sh_type'] not in ('SHT_REL','SHT_RELA') or rel['sh_info']!=index:continue
        for r in rel.iter_relocations():
            if not symbol['st_value']<=r['r_offset']<symbol['st_value']+symbol['st_size']:continue
            target=symbols.get_symbol(r['r_info_sym']).name
            if target:rows.append({'offset':hex(r['r_offset']),'relocation':r['r_info_type'],'target':target})
    return {'function':function,'section':section.name,'offset':hex(symbol['st_value']),'bytes':symbol['st_size'],'references':rows}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--idf-root',type=Path,required=True);parser.add_argument('--objdump',type=Path,required=True);args=parser.parse_args();libs=args.idf_root/'components/esp_wifi/lib/esp32s3';objects={};files={}
    for name,digest in EXPECTED.items():assert hashlib.sha256((libs/name).read_bytes()).hexdigest()==digest
    for member,archive in MEMBERS.items():
        data=subprocess.check_output(['ar','p',str(libs/archive),member]);elf=ELFFile(io.BytesIO(data));assert elf['e_machine']=='EM_XTENSA' and elf.elfclass==32 and elf.little_endian
        (OUT/member).write_bytes(data);objects[member]=data;files[member]={'archive':archive,'sha256':hashlib.sha256(data).hexdigest()}
        result=subprocess.run([str(args.objdump),'-dr',member],cwd=OUT,capture_output=True,text=True,check=True);(OUT/(member+'.disasm.txt')).write_text(result.stdout)
    selections=[('manatick.o','mt_send'),('ieee80211_action_vendor.o','ieee80211_send_action_vendor_spec'),('ieee80211_action_vendor.o','ieee80211_construct_action_vendor_spec'),('ieee80211_action_vendor.o','ieee80211_alloc_action_vendor_spec'),('ieee80211_output.o','ieee80211_post_hmac_tx'),('ieee80211_output.o','ieee80211_output_pending_eb'),('ieee80211_crypto_ccmp.o','ccmp_encap'),('pp.o','ppTask'),('pp.o','ppProcessTxQ'),('pp.o','ppTxPkt'),('pp.o','ppProcTxSecFrame')]
    selections.append(('lmac.o','lmacTxFrame'))
    selections.append(('lmac.o','lmacSetTxFrame'))
    selections.append(('hal_mac.o','hal_mac_tx_set_ppdu'))
    selections.append(('ieee80211_sta.o','sta_recv_mgmt'))
    selections.extend([('ieee80211_crypto_ccmp.o','ieee80211_decrypt_espnow_pkt'),('ieee80211_crypto_ccmp.o','ccmp_decap')])
    selections.extend([('if_hwctrl.o','ic_set_key'),('wdev.o','wDev_Insert_KeyEntry'),('hal_crypto.o','hal_crypto_set_key_entry')])
    selections.extend([('ieee80211_output.o','ieee80211_output_init'),('ieee80211_output.o','ieee80211_output_process'),('if_hwctrl.o','ic_register_net80211_tx_cb'),('pp.o','pp_register_net80211_tx_cb')])
    selections.extend(('hal_crypto.o',n) for n in ('hal_crypto_init','hal_crypto_enable','hal_crypto_disable','hal_crypto_mgmt_rx_enabled'))
    procedures=[dict(object=member,**references(objects[member],name)) for member,name in selections]
    expected_edges={'mt_send':'ieee80211_send_action_vendor_spec','ieee80211_send_action_vendor_spec':'ieee80211_construct_action_vendor_spec','ieee80211_construct_action_vendor_spec':'ieee80211_alloc_action_vendor_spec','ieee80211_post_hmac_tx':'pp_post'}
    for caller,target in expected_edges.items():assert target in {r['target'] for p in procedures if p['function']==caller for r in p['references']}
    elf=ELFFile(io.BytesIO(objects['ieee80211_crypto_ccmp.o']));descriptor=elf.get_section_by_name('.data.ccmp');assert struct.unpack_from('<3I',descriptor.data())==(3,8,8);sym=elf.get_section_by_name('.symtab');bindings={}
    idx=next(i for i,s in enumerate(elf.iter_sections()) if s.name=='.data.ccmp')
    for sec in elf.iter_sections():
        if sec['sh_type'] in ('SHT_REL','SHT_RELA') and sec['sh_info']==idx:
            for r in sec.iter_relocations():bindings[r['r_offset']]=sym.get_symbol(r['r_info_sym']).name
    assert bindings[16]=='ccmp_encap' and bindings[20]=='ccmp_decap'
    pp=ELFFile(io.BytesIO(objects['pp.o']));table=pp.get_section_by_name('.rodata');assert struct.unpack_from('<I',table.data(),5*4)[0]==0x130
    overhead=pp.get_section_by_name('.rodata.CSWTCH$542').data();assert overhead[3-1]==12
    for caller,target in [('ieee80211_send_action_vendor_spec','ieee80211_post_hmac_tx'),('ieee80211_output_pending_eb','ppTxPkt'),('ppTxPkt','ppProcTxSecFrame'),('ppProcessTxQ','lmacTxFrame')]:
        assert target in {r['target'] for p in procedures if p['function']==caller for r in p['references']}
    report={'reviewed':True,'framework':'ESP-IDF5.5.1 packaged ESP32-S3 binaries','architecture':'ELF32 Xtensa little endian','archive_sha256':EXPECTED,'objects':files,'procedures':procedures,'verified_symbol_reference_edges':expected_edges,'ccmp_descriptor_words':[3,8,8],'ccmp_descriptor_bindings':bindings,'allocator_review':{'pn_extiv_at_mac_header_offset':24,'reserved_header_bytes':8,'software_pn_increment':1,'body_start_after_extiv':True},'constructor_review':{'protected_flag_store_section_offset':'0x1d6','descriptor_enable_or_section_offset':'0x1df','cipher_field_store_section_offset':'0x20e','software_ccmp_encrypt_direct_reference':False},'pp_static_queue_review':{'post_hmac_event':5,'pp_task_switch_case5_target':'0x130','case5_uses_g_net80211_tx_func':True,'callback_registration_proven':False,'pp_tx_security_ccmp_length_increment':12,'cipher_overhead_table_bytes':list(overhead),'length_increment_consistent_with_trailer8_plus_fcs4':True},'queue_dispatch_execution_proven':False,'hardware_ccm_nonce_aad_mic_proven':False,'espnow_software_decrypt_branch_called_in_s3_path_proven':False,'target_instructions_executed':False,'device_accessed':False,'radio_loaded':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    def literal_binding(member,section_name,offset,target):
        e=ELFFile(io.BytesIO(objects[member]));symbols=e.get_section_by_name('.symtab')
        index=next(i for i,s in enumerate(e.iter_sections()) if s.name==section_name)
        bindings=[symbols.get_symbol(r['r_info_sym']).name for s in e.iter_sections() if s['sh_type'] in ('SHT_REL','SHT_RELA') and s['sh_info']==index for r in s.iter_relocations() if r['r_offset']==offset and r['r_info_type']==1]
        assert bindings==[target]
    literal_binding('ieee80211_output.o','.text.ieee80211_output_init',4,'ieee80211_output_process')
    literal_binding('ieee80211_output.o','.text.ieee80211_output_init',16,'ic_register_net80211_tx_cb')
    literal_binding('pp.o','.text.pp_register_net80211_tx_cb',0,'g_net80211_tx_func')
    for caller,target in [('ieee80211_output_init','ic_register_net80211_tx_cb'),('ic_register_net80211_tx_cb','pp_register_net80211_tx_cb'),('ieee80211_output_process','ieee80211_output_pending_eb')]:
        assert target in {r['target'] for p in procedures if p['function']==caller for r in p['references']}
    # Pinned instruction bytes reviewed with matching Xtensa objdump: init loads
    # callback into a10; wrapper forwards a2 to a10; registrar stores a2 to global.
    for member,section,offset,expected in [('ieee80211_output.o','.text.ieee80211_output_init',0x1a,'a1faff'),('if_hwctrl.o','.text.ic_register_net80211_tx_cb',7,'ad02'),('pp.o','.text.pp_register_net80211_tx_cb',10,'2908')]:
        data=ELFFile(io.BytesIO(objects[member])).get_section_by_name(section).data()
        assert data[offset:offset+len(bytes.fromhex(expected))]==bytes.fromhex(expected)
    report['pp_static_queue_review'].update(callback_registration_proven=True,registered_callback='ieee80211_output_process',registration_evidence='Pinned literal relocations and reviewed Xtensa argument/store instructions; static only')
    literal_binding('manatick.o','.text.mt_set_lmk',0x3c,'ic_set_key')
    for caller,target in [('ic_set_key','wDev_Insert_KeyEntry'),('wDev_Insert_KeyEntry','hal_crypto_set_key_entry'),('wDev_Insert_KeyEntry','hal_crypto_enable')]:
        assert target in {r['target'] for p in procedures if p['function']==caller for r in p['references']}
    mt=ELFFile(io.BytesIO(objects['manatick.o'])).get_section_by_name('.text.mt_set_lmk').data()
    assert mt[0x137:0x13a]==bytes.fromhex('b2a003') # movi a11,3 before ic_set_key
    report['key_install_review']={'mt_set_lmk_section_call_offset':'0x13a','ic_set_key_second_argument':3,'path':['ic_set_key','wDev_Insert_KeyEntry','hal_crypto_set_key_entry/hal_crypto_enable'],'key_material_extracted':False,'hardware_parameter_semantics_proven':False}
    hal=ELFFile(io.BytesIO(objects['hal_crypto.o'])).get_section_by_name('.text.hal_crypto_set_key_entry').data()
    assert struct.unpack_from('<4I',hal,0x10)==(0x60034400,0x60034404,0x60033814,0x60034408)
    # Reviewed slot addressing: addx4(index,index) followed by addx8(...,base).
    assert hal[0x148:0x14b]==bytes.fromhex('2052a0')
    assert hal[0x14b:0x14e]==bytes.fromhex('9095b0')
    assert mt[0x4c:0x4f]==bytes.fromhex('22a310') # initial metadata halfword0x310
    report['key_entry_layout_review']={'slot_stride_bytes':40,'metadata_words_offsets':[0,4],'rounded_key_copy_offset':8,'validity_bitmap_address':'0x60033814','slot_base_address':'0x60034400','mt_initial_halfword_at_context184':'0x0310','hal_key_length_rounding':'(length+3)&~3','nonce_or_aad_register_identified':False,'instruction_execution':False}
    allocator=ELFFile(io.BytesIO(objects['ieee80211_action_vendor.o'])).get_section_by_name('.text.ieee80211_alloc_action_vendor_spec').data()
    # l8ui(context,185), shift6, OR ExtIV32, store header27. This is distinct
    # from the hardware key-slot index stored at context186.
    assert allocator[0x9f:0xab]==bytes.fromhex('3206b9a0331190332032481b')
    report['key_id_review']={'initializer_halfword':'0x0310','initial_context185':3,'allocator_key_id_source_context_offset':185,'allocator_extiv_byte':'0x20 | (context185 << 6)','initial_extiv_byte_expected':'0xe0','hardware_slot_context_offset':186,'native_endpoint_default_key_id':0,'static_default_mismatch':True,'actual_rf_key_id_verified':False,'warm_context_initialization_not_executed':True}
    for caller,target in [('sta_recv_mgmt','get_iav_key'),('sta_recv_mgmt','ieee80211_decrypt_espnow_pkt'),('ieee80211_decrypt_espnow_pkt','get_iav_key')]:
        assert target in {r['target'] for p in procedures if p['function']==caller for r in p['references']}
    wrapper=ELFFile(io.BytesIO(objects['ieee80211_crypto_ccmp.o'])).get_section_by_name('.text.ieee80211_decrypt_espnow_pkt').data()
    assert len(wrapper)==0x39
    report['rx_wrapper_review']={'function':'ieee80211_decrypt_espnow_pkt','section_sha256':hashlib.sha256(wrapper).hexdigest(),'reviewed_behavior':'get_iav_key(source), advance data pointer by24+descriptor header, subtract descriptor header+trailer','software_aes_in_this_wrapper':False,'sta_call_section_offset':'0xa0a','sta_checks_protected_and_key_id_before_call':True,'upstream_hardware_mic_validation_proven':False,'promiscuous_ciphertext_preservation_proven':False}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('procedures','objects')},indent=2))
if __name__=='__main__':main()
