#!/usr/bin/env python3
"""Offline probe of finished jobs; prints per-candidate metrics for tuning."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.engine.probe import probe_report

JOBS = {
    '1': '8931daf8554d49ae8e7da39f97b8a48f',
    '2': 'c58b87f295c74becb7619bf324d820fa',
    '3': 'cb4230d548d3481484735f8e046b30a9',
    '4': 'e37ab74b25684ef5a74ec1bb8d3cb050',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--jobs', default=','.join(JOBS.values()))
    parser.add_argument('--out', type=Path, default=ROOT / 'evaluation' / 'probe-report.json')
    args = parser.parse_args()
    reports = []
    for job_id in [j for j in args.jobs.split(',') if j]:
        report = probe_report(job_id)
        reports.append(report)
        print(json.dumps({
            'label': next((k for k, v in JOBS.items() if v == job_id), job_id[:8]),
            'filename': report.filename,
            'outcome': report.outcome,
            'reason_code': report.reason_code,
            'per_candidate': report.per_candidate,
        }, ensure_ascii=False), flush=True)
    args.out.write_text(json.dumps(
        [{'job_id': r.job_id, 'filename': r.filename, 'outcome': r.outcome,
          'reason_code': r.reason_code, 'per_candidate': r.per_candidate} for r in reports],
        ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
