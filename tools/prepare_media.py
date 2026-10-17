#!/usr/bin/env python3
"""Prepare/verify private AVC caches from one original movie or a movie folder."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import tempfile
from media_cache import cache_status, digest, validate_profiles

ROOT = Path(__file__).resolve().parents[1]


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries',
        'stream=codec_name,width,height,nb_read_frames,r_frame_rate,color_space,color_range:format=duration',
        '-of', 'json', str(path)], text=True))


def prepare(source, cache):
    source, cache = Path(source).resolve(), Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    status = cache_status(source, cache)
    if status['ready']:
        return status
    original = probe(source)
    x = original['streams'][0]
    if x.get('codec_name') != 'vp9' or x.get('color_space') != 'bt709' or x.get('color_range') != 'tv':
        raise ValueError(f'{source.name}: unsupported source profile')
    # Never publish an unchecked movie at the path the runtime loads.
    with tempfile.TemporaryDirectory(prefix='.prepare-', dir=cache) as tmp:
        temp = Path(tmp) / 'movie.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(source), '-c:v', 'h264_videotoolbox', '-b:v', '20M',
            '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-c:a', 'aac', '-b:a', '256k',
            '-movflags', '+faststart', '-y', str(temp)], check=True)
        converted = probe(temp)
        validate_profiles(original, converted)
        if digest(source) != status['source_sha256']:
            raise ValueError(f'{source.name}: source changed during conversion')
        receipt = {'source': str(source), 'source_sha256': status['source_sha256'],
            'output_sha256': digest(temp), 'original': original, 'converted': converted,
            'method': 'AVC VideoToolbox 20 Mbps; AAC audio; original frame cadence'}
        saved = Path(tmp) / 'receipt.json'
        saved.write_text(json.dumps(receipt, indent=2) + '\n')
        temp.replace(status['output'])
        saved.replace(cache / (status['source_sha256'] + '.json'))
    return dict(status, ready=True, reason='prepared', frames=converted['streams'][0]['nb_read_frames'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path, help='One original movie, or the complete original movie directory')
    p.add_argument('--cache', type=Path, default=ROOT / 'work/media')
    p.add_argument('--jobs', type=int, choices=range(1, 5), default=2)
    p.add_argument('--check', action='store_true', help='Verify cache coverage without converting')
    a = p.parse_args()
    source = a.input.resolve()
    files = sorted(source.rglob('*.webm')) if source.is_dir() else [source]
    if not files or any(not f.is_file() for f in files):
        p.error('input must contain existing local movies')
    report = []
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        jobs = {pool.submit(cache_status if a.check else prepare, f, a.cache): f for f in files}
        for future in as_completed(jobs):
            f = jobs[future]
            try:
                row = future.result()
            except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as e:
                row = {'source': str(f), 'ready': False, 'reason': str(e)}
            report.append(row)
            print(f"[{len(report)}/{len(files)}] {f.name}: {row['reason']}", flush=True)
    a.cache.mkdir(parents=True, exist_ok=True)
    ready = sum(r['ready'] for r in report)
    output = a.cache / 'inventory.json'
    output.write_text(json.dumps({'total': len(files), 'ready': ready,
        'movies': sorted(report, key=lambda r: r['source'])}, indent=2) + '\n')
    print(f'{ready}/{len(files)} movie caches verified. Private report: {output}', flush=True)
    if ready != len(files):
        p.exit(1, 'Incomplete movie cache; do not launch a full chapter run yet.\n')


if __name__ == '__main__':
    main()
