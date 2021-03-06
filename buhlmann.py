# Project: diving_decompression
# File: test_buhlmann.py
# Created by BlueTrin at 15-May-20

import copy
import numbers
import numpy as np
import pandas as pd
import math
from prettytable import PrettyTable

ZHL_16C = pd.DataFrame([
    [1, 5.0, 1.1696, 0.5578, 1.88, 1.6189, 0.4770],
    [2, 8.0, 1.0000, 0.6514, 3.02, 1.3830, 0.5747],
    [3, 12.5, 0.8618, 0.7222, 4.72, 1.1919, 0.6527],
    [4, 18.5, 0.7562, 0.7825, 6.99, 1.0458, 0.7223],
    [5, 27.0, 0.6200, 0.8126, 10.21, 0.9220, 0.7582],
    [6, 38.3, 0.5043, 0.8434, 14.48, 0.8205, 0.7957],
    [7, 54.3, 0.4410, 0.8693, 20.53, 0.7305, 0.8279],
    [8, 77.0, 0.4000, 0.8910, 29.11, 0.6502, 0.8553],
    [9, 109.0, 0.3750, 0.9092, 41.20, 0.5950, 0.8757],
    [10, 146.0, 0.3500, 0.9222, 55.19, 0.5545, 0.8903],
    [11, 187.0, 0.3295, 0.9319, 70.69, 0.5333, 0.8997],
    [12, 239.0, 0.3065, 0.9403, 90.34, 0.5189, 0.9073],
    [13, 305.0, 0.2835, 0.9477, 115.29, 0.5181, 0.9122],
    [14, 390.0, 0.2610, 0.9544, 147.42, 0.5176, 0.9171],
    [15, 498.0, 0.2480, 0.9602, 188.24, 0.5172, 0.9217],
    [16, 635.0, 0.2327, 0.9653, 240.03, 0.5119, 0.9267],
],
    columns=['compartment',
             'n2_halflife', 'n2_a', 'n2_b',
             'he_halflife', 'he_a', 'he_b']
)


class GradientFactors:
    def __init__(self, gf_lo, pamb_lo, gf_hi, pamb_hi=1, t_first_stop=None):
        """
        :param gf_lo: gradient factor for first stop, usually between 0 and 1
        :param pamb_lo: ambiant pressure for the first stop
        :param gf_hi:  gradient factor for surfacing stop, usually between 0 and 1
        :param pamb_hi: ambiant pressure for the surface, assume 1 bar by default ?
        """
        self.gf_lo = gf_lo
        self.pamb_lo = pamb_lo
        self.gf_hi = gf_hi
        self.pamb_hi = pamb_hi
        self.t_first_stop = t_first_stop

    def gf(self, pamb, t=None):
        if t is not None and self.t_first_stop is not None and t <= self.t_first_stop:
            return self.gf_lo
        else:
            return self.gf_lo + \
                   (self.gf_hi - self.gf_lo) / (self.pamb_hi - self.pamb_lo) \
                   * (pamb - self.pamb_lo)


def generate_ascii_table(df):
    x = PrettyTable()
    x.field_names = df.columns.tolist()
    for row in df.values:
        x.add_row(row)
    print(x)
    return x


# in bar
SURFACE_PRESSURE = 1
WATER_VAPOR_PRESSURE_ALVEOLI = 0.0567

# in fsw
# SURFACE_PRESSURE = 33
# WATER_VAPOR_PRESSURE_ALVEOLI = 2.042

# 1st dive so 0.79 N2 and 0 HE
surface_n2_pp = 0.79


class Gas(object):
    def __init__(self, n2_pc, he_pc):
        if not 0 <= n2_pc <= 1:
            raise RuntimeError("N2 must be between 0 and 1")
        if not 0 <= he_pc <= 1:
            raise RuntimeError("He must be between 0 and 1")
        if not 0 <= n2_pc + he_pc <= 1:
            raise RuntimeError("He+N2 must be between 0 and 1")

        self.n2_pc = n2_pc
        self.he_pc = he_pc
        self.o2_pc = 1.0 - he_pc - n2_pc


class Tissues(object):
    def __init__(self, n2_p=None, he_p=None):
        # default tissues saturation for surface
        # Compute P0(He) and P0(N2)
        if n2_p is not None:
            self.n2_p = n2_p
        else:
            self.n2_p = pd.array([(SURFACE_PRESSURE - WATER_VAPOR_PRESSURE_ALVEOLI) * surface_n2_pp] * 16)

        if he_p is not None:
            self.he_p = he_p
        else:
            self.he_p = pd.array([0] * 16)


