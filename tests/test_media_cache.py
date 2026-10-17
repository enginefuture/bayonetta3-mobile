"""Media preflight must reject missing/corrupt caches before a chapter runs."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from media_cache import cache_status, digest, movie_inventory
import prepare_media


def profile(codec):
    return {'streams':[{'codec_name':codec,'color_space':'bt709','color_range':'tv',
        'width':16,'height':16,'nb_read_frames':'2','r_frame_rate':'30/1'}],
        'format':{'duration':'0.066667'}}


class MediaCache(unittest.TestCase):
    def test_original_and_output_checksums_and_receipt_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'test.webm';source.write_bytes(b'synthetic original')
            sha=digest(source);out=root/(sha+'.mp4');out.write_bytes(b'synthetic converted')
            self.assertFalse(cache_status(source,root)['ready'])
            receipt={'source_sha256':sha,'output_sha256':digest(out),
                'original':profile('vp9'),'converted':profile('h264')}
            (root/(sha+'.json')).write_text(json.dumps(receipt))
            self.assertTrue(cache_status(source,root)['ready'])
            out.write_bytes(b'corrupt')
            self.assertFalse(cache_status(source,root)['ready'])
            source.write_bytes(b'different source')
            self.assertFalse(cache_status(source,root)['ready'])

    def test_directory_preflight_includes_nested_movies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'localized').mkdir()
            (root/'a.webm').write_bytes(b'first')
            (root/'localized/b.webm').write_bytes(b'second')
            self.assertEqual(len(movie_inventory(root,root/'cache')),2)

    def test_invalid_conversion_does_not_replace_existing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'test.webm';source.write_bytes(b'synthetic original')
            out=root/(digest(source)+'.mp4');out.write_bytes(b'existing cache')
            wrong=profile('h264');wrong['streams'][0]['width']=32
            def encode(cmd,**kwargs):Path(cmd[-1]).write_bytes(b'bad conversion')
            with patch.object(prepare_media,'probe',side_effect=[profile('vp9'),wrong]),patch.object(prepare_media.subprocess,'run',side_effect=encode):
                with self.assertRaises(ValueError):prepare_media.prepare(source,root)
            self.assertEqual(out.read_bytes(),b'existing cache')
            self.assertFalse(list(root.glob('.prepare-*')))


if __name__=='__main__':unittest.main()
