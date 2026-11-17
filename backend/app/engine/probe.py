"""Read-only probe of finished job artifacts for offline strategy tuning."""
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
from .ipol import CandidateConfig, parse_primitives
from .policy import evaluate

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / '.runtime' / 'jobs'


@dataclass
class EstimateBundle:
    job_id: str
    size: tuple[int, int]
    estimate_path: Path
    primitive_paths: list[Path]
    candidates: list = None

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = [self._load(path) for path in self.primitive_paths]

    def _load(self, path: Path):
        parts = path.parent.name.split('-')
        if parts[0] == 'center':
            config = CandidateConfig(parts[1], .8, True)
        else:
            config = CandidateConfig(parts[0], float(parts[1]))
        return parse_primitives(path, config, self.size)


@dataclass
class ProbeReport:
    job_id: str
    filename: str
    outcome: str
    reason_code: str
    per_candidate: list[dict]


def load_job_estimate(job_id: str, jobs_root: Path=JOBS) -> EstimateBundle:
    folder = jobs_root / job_id
    if not folder.is_dir():
        raise FileNotFoundError(job_id)
    with Image.open(folder / 'estimate.png') as image:
        size = image.size
    paths = sorted(p for p in folder.glob('*/primitives.txt'))
    if len(paths) < 1:
        raise FileNotFoundError(f'no primitives under {folder}')
    return EstimateBundle(job_id, size, folder / 'estimate.png', paths)


def probe_report(job_id: str) -> ProbeReport:
    import json
    bundle = load_job_estimate(job_id)
    record = json.loads((JOBS / job_id / 'job.json').read_text())
    rows = []
    for path, candidate in zip(bundle.primitive_paths, bundle.candidates):
        metrics = evaluate(candidate)
        rows.append({
            'candidate': path.parent.name,
            'lines': len(candidate.lines),
            'metrics': metrics,
        })
    return ProbeReport(job_id, record.get('filename', ''), record.get('outcome', ''),
                       record.get('reason_code', ''), rows)