def get_partial_pressures(
        tissues,  # tissue loading vectors for compartments
        gas,  # gas composition
        start_pressure,  # in bar
        end_pressure,  # in bar
        t,  # time for depth change
):
    """

    :param t:
    :type tissues: Tissues
    :type gas: Gas
    :param start_pressure:
    :param end_pressure:
    """
    if t and t < 0:
        raise RuntimeError("Negative time")
    elif t:
        rate_depth = (end_pressure - start_pressure) / t
    else:
        rate_depth = 0

    # Compute P_{i,0}(He)
    init_inspired_pp_he = (start_pressure - WATER_VAPOR_PRESSURE_ALVEOLI) * gas.he_pc
    init_inspired_pp_n2 = (start_pressure - WATER_VAPOR_PRESSURE_ALVEOLI) * gas.n2_pc

    rate_change_he_p = rate_depth * gas.he_pc
    rate_change_n2_p = rate_depth * gas.n2_pc

    # Compute k(He)
    k_he = math.log(2) / ZHL_16C['he_halflife']

    # P(He) = Pi,0(He) + R(HE) (t - 1/k(He)) - (Pi,0(He) - P0(He) - R(He)/k(He)) exp(-2 k(He))
    p_he = init_inspired_pp_he + rate_change_he_p * (t - 1 / k_he) \
           - (init_inspired_pp_he - tissues.he_p - rate_change_he_p / k_he) \
           * np.exp(-k_he * t)

    k_n2 = math.log(2) / ZHL_16C['n2_halflife']
    p_n2 = init_inspired_pp_n2 + rate_change_n2_p * (t - 1 / k_n2) \
           - (init_inspired_pp_n2 - tissues.n2_p - rate_change_n2_p / k_n2) \
           * np.exp(-k_n2 * t)

    return Tissues(n2_p=p_n2, he_p=p_he)


def ceiling_pressure_by_tissue(
        tissues: Tissues,
        gf=1.0
) -> pd.DataFrame:
    """
    Return the ceiling (in bar)
    :param tissues:
    :param gf: gradient factor
    :return:
    """
    a = (ZHL_16C['n2_a'] * tissues.n2_p + ZHL_16C['he_a'] * tissues.he_p) / (tissues.n2_p + tissues.he_p)
    b = (ZHL_16C['n2_b'] * tissues.n2_p + ZHL_16C['he_b'] * tissues.he_p) / (tissues.n2_p + tissues.he_p)
    tissue_ceilings = ((tissues.n2_p + tissues.he_p) - gf * a) / (gf / b - gf + 1.0)
    return tissue_ceilings


def ceiling_pressure(
        tissues: Tissues,
        gf=1.0
) -> float:
    """
    Return the ceiling (in bar)
    :param tissues:
    :param gf: gradient factor
    :return:
    """
    return max(ceiling_pressure_by_tissue(tissues, gf))


def depth_to_pressure(depth):
    return depth / 10.0 + 1.0


def pressure_to_depth(pressure):
    return (pressure - 1.0) * 10.0


def round_depth_ceiling(raw_ceiling):
    # rounds to the closest multiple of 3 except if it is between 0 and 6 then we round to 6
    ceiling = math.ceil(raw_ceiling / 3) * 3
    if 0 < ceiling <= 6:
        return 6
    else:
        return ceiling


def try_stop(tissues: Tissues, depth_start: float, depth_end: float, gas: Gas, max_ascent_rate: float, gf) -> bool:
    # test if you can attempt this stop
    # - returns True if not violated ceiling
    # - returns False otherwise
    t_ascent = math.ceil((depth_start - depth_end) / max_ascent_rate)
    tissues_after_ascent = get_partial_pressures(
        tissues,
        gas,
        depth_to_pressure(depth_start),
        depth_to_pressure(depth_end),
        t_ascent)

    return pressure_to_depth(
        ceiling_pressure(tissues_after_ascent, gf=gf.gf(depth_to_pressure(depth_end)))) <= depth_end


def next_depth_stop(stop_depth):
    estimated_stop_depth = round_depth_ceiling(stop_depth)
    if estimated_stop_depth == 0:
        raise RuntimeError("Already at 0metres, cannot find shallower next stop")
    elif estimated_stop_depth <= 6:
        return 0
    else:
        return estimated_stop_depth - 3


