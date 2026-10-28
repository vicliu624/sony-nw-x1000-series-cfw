"""SDK adoption is source-level and cannot silently select another ABI/profile."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from app_registry import ROOT
from sdk_services import definition_contract,resolve,service_files

class SDKServiceContract(unittest.TestCase):
    def test_modules_resolve_to_real_sources_and_reject_invalid_requests(self):
        self.assertIn('runtime/store/tls_socket_step.c',service_files(['network']))
        self.assertIn('runtime/platform/pcm_output.c',service_files(['pcm']))
        self.assertIn('runtime/apps/dictionary/dictionary.c',service_files(['unicode-font']))
        for modules in ([],['missing'],['display','display'],[42]):
            with self.assertRaises(ValueError):resolve(modules)

    def test_native_app_contract_requires_matching_sdk_and_target(self):
        parent=ROOT/'work/sdk-contract-tests';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            definition=Path(directory)/'example';definition.mkdir()
            data={'id':'example','target':'sony-nw-x1000-jp','sdk':{'version':(ROOT/'sdk/VERSION').read_text().strip(),'profile':'native-services','modules':['startup','display']}}
            file=definition/'app.json';file.write_text(json.dumps(data))
            self.assertIn('display',definition_contract(definition)['resolved_modules'])
            data['sdk']['version']='0.0.0';file.write_text(json.dumps(data))
            with self.assertRaises(ValueError):definition_contract(definition)
            data['sdk']['version']=(ROOT/'sdk/VERSION').read_text().strip();data['target']='another-model';file.write_text(json.dumps(data))
            with self.assertRaises(ValueError):definition_contract(definition)

    def test_every_frozen_app_is_bound_without_changing_release_composition(self):
        policy=json.loads((ROOT/'config/sdk-migration.json').read_text())
        self.assertEqual(len(policy['apps']),16)
        for ident in policy['apps']:
            contract=definition_contract(ROOT/'runtime/apps'/ident)
            self.assertEqual(contract['profile'],'native-services')
        self.assertEqual(len(json.loads((ROOT/'config/release.json').read_text())['apps']),14)

if __name__=='__main__':unittest.main()
