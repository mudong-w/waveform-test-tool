import csv


def demo(out):
    with (out / "waveform.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s","CH1_V"])
        for i in range(60000):
            t = i / 4000
            phase = (t+.5) % 4
            v = 0
            if 1 <= phase < 4 and (phase-1) % .2 < .104:
                pulse = ((phase-1)*100 + 1e-8) % 1
                v = 10 if pulse < .12 else -10 if pulse < .24 else 0
            writer.writerow((f"{t:.6f}", v))
