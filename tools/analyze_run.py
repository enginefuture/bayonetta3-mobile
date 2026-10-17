#!/usr/bin/env python3
"""Summarize a private native run without uploading logs or game content."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
from run_diagnostics import classify_exit, write_json


def distribution(values):
    values=sorted(v for v in values if math.isfinite(v) and v>=0)
    if not values:return None
    return {'samples':len(values),'p50':round(statistics.median(values),4),
            'p95':round(values[max(0,math.ceil(len(values)*.95)-1)],4),'max':round(values[-1],4)}


def frame_metrics(path):
    metrics={}
    with Path(path).open() as f:
        for line in f:
            if not line.strip() or line.startswith('#') or line.startswith('frame\t'):continue
            fields=line.rstrip().split('\t')
            if len(fields)!=3:continue
            try:value=float(fields[2])
            except ValueError:continue
            if fields[1].startswith('@'):metrics.setdefault(fields[1],[]).append(value)
    return {key:distribution(values) for key,values in metrics.items()}


def gpu_passes(path):
    largest=[];total=missing=0
    with Path(path).open() as f:
        for row in csv.DictReader((line for line in f if not line.startswith('#')),delimiter='\t'):
            try:span=float(row['span_ms'])
            except (KeyError,ValueError):continue
            total+=1
            if not math.isfinite(span) or span<0:missing+=1;continue
            largest.append(dict(row,span_ms=span))
            largest.sort(key=lambda r:r['span_ms'],reverse=True)
            del largest[12:]
    return {'rows':total,'unavailable_spans':missing,'largest_observed_spans':largest,
            'limitation':'Precise probes can split encoders. Spans overlap and must not be summed as independent GPU work; not an FPS benchmark.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('log',type=Path)
    a=p.parse_args();base=a.log.with_suffix('')
    summary=Path(str(base)+'.summary.json')
    result=json.loads(summary.read_text()) if summary.exists() else classify_exit(0,a.log.read_text(errors='replace'))
    if not summary.exists():result.update(reason='run_not_observed_exited',returncode=None)
    frames=Path(str(base)+'.frames.tsv');passes=Path(str(base)+'.passes.tsv')
    if frames.exists():result['frame_metrics']=frame_metrics(frames)
    if passes.exists():result['gpu_passes']=gpu_passes(passes)
    log=a.log.read_text(errors='replace')
    result['diagnostic_limits']=[s for s in log.splitlines() if 'limit_reached' in s]
    result['unavailable_legacy_gpu_probe']=('DM_NVN_PASSGPU' in log and not passes.exists())
    output=Path(str(base)+'.analysis.json');write_json(output,result)
    print(f"Reason: {result['reason']}; report: {output}")
    for key in ('@frame_ms','@gpu_ms','@nvn_ms','@depth_snapshots','@depth_snapshot_mb','@rt_load_mb','@rt_store_mb'):
        row=result.get('frame_metrics',{}).get(key)
        if row:print(f"{key}: p50={row['p50']}, p95={row['p95']}, max={row['max']} ({row['samples']} samples)")
    if passes.exists():print(f"GPU encoder observations: {result['gpu_passes']['rows']}; unavailable spans: {result['gpu_passes']['unavailable_spans']}")


if __name__=='__main__':main()
