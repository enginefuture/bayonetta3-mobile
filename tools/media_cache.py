"""Local movie-cache validation shared by preparation and launch preflight."""
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def validate_profiles(original, converted):
    x, y = original['streams'][0], converted['streams'][0]
    if x.get('codec_name') != 'vp9' or x.get('color_space') != 'bt709' or x.get('color_range') != 'tv':
        raise ValueError('Native movie adapter requires VP9 BT.709 studio range')
    if y.get('codec_name') != 'h264' or any(x[k] != y[k] for k in ('width', 'height', 'nb_read_frames', 'r_frame_rate')):
        raise ValueError('Converted video shape/frame timing mismatch')
    if abs(float(original['format']['duration']) - float(converted['format']['duration'])) > 0.05:
        raise ValueError('Converted duration differs by more than 50 ms')


def cache_status(source, cache):
    """Require a successful validation receipt and exact original/output hashes."""
    source, cache = Path(source), Path(cache)
    sha = digest(source)
    out, receipt = cache / (sha + '.mp4'), cache / (sha + '.json')
    row = {'source': str(source), 'source_sha256': sha, 'output': str(out)}
    try:
        data = json.loads(receipt.read_text())
        if data['source_sha256'] != sha or digest(out) != data['output_sha256']:
            raise ValueError('cache checksum mismatch')
        validate_profiles(data['original'], data['converted'])
        row.update(ready=True, reason='verified', frames=data['converted']['streams'][0]['nb_read_frames'])
    except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
        row.update(ready=False, reason=str(e))
    return row


def movie_inventory(directory, cache):
    return [cache_status(p, cache) for p in sorted(Path(directory).rglob('*'))
            if p.is_file() and p.suffix.lower() == '.webm']
