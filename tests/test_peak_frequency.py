import unittest

import numpy as np

from waveform_test.peak_frequency import frequency_windows, resolved_intervals


class PeakDetectTest(unittest.TestCase):
    def test_alternating_bipolar_buckets_across_rate_change(self):
        dt = .0025
        volts = np.zeros(1600)
        for start,rate in [(0,82.),(2,118.)]:
            buckets = np.floor((start + np.arange(0,2,1/rate))/(2*dt)).astype(int)
            for index,bucket in enumerate(buckets):
                volts[2*bucket:2*bucket+2] = [12,-10] if index%2==0 else [-10,12]
        points = np.array(frequency_windows(volts,dt,3,0,.05,False))
        for low,high,expected in [(.15,1.85,82),(2.15,3.85,118)]:
            actual = points[(points[:,0]>low)&(points[:,0]<high),1]
            self.assertGreater(len(actual),5)
            self.assertAlmostEqual(float(np.median(actual)),expected,delta=1.5)
        self.assertEqual(frequency_windows(abs(volts),dt,3,0,.05,False),[])
        self.assertEqual(resolved_intervals(np.arange(10)*.01,[100]*10,dt),[])
