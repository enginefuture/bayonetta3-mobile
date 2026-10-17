"""Private session metadata and actionable exit classification for the native host."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import signal
import subprocess
import time


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.partial')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def classify_exit(code, log, watchdog=False):
    lines = log.splitlines()
    fatals = [line for line in lines if 'FATAL ' in line or '[dm] CRASH ' in line]
    reason = 'normal_exit' if code == 0 else 'nonzero_exit'
    if code < 0:
        reason = 'signal_' + signal.Signals(-code).name
    if watchdog and code in (124, 142, -signal.SIGALRM):
        reason = 'diagnostic_timeout'
    text = '\n'.join(fatals)
    if 'prepared H.264 movie missing' in text:
        reason = 'missing_movie_cache'
    elif 'Tessellation GPU failure:' in text or 'Tessellation preceding Metal 4 submission failed' in text:
        reason = 'metal_gpu_failure'
    elif 'tessellation' in text.lower() and 'pipeline' not in text.lower():
        reason = 'unsupported_tessellation'
    elif 'missing' in text.lower() and any(word in text.lower() for word in ('shader', 'metallib', 'library')):
        reason = 'missing_shader_library'
    elif 'pipeline' in text.lower():
        reason = 'metal_pipeline_failure'
    elif any('FATAL ' in line for line in fatals):
        reason = 'native_fatal'
    elif fatals and reason != 'diagnostic_timeout':
        reason = 'native_crash'
    windows = [line for line in lines if '计时 至帧' in line][-8:]
    movies = [line for line in lines if 'reader-backed source' in line or 'movie：打开' in line][-12:]
    frame = re.findall(r'\[nvn\] 帧 (\d+)：', log)
    tess=re.search(r'patch_size=(\d+) TCS=([0-9a-f]*) TES=([0-9a-f]*)',text)
    completed=[{'frame':int(f),'draws':int(d),'patches':int(p),'instances':int(i),'vs':vs,'tcs':tc,'tes':te,'gpu_ms':float(gpu)}
               for f,d,p,i,vs,tc,te,gpu in re.findall(r'\[tessellation\] frame=(\d+) draws=(\d+) patches=(\d+) instances=(\d+) VS=(\w+) TCS=(\w+) TES=(\w+) GPU=([\d.]+)ms',log)]
    return {'returncode': code, 'reason': reason, 'fatal_lines': fatals[-8:],
            'tessellation':{'patch_size':int(tess[1]),'tcs':tess[2],'tes':tess[3]} if tess else None,
            'completed_tessellation_samples':completed[-8:],
            'last_summary_frame': int(frame[-1]) if frame else None,
            'recent_frame_windows': windows, 'recent_movies': movies,
            'tail': lines[-40:], 'gameplay_pass': False}


def execute(command, env, log_path, metadata, timeout=None, watchdog=False):
    """Keep raw native stderr; the parent records exit even when native aborts."""
    log_path = Path(log_path)
    base = log_path.with_suffix('')
    session = Path(str(base) + '.session.json')
    events = Path(str(base) + '.events.jsonl')
    summary = Path(str(base) + '.summary.json')
    start = time.monotonic()
    metadata = dict(metadata, started_utc=datetime.now(timezone.utc).isoformat(),
                    command=command, raw_log=str(log_path), status='starting')
    write_json(session, metadata)
    with events.open('w', buffering=1) as journal:
        def event(name, **values):
            journal.write(json.dumps({'event': name, 'utc': datetime.now(timezone.utc).isoformat(),
                                      'elapsed_s': round(time.monotonic()-start, 6), **values}) + '\n')
        event('session_start')
        with log_path.open('w') as output:
            child = subprocess.Popen(command, env=env, stdout=output, stderr=subprocess.STDOUT)
            metadata.update(pid=child.pid, status='running')
            write_json(session, metadata)
            event('process_started', pid=child.pid)
            timed_out = False
            try:
                code = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                event('parent_timeout')
                child.kill()
                child.wait()
                code = 124
            except KeyboardInterrupt:
                event('parent_interrupted')
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                code = 130
        result = classify_exit(code, log_path.read_text(errors='replace'), watchdog=watchdog)
        if timed_out:
            result['reason'] = 'diagnostic_timeout'
        result.update(diagnostics=metadata.get('diagnostics',{}),elapsed_s=round(time.monotonic()-start, 3), pid=child.pid,
                      ended_utc=datetime.now(timezone.utc).isoformat())
        write_json(summary, result)
        metadata.update(status='exited', returncode=code, reason=result['reason'], summary=str(summary))
        write_json(session, metadata)
        event('process_exited', returncode=code, reason=result['reason'])
    print(f"Exit {code}: {result['reason']}. Summary: {summary}", flush=True)
    return code
