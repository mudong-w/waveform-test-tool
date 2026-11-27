"""Reviewed report curves, expressed in fractions of each stage's adopted duration."""
import json
from pathlib import Path

import numpy as np


def read_profiles(path, stages):
    if path is None:
        return {}
    spec = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(spec, dict) or set(spec) - set(stages):
        raise ValueError("幅频采用值只能指定当前识别出的输出段")
    for name, curves in spec.items():
        if not isinstance(curves, dict) or not curves or set(curves) - {"amplitude_vpp", "frequency_hz"}:
            raise ValueError(f"{name} 需要 amplitude_vpp 或 frequency_hz 曲线")
        for key, points in curves.items():
            values = np.asarray(points)
            if (values.dtype.kind not in "ifu" or values.ndim != 2 or values.shape[1] != 2
                    or len(values) < 2 or not np.isfinite(values).all()):
                raise ValueError(f"{name}.{key} 需要有限的数值坐标对")
            x, y = values.T
            if x[0] != 0 or x[-1] != 1 or np.any(np.diff(x) < 0) or np.any(y < 0):
                raise ValueError(f"{name}.{key} 横坐标须从 0 递增至 1，纵坐标须为非负值")
    return spec


def active_windows(volts, threshold, baseline, dt, packet_gap):
    """Detect real packet silences in an already confirmed grouped output stage."""
    active = np.flatnonzero(abs(volts - baseline) >= threshold)
    if not len(active):
        return []
    packets = np.split(active, np.flatnonzero(np.diff(active)*dt >= packet_gap) + 1)
    return [(p[0]/len(volts), (p[-1]+1)/len(volts)) for p in packets]


def report_points(points, start, duration, windows):
    x, y = np.asarray(points, dtype=float).T
    if windows is None:
        return list(start + x*duration), list(y)
    trace = [(start, 0.)]
    for left, right in windows:
        first, last = start + left*duration, start + right*duration
        # Keep duplicate x coordinates for genuine steps; at a packet end use the left limit.
        inside = (x >= left) & (x <= right)
        trace.append((first, 0.))
        if not np.any(x == left):
            trace.append((first, float(np.interp(left, x, y))))
        trace.extend(zip(start + x[inside]*duration, y[inside]))
        if not np.any(x == right):
            trace.append((last, float(np.interp(right, x, y))))
        trace.append((last, 0.))
    trace.append((start+duration, 0.))
    xx, yy = zip(*trace)
    return list(xx), list(yy)


def range_label(curve, unit):
    levels = [p[1] for p in curve]
    low, high = min(levels), max(levels)
    return (f"{low:g}" if low == high else f"{low:g}–{high:g}") + " " + unit
