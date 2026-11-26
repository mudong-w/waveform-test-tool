"""CH1 USBTMC adapter for the UTD2202CEX+ instrument profile."""
import csv
from contextlib import closing
from datetime import datetime
import math
from statistics import fmean
import struct
import os
import pyvisa
from .storage import write_json


def manager():
    return pyvisa.ResourceManager(os.environ.get("WAVEFORM_VISA_LIBRARY", ""))


def matching(rm):
    return [s for s in rm.list_resources() if s.upper().startswith("USB") and
            "::0X5656::0X0832::" in s.upper() and s.upper().endswith("::INSTR")]


def devices():
    with closing(manager()) as rm:
        return matching(rm)


def request_block(scope, first, stop, max_read):
    scope.write(f':WAV:STAR {first}')
    scope.write(f':WAV:STOP {stop}')
    scope.write(f':WAV:POIN {stop-first}')
    scope.write(':WAV:DATA?')
    block, _ = scope.visalib.read(scope.session, max_read)
    if len(block) < 3 or not block.startswith(b'#'):
        raise ValueError(f'Unexpected waveform block header: {block[:20]!r}.')
    width = int(chr(block[1]))
    if width == 0:
        raise ValueError('The waveform block did not include a length.')
    start = 2 + width
    size = int(block[2:start])
    data = block[start:start+size]
    if len(data) != size or block[start+size:] not in (b'', b'\r\n', b'\n', b',\r'):
        raise ValueError(f'Incomplete waveform block. Expected {size} data bytes, got {len(data)}.')
    return data


def capture_screen(scope):
    scope.write(':DISP:DATA?')
    block, _ = scope.visalib.read(scope.session, 4 * 1024 * 1024)
    if not block.startswith(b'#'):
        raise ValueError('Unexpected screen image header.')
    start = 2 + int(chr(block[1]))
    size = int(block[2:start])
    bmp = block[start:start+size]
    if not bmp.startswith(b'BM') or len(bmp) != size or struct.unpack_from('<I', bmp, 2)[0] != size:
        raise ValueError('The screen image block does not contain a complete BMP.')
    return bmp


def capture(scope, screen_path=None):
    identity = scope.query('*IDN?').strip()
    if not identity.upper().startswith("UNI-TREND"):
        raise ValueError("不支持该仪器的标识")
    status = scope.query(':TRIG:STAT?').strip()
    if status not in ('SCAN', 'AUTO', 'TRIGED', 'ARMED', 'READY', 'STOP'):
        raise ValueError(f'Unexpected trigger state: {status!r}.')

    metadata = {
        'manufacturer': identity.split(',')[0],
        'driver_profile': 'UTD2202CEX+',
        'channel': 'CH1',
        'acquired_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'seconds_per_div': float(scope.query(':TIM:SCAL?')),
        'volts_per_div': float(scope.query(':CHAN1:SCAL?')),
        'probe_attenuation': float(scope.query(':CHAN1:PROB?')),
        'coupling': scope.query(':CHAN1:COUP?').strip(),
        'counter_hz': scope.query(':SYST:CYMO:FREQ?').strip(),
        'trigger_before_capture': status,
    }
    keys = (':WAV:SOUR', ':WAV:MODE', ':WAV:FORM', ':WAV:STAR', ':WAV:STOP', ':WAV:POIN')
    previous = {key: scope.query(key+'?').strip() for key in keys}
    try:
        if status != 'STOP':
            scope.write(':STOP')
        if scope.query(':TRIG:STAT?').strip() != 'STOP':
            raise RuntimeError('The scope did not hold the current acquisition.')
        if screen_path is not None:
            screen_path.write_bytes(capture_screen(scope))
        scope.write(':WAV:SOUR CHAN1')
        scope.write(':WAV:MODE RAW')
        scope.write(':WAV:FORM BYTE')
        preamble = scope.query(':WAV:PRE?').strip()
        _, _, _, _, dt, time_zero, time_ref, y_scale, y_origin, y_ref = preamble.split(',')
        dt, time_zero, time_ref, y_scale, y_origin, y_ref = map(
            float, (dt, time_zero, time_ref, y_scale, y_origin, y_ref)
        )
        if dt <= 0 or y_scale <= 0:
            raise ValueError(f'Invalid waveform scaling: {preamble!r}.')
        stop_index = int(scope.query(':WAV:STOP?'))

        if stop_index < 34:
            raise ValueError('波形读取范围过短')
        first_sample = 1
        all_codes = bytearray()
        for first in range(first_sample, stop_index, 1024):
            stop = min(first + 1024, stop_index)
            data = request_block(scope, first, stop, 4096)
            if len(data) != stop-first:
                raise ValueError(f'Expected {stop-first} BYTE samples at index {first}, got {len(data)}.')
            all_codes.extend(data)

        times = [time_zero + (i - time_ref) * dt for i in range(first_sample, stop_index)]
        volts = [(code - y_origin - y_ref) * y_scale for code in all_codes]

        index = min(max(0, all_codes.index(max(all_codes)) - 8), len(volts) - 32)
        ascii_check_error = None
        actual_check_volts = None
        try:
            scope.write(':WAV:FORM ASCII')
            ascii_data = request_block(scope, index + first_sample, index + first_sample + 32, 4096)
            actual_check_volts = [float(value) for value in ascii_data.strip().split(b',')]
            if len(actual_check_volts) != 32:
                raise ValueError(f'Unexpected ASCII check length: {len(actual_check_volts)}.')
        except (ValueError, pyvisa.errors.VisaIOError) as error:
            ascii_check_error = str(error)

        if actual_check_volts is not None:
            difference = max(abs(a-b) for a,b in zip(volts[index:index+32], actual_check_volts))
            metadata['ascii_crosscheck_max_difference_v'] = difference
            if difference > 0.51 * y_scale:
                raise ValueError(f'BYTE and ASCII calibration disagree by {difference:g} V.')
        elif ascii_check_error:
            metadata['ascii_check_error'] = ascii_check_error

        metadata.update(
            sample_count=len(volts), sample_interval_s=dt, sample_rate_hz=1/dt,
            duration_s=times[-1]-times[0], raw_preamble=preamble, first_raw_index=first_sample,
            resolution_v_per_code=y_scale, min_v=min(volts), max_v=max(volts),
            peak_to_peak_v=max(volts)-min(volts), mean_v=fmean(volts),
            rms_v=math.sqrt(fmean(v*v for v in volts)),
            full_scale_adc_samples=sum(code in (0,255) for code in all_codes),
        )
    finally:
        try:
            for key in keys:
                scope.write(f'{key} {previous[key]}')
        finally:
            if status != 'STOP':
                scope.write(':RUN')
        metadata['trigger_after_capture'] = scope.query(':TRIG:STAT?').strip()

    return times, volts, all_codes, metadata



def export(out, resource=None):
    with closing(manager()) as rm:
        available = matching(rm)
        if resource is None and len(available) == 1:
            resource = available[0]
        if resource not in available:
            raise ValueError("请连接支持的设备；多台时用 --resource 指定地址")
        with rm.open_resource(resource, timeout=5000, write_termination="\n") as scope:
            times, volts, codes, metadata = capture(scope, out / "screen-original.bmp")
    with (out / "waveform.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "CH1_V", "adc_code"])
        writer.writerows(zip(times, volts, codes))
    write_json(out / "capture.json", metadata)
