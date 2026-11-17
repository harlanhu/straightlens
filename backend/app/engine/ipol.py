"""Subprocess boundary for the pinned IPOL reference program."""
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import time
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
BINARY = ROOT / 'third_party/ipol/lens_distortion_correction_2p_iterative_optimization'

class EngineError(RuntimeError):
    pass

@dataclass(frozen=True)
class CandidateConfig:
    model: str
    threshold: float
    optimize_center: bool = False
    start: float = -0.3
    stop: float = 1.0

@dataclass
class CandidateResult:
    config: CandidateConfig
    coefficients: tuple[float, ...]
    center: tuple[float, float]
    size: tuple[int, int]
    lines: list[np.ndarray]
    work_dir: Path
    strategy: str = 'native'
    validation: dict | None = None


def parse_primitives(path: Path, config: CandidateConfig, size: tuple[int,int]) -> CandidateResult:
    try:
        text = path.read_text()
        center_match = re.search(r'distortion center = \(([^)]+)\)', text)
        center = tuple(float(v) for v in center_match[1].split())
        coeff = tuple(float(v) for v in re.findall(r'value of distortion parameter \d+\s*=\s*(\S+)', text))
        if len(center) != 2 or len(coeff) not in (2,3) or not np.isfinite((*center,*coeff)).all():
            raise ValueError('invalid model')
        lines = []
        for block in text.split('line points :')[1:]:
            rows = block.strip().splitlines()
            count = int(rows[0])
            points = np.array([[float(v) for v in line.split()] for line in rows[1:count+1]])
            if points.shape != (count,2) or not np.isfinite(points).all():
                raise ValueError('invalid points')
            lines.append(points)
        return CandidateResult(config, coeff, center, size, lines, path.parent)
    except (OSError, ValueError, TypeError, IndexError) as exc:
        raise EngineError('算法未产生有效的参数文件') from exc


def run_ipol(input_png: Path, config: CandidateConfig, work_dir: Path, timeout_s: float, cancel_event=None) -> CandidateResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(input_png) as image:
        size = image.size
    args = [str(BINARY), str(input_png.resolve()), 'edges.png', 'lines.png', 'corrected.png',
            str(config.threshold), str(config.start), str(config.stop), '3', '10', config.model,
            'True' if config.optimize_center else 'False', 'primitives.txt']
    try:
        with (work_dir/'run.log').open('w') as log:
            run = subprocess.Popen(args, cwd=work_dir, stdout=log, stderr=subprocess.STDOUT)
            deadline=time.monotonic()+timeout_s
            try:
                while run.poll() is None:
                    if cancel_event is not None and cancel_event.is_set():
                        raise EngineError('任务已取消')
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise EngineError('算法计算超时')
                    try:run.wait(timeout=min(.15,remaining))
                    except subprocess.TimeoutExpired:pass
            finally:
                if run.poll() is None:
                    run.kill();run.wait()
        if run.returncode:
            raise EngineError(f'算法退出异常（{run.returncode}）')
    except OSError as exc:
        raise EngineError('算法程序不可用，请先编译') from exc
    primitives = work_dir/'primitives.txt'
    if not primitives.exists():
        # Upstream returns success for a no-lines result. Missing all output is not success.
        if (work_dir/'corrected.png').exists():
            return CandidateResult(config,(1.,0.,0.),(size[0]/2,size[1]/2),size,[],work_dir)
        raise EngineError('算法未产生有效输出')
    result = parse_primitives(primitives,config,size)
    if not (work_dir/'corrected.png').is_file():
        raise EngineError('算法缺少校正输出')
    return result
