"""Public, user-facing distortion report derived from the applied transform."""
from pathlib import Path
import json
import math
from typing import Any

import numpy as np
from PIL import Image

from .engine.remap import correct_points
from .engine.transforms import load_transform


def _profile(directory: Path, spec) -> dict[str, Any]:
    w, h = spec.original_size
    cx, cy = spec.center
    radius = min(w, h) * 0.5
    deltas: list[float] = []
    for fraction in (0.25, 0.5, 0.75, 0.95):
        for angle in np.linspace(0, math.tau, 16, endpoint=False):
            point = np.array([[cx + radius * fraction * math.cos(angle), cy + radius * fraction * math.sin(angle)]])
            corrected = correct_points(point, spec.as_candidate())[0]
            before = float(np.linalg.norm(point[0] - np.array([cx, cy])))
            after = float(np.linalg.norm(corrected - np.array([cx, cy])))
            if before > 0:
                deltas.append(1.0 - after / before)
    edge = deltas[-64:] if len(deltas) >= 64 else deltas
    median = float(np.median(deltas)) if deltas else 0.0
    edge_max = max((abs(value) for value in edge), default=0.0)
    signs = [value for value in deltas if abs(value) > 0.0005]
    if not signs or max(abs(value) for value in signs) < 0.01:
        profile, profile_label = 'neutral', '轻微畸变'
    elif min(signs) < -0.002 and max(signs) > 0.002:
        profile, profile_label = 'mustache', '胡须形畸变'
    elif median > 0:
        # A positive correction delta means the correction pulls edge points inward;
        # the source image therefore exhibits pincushion distortion.
        profile, profile_label = 'pincushion', '枕形畸变'
    else:
        profile, profile_label = 'barrel', '桶形畸变'
    strength_value = edge_max * 100
    if strength_value < 1:
        strength, strength_label = 'light', '轻微'
    elif strength_value < 3:
        strength, strength_label = 'low', '低'
    elif strength_value < 7:
        strength, strength_label = 'medium', '中等'
    elif strength_value < 12:
        strength, strength_label = 'strong', '明显'
    else:
        strength, strength_label = 'very_strong', '强烈'
    x0, y0, x1, y1 = spec.crop
    retained = (x1 - x0) * (y1 - y0) / (w * h)
    center_offset_x = cx - w / 2
    center_offset_y = cy - h / 2
    return {
        'available': True,
        'profile': profile,
        'profile_label': profile_label,
        'strength': strength,
        'strength_label': strength_label,
        'edge_correction_percent': round(edge_max * 100, 2),
        'center': {
            'x': round(cx, 2), 'y': round(cy, 2),
            'x_percent': round(cx / w * 100, 2), 'y_percent': round(cy / h * 100, 2),
            'offset_x': round(center_offset_x, 2), 'offset_y': round(center_offset_y, 2),
        },
        'model': {
            'type': spec.model,
            'label': '径向除法模型' if spec.model == 'div' else '径向多项式模型',
            'coefficients': [round(float(value), 8) for value in spec.coefficients],
            'estimation_size': {'width': spec.estimation_size[0], 'height': spec.estimation_size[1]},
            'render_scale': round(spec.render_scale, 6),
            'version': spec.version,
        },
        'crop': {
            'left': x0, 'top': y0, 'right': w - x1, 'bottom': h - y1,
            'retained_area': round(retained, 4),
        },
    }


def describe_exif(source: Path) -> dict[str, Any] | None:
    try:
        with Image.open(source) as image:
            exif = image.getexif()
            if not exif:
                return None
            fields = {
                'make': exif.get(271), 'model': exif.get(272), 'lens': exif.get(42036),
                'focal_length': exif.get(37386), 'f_number': exif.get(33437),
            }
            values = {key: value for key, value in fields.items() if value is not None}
            return values or None
    except (OSError, ValueError):
        return None


def describe_distortion(directory: Path, record: dict[str, Any]) -> dict[str, Any]:
    if record.get('status') != 'succeeded' or record.get('outcome') != 'corrected':
        return {'available': False, 'reason_code': record.get('reason_code')}
    try:
        report = _profile(directory, load_transform(directory))
        report['exif'] = describe_exif(directory / 'source')
        return report
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {'available': False, 'reason_code': 'model_unavailable', 'reason_label': '校正模型记录不可用'}
