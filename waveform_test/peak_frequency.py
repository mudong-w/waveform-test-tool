"""Frequency evidence from alternating bipolar pulses in UNI-T peak-detect buckets."""
import numpy as np


def bipolar_events(volts, threshold, baseline):
    """Choose the pair alignment that captures both polarities in one bucket."""
    candidates = []
    for offset in (0, 1):
        length = (len(volts)-offset)//2*2
        if length <= 0:
            return None
        pairs = (volts[offset:offset+length]-baseline).reshape(-1, 2)
        complete = (pairs.min(axis=1) <= -threshold) & (pairs.max(axis=1) >= threshold)
        buckets = np.flatnonzero(complete)
        candidates.append((2*buckets+offset, np.sign(pairs[buckets,0])))
    candidates.sort(key=lambda c: len(c[0]), reverse=True)
    events, order = candidates[0]
    if len(events) < 8 or len(events) < 2 * max(1,len(candidates[1][0])):
        return None
    return events, order


def alternating_rate(samples, signs, dt):
    """Estimate pulse rate only when polarity order and timing both agree."""
    if len(samples) < 5:
        return None
    # A repeated leading polarity can indicate one missed pulse. Check that
    # inference against the time residual of every detected bucket.
    advances = np.where(np.diff(signs) == 0, 2, 1)
    if np.mean(advances == 2) > .25:
        return None
    cycles = np.r_[0, np.cumsum(advances)]
    stamps = samples - samples[0]
    slope, intercept = np.polyfit(cycles, stamps, 1)
    if slope < 3 or np.max(abs(stamps - (intercept+slope*cycles))) > 2.5:
        return None
    return float(1/(slope*dt))


def frequency_windows(volts, dt, threshold, baseline, packet_gap, grouped):
    pair = bipolar_events(volts,threshold,baseline)
    if pair is None:
        return []
    events, signs = pair
    splits = np.flatnonzero(np.diff(events)*dt >= packet_gap)+1 if grouped else []
    groups = np.split(np.arange(len(events)), splits)
    points = []
    window = max(1,round(.22/dt))
    for group in groups:
        if len(group)<5:
            continue
        first,last = events[group[0]],events[group[-1]]
        for ids in np.array_split(group, max(1,round((last-first)/window))):
            rate = alternating_rate(events[ids],signs[ids],dt)
            if rate is not None:
                points.append((float((events[ids[0]]+events[ids[-1]])*.5*dt),rate))
    return points


def resolved_intervals(times, rates, dt):
    """Summarize contiguous, sufficiently resolved intervals over elapsed time."""
    times, rates = np.asarray(times), np.asarray(rates)
    if not len(times):
        return []
    result = []
    for ids in np.split(np.arange(len(times)), np.flatnonzero(np.diff(times)>.22)+1):
        bins = ((times[ids]-times[ids[0]])/.22).astype(int)
        for window in np.split(ids, np.flatnonzero(np.diff(bins))+1):
            periods = 1/rates[window]
            if len(window)>=3 and np.min(periods)>=8*dt*(1-1e-5):
                result.append((float(np.mean(times[window])),float(1/np.mean(periods))))
    return result
