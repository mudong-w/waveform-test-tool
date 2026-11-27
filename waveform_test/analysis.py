"""Interval-first analysis for isolated pulse trains with observable idle gaps."""
import csv
from pathlib import Path
import numpy as np


def read_trace(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        if not {"time_s", "CH1_V"}.issubset(rows.fieldnames or []):
            raise ValueError("CSV 需要 time_s 和 CH1_V 两列")
        data = np.array([(float(r["time_s"]), float(r["CH1_V"])) for r in rows])
    if len(data) < 4 or not np.isfinite(data).all():
        raise ValueError("样本不足或含无效值")
    t, v = data.T
    steps = np.diff(t)
    dt = np.median(steps)
    if dt <= 0 or not np.allclose(steps, dt, rtol=.01, atol=dt*1e-5):
        raise ValueError("时间戳必须等间隔、递增且无缺样")
    return t, v, float(dt)


def find_cycle(t, v, dt, threshold, gap, stages, baseline):
    if not np.isfinite([threshold, gap, baseline]).all() or threshold <= 0 or gap <= dt:
        raise ValueError("阈值和分段间隔必须为有效正数，分段间隔应大于采样间隔")
    active = np.flatnonzero(np.abs(v-baseline) >= threshold)
    if not len(active):
        raise ValueError("阈值范围内没有脉冲")
    chunks = np.split(active, np.flatnonzero(np.diff(active)*dt >= gap)+1)
    spans = [(int(c[0]), int(c[-1]+1)) for c in chunks]
    gaps = np.array([(b[0]-a[1])*dt for a,b in zip(spans,spans[1:])])
    if len(gaps) < 2:
        raise ValueError("至少需要两个完整间隔和下一轮输出，请延长记录或检查阈值")
    def close(a,b):
        return abs(a-b) <= max(4*dt,.10*max(a,b))
    longest = float(np.max(gaps))
    for i, pause in enumerate(gaps):
        if not close(pause, longest):
            continue
        candidates = [i+stages] if stages is not None else range(i+1,len(gaps))
        for j in candidates:
            if j >= len(gaps) or j <= i or not close(pause,gaps[j]):
                continue
            count = j-i
            # Check all available repetitions, including the clipped final segment.
            ok = True
            for k in range(j,len(gaps)):
                ref = i+(k-i)%count
                a,b = spans[ref+1]
                c,d = spans[k+1]
                observed, expected = (d-c)*dt, (b-a)*dt
                if not close(gaps[ref],gaps[k]):
                    ok = False
                    break
                if k+1 < len(spans)-1 and not close(expected,observed):
                    ok = False
                    break
                if k+1 == len(spans)-1 and observed > expected+max(4*dt,.1*expected):
                    ok = False
                    break
                # Compare pulse occupancy and amplitude on the common visible portion.
                n = min(b-a,d-c)
                for u,w in zip(np.array_split(v[a:a+n]-baseline, min(4,n)), np.array_split(v[c:c+n]-baseline,min(4,n))):
                    p,q = np.mean(abs(u)>=threshold), np.mean(abs(w)>=threshold)
                    if abs(p-q) > .25 or abs(np.max(abs(u))-np.max(abs(w))) > max(threshold,.3*max(np.max(abs(u)),np.max(abs(w)))):
                        ok = False
                        break
                if not ok:
                    break
            recurrence = (spans[j+1][1]-spans[j+1][0])*dt
            if ok and recurrence >= min(.25,.5*(spans[i+1][1]-spans[i+1][0])*dt):
                parts = []
                for k in range(i,j):
                    parts.extend([(f"gap{k-i+1}",spans[k][1],spans[k+1][0]),
                                  (f"t{k-i+1}",*spans[k+1])])
                return parts, spans[j+1][0], recurrence
    raise ValueError("未确认从间隔开始的完整周期及可见复现。检查长记录、分段间隔和每轮段数")


def pulse_metrics(t,v,dt,threshold,baseline,packet_gap):
    # One polarity avoids double-counting the two phases of bipolar pulses.
    y = v-baseline
    polarity = 1 if np.max(y) >= abs(np.min(y))*.8 else -1
    high = polarity*y >= threshold
    events = np.flatnonzero(high & ~np.r_[False, high[:-1]])
    times = t[events]
    delta = np.diff(times)
    if not len(delta):
        return [], [], None
    packets = np.split(times,np.flatnonzero(delta >= packet_gap)+1)
    within = delta < packet_gap
    if np.any(within) and np.median(delta[within]) < 4*dt*(1-1e-5):
        within[:] = False
    f_t = ((times[:-1]+times[1:])/2)[within]
    hz = 1/delta[within]
    group_hz = None
    if len(packets)>=3 and all(len(p)>=2 for p in packets[1:-1]):
        periods = np.diff([p[0] for p in packets])
        if np.max(abs(periods-np.median(periods))) <= .2*np.median(periods):
            group_hz = float(1/np.median(periods))
    return f_t.tolist(), hz.tolist(), group_hz
