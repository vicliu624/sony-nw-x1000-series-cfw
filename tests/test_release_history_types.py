"""SDK source releases coexist with strict firmware/application version history."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from publish_release import firmware_history_releases

def release(tag,names,draft=False):
    return {'tag_name':tag,'draft':draft,'assets':[{'name':name} for name in names]}

class ReleaseHistoryTypes(unittest.TestCase):
    def test_only_recognized_source_sdk_is_separate_from_app_history(self):
        firmware=release('v0.1.0-dev.21',['catalog.tsv','release-manifest.json'])
        sdk=release('sdk-v0.1.0-alpha.1',['x1000-sdk-0.1.0-alpha.1-source.zip','x1000-sdk-0.1.0-alpha.1-source.zip.sha256'])
        self.assertEqual(firmware_history_releases([sdk,firmware],'v0.1.0-dev.22'),[firmware])

    def test_unknown_release_is_not_silently_excluded_from_catalog_validation(self):
        unknown=release('other-tool-v1',[])
        self.assertEqual(firmware_history_releases([unknown],'v1.0.0'),[unknown])

    def test_sdk_tag_cannot_hide_a_firmware_catalog_or_arbitrary_assets(self):
        for names in ([],['catalog.tsv','release-manifest.json'],['x1000-sdk-0.1.0-alpha.1-source.zip']):
            with self.assertRaises(ValueError):
                firmware_history_releases([release('sdk-v0.1.0-alpha.1',names)],'v1.0.0')
        with self.assertRaises(ValueError):
            firmware_history_releases([release('sdk-vinvalid',[])],'v1.0.0')

    def test_drafts_and_current_tag_preserve_existing_publisher_semantics(self):
        current=release('v1.0.0',[])
        draft=release('sdk-vbad',[],draft=True)
        self.assertEqual(firmware_history_releases([current,draft],'v1.0.0'),[])

if __name__=='__main__':unittest.main()
