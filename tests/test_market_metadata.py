"""Release metadata/version policy, independent of proprietary inputs."""
from pathlib import Path
import ast,json,struct,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from market_metadata import parse_version,compare_versions,descriptions,description_header,check_history,ROOT

class MarketMetadataTests(unittest.TestCase):
    def test_semver_order(self):
        values=['1.0.0-alpha','1.0.0-alpha.1','1.0.0-alpha.beta','1.0.0-beta','1.0.0-beta.2','1.0.0-beta.11','1.0.0-rc.1','1.0.0','1.0.1','1.9.0','1.10.0']
        for i,a in enumerate(values):
            for j,b in enumerate(values):self.assertEqual(compare_versions(a,b),(i>j)-(i<j))
        self.assertEqual(compare_versions('1.0.0+one','1.0.0+two'),0)
    def test_bad_versions_are_not_guessed(self):
        for value in ['v1.0.0','1.0','01.0.0','1.0.0-01','1.0.0-','1.0.0+','1.0.0-a..b','1.0.0+a..b']:
            with self.assertRaises(ValueError):parse_version(value)
    def test_every_release_app_has_bounded_metadata(self):
        info=descriptions();self.assertTrue(set(json.loads((ROOT/'config/release.json').read_text())['apps'])<=set(info))
        self.assertEqual((ROOT/'runtime/store/market_descriptions.h').read_text(),description_header())
    def test_unknown_application_is_discovered_without_registration(self):
        import tempfile
        from app_registry import applications
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/'independent-example';(folder/'assets').mkdir(parents=True)
            info=dict(schema=1,id=folder.name,target='sony-nw-x1000-jp',title='Example',summary='Independent app',description='Native example.',changes='First build.',channel='experimental',build=dict(script='build.py',package='work/independent-example'))
            (folder/'app.json').write_text(json.dumps(info));(folder/'VERSION').write_text('1.0.0')
            (folder/'assets/icon.png').write_bytes((ROOT/'runtime/native/assets/icon.png').read_bytes());(folder/'build.py').write_text('# local builder\n')
            self.assertEqual(set(applications(root)),{'independent-example'})
            info['title']='x'*49;(folder/'app.json').write_text(json.dumps(info))
            with self.assertRaises(ValueError):applications(root)
    def test_immutable_version_and_monotonic_release(self):
        old={'hello':{'version':'1.2.3','inventory_sha256':'old'}}
        check_history(old,[old])
        check_history({'hello':{'version':'1.2.4','inventory_sha256':'new'}},[old])
        for version in ['1.2.2','1.2.3','1.2.3+repacked']:
            with self.assertRaises(ValueError):check_history({'hello':{'version':version,'inventory_sha256':'new'}},[old])
    def test_icon_coverage_and_qqmusic_version(self):
        from app_registry import applications
        entries=applications()
        self.assertTrue(set(descriptions())<=set(entries))
        for ident in entries:
            svg=ROOT/'runtime/apps'/ident/'assets/icon.svg';png=svg.with_suffix('.png')
            self.assertIn('<svg',svg.read_text());data=png.read_bytes();self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n');self.assertEqual(struct.unpack('>II',data[16:24]),(64,64))
        version=(ROOT/'runtime/apps/qqmusic/VERSION').read_text().strip()
        self.assertGreater(compare_versions(version,'0.1.0-dev.20'),0)

if __name__=='__main__':unittest.main()
