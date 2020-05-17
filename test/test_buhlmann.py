# Project: diving_decompression
# File: test_buhlmann.py
# Created by BlueTrin at 15-May-20

from unittest import TestCase

import buhlmann
import numpy.testing as npt
import math
import pandas as pd


class TestBuhlmann(TestCase):
    def test_zero_time(self):
        gas = buhlmann.Gas(n2_pc=0.45, he_pc=0.40)
        tissue = buhlmann.Tissues()
        new_tissue = buhlmann.get_partial_pressures(tissue, gas, buhlmann.depth_to_pressure(0),
                                                    buhlmann.depth_to_pressure(40), 0)
        npt.assert_array_equal(tissue.n2_p, new_tissue.n2_p)
        npt.assert_array_equal(tissue.he_p, new_tissue.he_p)

    def test_flat_bottom(self):
        gas = buhlmann.Gas(n2_pc=0.79, he_pc=0.0)
        tissue = buhlmann.Tissues()
        new_tissue = buhlmann.get_partial_pressures(tissue, gas, buhlmann.depth_to_pressure(40),
                                                    buhlmann.depth_to_pressure(40), 20)
        self.assertEqual(
            math.ceil(buhlmann.pressure_to_depth(buhlmann.ceiling(new_tissue))),
            6
        )

    def test_dive_plan(self):
        gas = buhlmann.Gas(n2_pc=0.79, he_pc=0.0)
        initial_tissues = buhlmann.Tissues()
        dive_plan = pd.DataFrame([
            [0, 0],
            [2, 40],
            [22, 40]],
            columns=['t', 'depth'])
        run_dive_plan = buhlmann.run_dive(dive_plan, initial_tissues, gas)
        current_tissues = run_dive_plan.iloc[-1]['tissues']
        current_depth = run_dive_plan.iloc[-1]['depth']
        max_ascent_rate = 9  # metres/sec
        run_stops = buhlmann.get_stops_to_surface(current_tissues, current_depth, gas, max_ascent_rate)
        run_stops['t'] += run_dive_plan.iloc[-1]['t']
        run_dive_plan = run_dive_plan.append(run_stops.iloc[1:])
        run_dive_plan.reset_index(inplace=True, drop=True)
        # get data resolution at 1 minute
        dive_data = buhlmann.run_dive(run_dive_plan, initial_tissues, gas, resolution=1)

        # check that we have all times in minutes
        self.assertTrue(
            dive_data.iloc[-1]['t'] > dive_plan.iloc[-1]['t'],
        )
        # check that every time is there
        self.assertEqual(
            list(dive_data['t']),
            list(range(len(dive_data)))
        )
        # check that we surfaced
        self.assertEqual(dive_data.iloc[-1]['depth'], 0)

    def test_gradient_factors(self):
        initial_tissues = buhlmann.Tissues()

        for gf_pc in list(range(0, 110, 10)):
            print("GF={}, ceiling={}".format(
                gf_pc / 100.0,
                buhlmann.pressure_to_depth(buhlmann.ceiling(initial_tissues, gf=gf_pc / 100.0))))

        gas = buhlmann.Gas(n2_pc=0.79, he_pc=0.0)
        initial_tissues = buhlmann.Tissues()
        dive_plan = pd.DataFrame([
            [0, 0],
            [2, 40],
            [22, 40]],
            columns=['t', 'depth'])
        run_dive_plan = buhlmann.run_dive(dive_plan, initial_tissues, gas)

        last_tissues = run_dive_plan.iloc[-1]['tissues']
        for gf_pc in list(range(0, 110, 10)):
            print("GF={}, ceiling={}".format(
                gf_pc / 100.0,
                buhlmann.pressure_to_depth(buhlmann.ceiling(last_tissues, gf=gf_pc / 100.0))))
