"""SDK adoption is source-level and cannot silently select another ABI/profile."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from app_registry import ROOT
from sdk_services import definition_contract,manifest,resolve,service_files
from sdk_build import compile_app

class SDKServiceContract(unittest.TestCase):
    def test_modules_resolve_to_real_sources_and_reject_invalid_requests(self):
        self.assertIn('runtime/store/tls_socket_step.c',service_files(['network']))
        self.assertIn('runtime/platform/pcm_output.c',service_files(['pcm']))
        self.assertIn('runtime/platform/text/bitmap_font.c',service_files(['unicode-font']))
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

    def test_native_apps_follow_selected_module_apis_across_sdk_releases(self):
        actual_read=Path.read_text
        newer_release='0.2.0-alpha.999'
        def read_sdk_file(path,*args,**kwargs):
            if path==ROOT/'sdk/VERSION':return newer_release+'\n'
            if path==ROOT/'sdk/services.json':
                data=json.loads(actual_read(path,*args,**kwargs))
                data['modules']['display']['api']=2
                return json.dumps(data)
            return actual_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',read_sdk_file):
            with self.assertRaisesRegex(ValueError,'display requires API 1'):
                definition_contract(ROOT/'runtime/apps/diagnostics')
            contract=definition_contract(ROOT/'runtime/apps/hello')
            self.assertEqual(contract['version'],newer_release)
            self.assertEqual(contract['resolved_module_api'],{'startup':1})

    def test_module_checks_its_dependency_api(self):
        available=manifest()
        available['abi']['api']=2
        self.assertEqual(resolve(['startup'],available),['startup'])
        with self.assertRaisesRegex(ValueError,'list-ui requires abi API 1'):
            resolve(['list-ui'],available)
        available['list-ui']['requires_api']={'abi':2}
        self.assertEqual(resolve(['list-ui'],available),['abi','list-ui'])

    def test_callback_recipe_checks_api_and_embeds_actual_sdk_release(self):
        definition=ROOT/'runtime/apps/sdk-counter'
        recipe_path=definition/'build.json'
        version_path=ROOT/'sdk/VERSION'
        actual_read=Path.read_text
        recipe=json.loads(actual_read(recipe_path))
        self.assertEqual(recipe['api'],1)
        release='0.2.0-alpha.999'
        def read_sdk_file(path,*args,**kwargs):
            if path==recipe_path:return json.dumps(recipe)
            if path==version_path:return release+'\n'
            return actual_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',read_sdk_file), \
             patch('sdk_build.fresh_work',return_value=ROOT/'work'), \
             patch('sdk_build.subprocess.check_output',return_value=''), \
             patch('sdk_build.subprocess.run',side_effect=RuntimeError('compiler boundary')) as compiler:
            with self.assertRaisesRegex(RuntimeError,'compiler boundary'):
                compile_app(definition,ROOT/'work',host=True)
            self.assertIn('-DXW_SDK_VERSION="'+release+'"',compiler.call_args.args[0])
            compiler.reset_mock()
            recipe['api']=2
            with self.assertRaisesRegex(ValueError,'callback API 2'):
                compile_app(definition,ROOT/'work',host=True)
            self.assertFalse(compiler.called)

    def test_every_frozen_app_is_bound_without_changing_release_composition(self):
        policy=json.loads((ROOT/'config/sdk-migration.json').read_text())
        self.assertEqual(len(policy['apps']),16)
        for ident in policy['apps']:
            contract=definition_contract(ROOT/'runtime/apps'/ident)
            self.assertEqual(contract['profile'],'native-services')
        published = json.loads((ROOT/'config/release.json').read_text())['apps']
        self.assertEqual(published, [
            'device-info', 'diagnostics', 'dictionary', 'ebook', 'fm-radio',
            'gbc', 'graphics-demo', 'hello', 'key-check', 'qqmusic', 'store',
            'tamagotchi-id', 'terminal',
        ])

if __name__=='__main__':unittest.main()