def find_next_stop(tissues: Tissues, depth: float, gas: Gas, max_ascent_rate: float, gf=None) -> pd.DataFrame:
    if gf is None:
        # default to GF=1
        gf = GradientFactors(1, 10, 1, 0)
    elif isinstance(gf, numbers.Number):
        gf = GradientFactors(gf, 10, gf, 0)

    # finds the next stop that does not go past the ceiling
    depth_ceiling = pressure_to_depth(ceiling_pressure(tissues, gf.gf(depth)))
    estimated_stop_depth = round_depth_ceiling(depth_ceiling)
    if estimated_stop_depth != 0 and try_stop(tissues, depth, next_depth_stop(estimated_stop_depth), gas,
                                              max_ascent_rate, gf):
        # the off gas during the ascent allowed to use the next stop
        estimated_stop_depth = next_depth_stop(estimated_stop_depth)

    if estimated_stop_depth < depth:
        # we don't do fraction of minutes for planning
        t = math.ceil((depth - estimated_stop_depth) / max_ascent_rate)

        return pd.DataFrame([
            [0, depth],
            [t, estimated_stop_depth]
        ],
            columns=['t', 'depth'])
    else:
        # then we compute how much time we have to wait at the current depth before to move
        t_wait = 1
        while True:
            tissues_after_stop = get_partial_pressures(
                tissues,
                gas,
                depth_to_pressure(depth),
                depth_to_pressure(depth),
                t_wait)

            depth_ceiling = pressure_to_depth(ceiling_pressure(tissues_after_stop, gf.gf(depth)))
            estimated_stop_depth = round_depth_ceiling(depth_ceiling)

            if estimated_stop_depth != 0 and try_stop(tissues_after_stop, depth, next_depth_stop(estimated_stop_depth),
                                                      gas,
                                                      max_ascent_rate, gf):
                # the off gas during the ascent allowed to use the next stop
                estimated_stop_depth = next_depth_stop(estimated_stop_depth)

            if estimated_stop_depth < depth:
                t_ascent = math.ceil((depth - estimated_stop_depth) / max_ascent_rate)
                return pd.DataFrame([
                    [0, depth],
                    [t_wait, depth],
                    [t_wait + t_ascent, estimated_stop_depth]
                ],
                    columns=['t', 'depth']
                )

            t_wait += 1

            if t_wait > 1000:
                raise RuntimeError("looks like we cannot ascend after 1000 minutes of stop")


def get_stops_to_surface(tissues, depth, gas, max_ascent_rate, gf_lo=1.0, gf_hi=1.0):
    dive_plan = pd.DataFrame([
        [0, depth, tissues, pressure_to_depth(ceiling_pressure(tissues)), gf_lo],
    ],
        columns=['t', 'depth', 'tissues', 'ceiling', 'gf'])

    first_stop = True
    gf = None
    while True:
        # update state variables
        curr_depth = dive_plan.iloc[-1]['depth']
        curr_tissues = dive_plan.iloc[-1]['tissues']
        curr_time = dive_plan.iloc[-1]['t']

        if curr_depth <= 0:
            break

        if first_stop:
            # for the first stop just use a flat GF
            stop_info = find_next_stop(curr_tissues, curr_depth, gas, max_ascent_rate, gf=gf_lo)

            # now we know the GF line, last stop will be at 6
            if stop_info.iloc[-1]['depth'] < 6:
                raise RuntimeError("first stop was under 6m ???")
            elif stop_info.iloc[-1]['depth'] == 6:
                # there is only one stop
                gf = GradientFactors(gf_hi, 120, gf_hi, depth_to_pressure(6))
            else:
                gf = GradientFactors(gf_lo, depth_to_pressure(stop_info.iloc[-1]['depth']), gf_hi, depth_to_pressure(0))

            first_stop = False
        else:
            curr_gf = gf.gf(depth_to_pressure(curr_depth))
            if not gf_lo <= curr_gf <= gf_hi:
                raise RuntimeError("GF out of boundaries")

            stop_info = find_next_stop(curr_tissues, curr_depth, gas, max_ascent_rate,
                                       gf=curr_gf)

        # update times
        stop_info['t'] += curr_time

        if stop_info.iloc[-1]['depth'] >= curr_depth:
            raise RuntimeError("We didn't get a shallower stop")

        # update tissues
        run_stop_schedule = run_dive(stop_info, curr_tissues, gas)
        run_stop_schedule['gf'] = gf.gf(depth_to_pressure(run_stop_schedule['depth']))
        dive_plan = dive_plan.append(run_stop_schedule[1:])  # don't repeat the first entry

    return dive_plan


def run_dive(
        dive_plan,
        initial_tissues,
        gas,
        resolution=None,
        gf=None):
    """
    Run a dive and update the columns tissues and ceiling
    :param dive_plan: can be either a dataframe with columns 't' for time in minutes and 'depth' for depth in metres
    or can be a list of tuples (t, depth)
    :param initial_tissues:
    :param gas:
    :param resolution: resolution in minutes, we will return information at this resolution, if left to None, then we u
    only use the poinst of the dive plan
    :return:
    """
    if gf is None:
        gf = GradientFactors(1.0, depth_to_pressure(120), 1.0, depth_to_pressure(0), 0)

    init_pt = dive_plan.iloc[0]
    init_gf = gf.gf(depth_to_pressure(init_pt['depth']))
    updated_dive_plan_lst = [
        [init_pt['t'],
         init_pt['depth'],
         initial_tissues,
         pressure_to_depth(ceiling_pressure(initial_tissues, init_gf)),
         init_gf,
         ]]

    # tissues_lst = [initial_tissues]
    # ceiling_lst = []
    for start_idx, end_idx in zip(range(len(dive_plan) - 1), range(1, len(dive_plan))):

        start_depth = dive_plan.iloc[start_idx]['depth']
        start_time = dive_plan.iloc[start_idx]['t']

        end_depth = dive_plan.iloc[end_idx]['depth']
        end_time = dive_plan.iloc[end_idx]['t']

        if updated_dive_plan_lst[-1][1] != start_depth or updated_dive_plan_lst[-1][0] != start_time:
            raise RuntimeError("sanity check, we should start every iteration with the last row matching the start")

        start_tissues = updated_dive_plan_lst[-1][2]
        if resolution:
            step_time = start_time + resolution
        else:
            step_time = end_time

        while True:
            if step_time >= end_time:
                step_time = end_time
                step_depth = end_depth
            else:
                step_depth = start_depth + (end_depth - start_depth) / (end_time - start_time) * (
                        step_time - start_time)

            step_tissues = get_partial_pressures(
                start_tissues,
                gas,
                depth_to_pressure(start_depth),  # for example 0 feet
                depth_to_pressure(step_depth),  # for example 120 feet
                step_time - start_time,  # time for depth change
            )
            step_gf = gf.gf(depth_to_pressure(step_depth), step_time)
            updated_dive_plan_lst.append(
                [step_time,
                 step_depth,
                 step_tissues,
                 pressure_to_depth(ceiling_pressure(step_tissues, step_gf)),
                 step_gf
                 ]
            )

            if step_time == end_time or not resolution:
                break

            step_time += resolution

    updated_dive_plan = pd.DataFrame(updated_dive_plan_lst, columns=['t', 'depth', 'tissues', 'ceiling', 'gf'])
    return updated_dive_plan


def main():
    pass
    # generate_ascii_table(ZHL_16C)
    #
    # descent_rate = 20  # 20m / min
    # ascent_rate = 9  # 9m / min
    # gas = Gas(n2_pc=0.4, he_pc=0.45)
    #
    # dive = [
    #     (0, 0),
    #     (40, 2),  # 40 meters at 2 mins
    #     (40, 22),  # 40 meters at 22 mins
    # ]
    # tissues = Tissues()
    # print("initial ceiling: {}".format(pressure_to_depth(ceiling(tissues))))
    #
    # i_step = 0
    # ((start_time, start_depth), (end_time, end_depth)) = list(zip(dive[:-1], dive[1:]))[i_step]
    # tissues = get_partial_pressures(
    #     tissues,  # vector for compartments
    #     gas,
    #     depth_to_pressure(start_depth),  # for example 0 feet
    #     depth_to_pressure(end_depth),  # for example 120 feet
    #     end_time - start_time,  # time for depth change
    # )
    # print("N2tissues: {}".format(tissues.n2_p))
    # print("ceiling: {}".format(pressure_to_depth(ceiling(tissues))))
    # # tissues = get_partial_pressures(
    # #         tissues,  # vector for compartments
    # #         gas,
    # #         end_depth,    # for example 0 feet
    # #         end_depth,      # for example 120 feet
    # #         20,              # time for depth change
    # # )
    # # print("ceiling: {}".format(ceiling(tissues)))
