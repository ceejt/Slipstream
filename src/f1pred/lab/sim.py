"""Lap-by-lap race simulator.

Every lap, each car's time is its pace plus the compound offset, tyre wear and the fuel slope, plus noise.
A car cannot get ahead of the one in front unless it is faster by a margin; otherwise it is held behind.
Pit stops cost the pit loss and change the compound. Cars can retire, and a safety car can bunch the field.
All of it runs for thousands of races at once as arrays: axis 0 is the simulation, axis 1 the car.
"""
from dataclasses import dataclass, field

import numpy as np

MAX_STINTS = 4


@dataclass
class Setup:
    laps: int
    grid: np.ndarray          # starting position per car, 1 = pole; or one row per simulation, shape (n, cars)
    pace: np.ndarray          # s per lap vs the field, lower is faster; or one row per simulation, shape (n, cars)
    pace_sd: float            # race-to-race uncertainty of that pace
    comp_off: dict
    deg: dict
    fuel: float               # s per lap, negative: cars get faster as fuel burns
    pit_loss: float
    pit_sd: float
    lap_sd: float
    p_dnf: np.ndarray         # chance each car retires during the race
    p_sc: float = 0.0         # chance of a safety car
    plans: list = field(default_factory=list)  # [(pit_laps, compounds)] to sample from, or one per car in `fixed`
    fixed: list = None        # one (pit_laps, compounds) per car, overrides plans
    dnf_laps: np.ndarray = None   # known retirement lap per car (np.inf if none), used when replaying a race
    margin: float = 0.8       # pace advantage needed to pass, seconds per lap
    gap: float = 0.3          # closest a following car gets, seconds
    sc_laps: int = 4
    pit_jitter: float = 2.5   # laps; cars on the same plan still stop at different times
    grid_step: float = 0.25   # seconds between grid slots


def _plan_arrays(s, n, rng, D):
    pit = np.full((n, D, MAX_STINTS - 1), 10 ** 6)
    comp = np.zeros((n, D, MAX_STINTS), dtype=int)
    names = ["SOFT", "MEDIUM", "HARD"]
    if s.fixed is not None:
        pool = [s.fixed[d] for d in range(D)]
        pick = np.tile(np.arange(D), (n, 1))
    else:
        pool = s.plans
        pick = np.repeat(rng.integers(0, len(pool), size=(n, 1)), D, axis=1)  # the whole field follows one plan
    pa = np.full((len(pool), MAX_STINTS - 1), 10 ** 6)
    ca = np.zeros((len(pool), MAX_STINTS), dtype=int)
    for i, (laps, comps) in enumerate(pool):
        laps, comps = laps[:MAX_STINTS - 1], comps[:MAX_STINTS]
        pa[i, :len(laps)] = laps
        for j, c in enumerate(comps):
            ca[i, j] = names.index(c) if c in names else 1
        ca[i, len(comps):] = ca[i, max(len(comps) - 1, 0)]
    pit = pa[pick]
    if s.fixed is None:
        pit = np.where(pit < 10 ** 5, pit + np.rint(rng.normal(0, s.pit_jitter, pit.shape)).astype(int), pit)
    return pit, ca[pick]


def simulate(s: Setup, n=1000, seed=0):
    """Returns finishing positions, shape (n, cars); 1 is the winner."""
    rng = np.random.default_rng(seed)
    D = s.grid.shape[-1]
    names = ["SOFT", "MEDIUM", "HARD"]
    off = np.array([s.comp_off[k] for k in names])
    deg = np.array([s.deg[k] for k in names])
    pit_at, comp_of = _plan_arrays(s, n, rng, D)

    pace = (s.pace if s.pace.ndim == 2 else s.pace[None, :]) + rng.normal(0, s.pace_sd, (n, D))
    cum = ((s.grid - 1) * s.grid_step if s.grid.ndim == 2 else np.tile((s.grid - 1) * s.grid_step, (n, 1))).astype(float)
    stint = np.zeros((n, D), dtype=int)
    age = np.zeros((n, D))
    if s.dnf_laps is not None:
        out_lap = np.tile(s.dnf_laps, (n, 1)).astype(float)
    else:
        out_lap = np.where(rng.random((n, D)) < s.p_dnf[None, :], rng.integers(1, s.laps + 1, (n, D)), np.inf)
    sc_start = np.where(rng.random(n) < s.p_sc, rng.integers(3, max(s.laps - s.sc_laps, 4), n), -10)
    rows = np.arange(n)[:, None]

    for lap in range(1, s.laps + 1):
        alive = out_lap >= lap
        sc = (lap >= sc_start) & (lap < sc_start + s.sc_laps)
        c = np.take_along_axis(comp_of, stint[..., None], 2)[..., 0]
        t = pace + off[c] + deg[c] * age + s.fuel * lap + rng.normal(0, s.lap_sd, (n, D))
        nxt = np.take_along_axis(pit_at, np.minimum(stint, MAX_STINTS - 2)[..., None], 2)[..., 0]
        pitting = (nxt == lap) & (stint < MAX_STINTS - 1) & alive
        loss = np.maximum(s.pit_loss + rng.normal(0, s.pit_sd, (n, D)), 12)
        t = t + np.where(pitting, np.where(sc[:, None], 0.45 * loss, loss), 0)
        stint = stint + pitting
        age = np.where(pitting, 0, age + 1)

        free = np.where(alive, cum + t, cum)
        order = np.argsort(np.where(alive, cum, 1e9 + cum), axis=1)
        new = np.empty_like(free)
        lead = order[:, 0]
        new[np.arange(n), lead] = free[np.arange(n), lead]
        for k in range(1, D):
            ahead, me = order[:, k - 1], order[:, k]
            cap = new[np.arange(n), ahead] + s.gap
            f = free[np.arange(n), me]
            need = s.margin * np.exp(rng.normal(0, 0.4, n))  # how much faster than the car ahead it must be to get by
            blocked = (f < cap) & (cap - f < need) & alive[np.arange(n), me] & alive[np.arange(n), ahead]
            new[np.arange(n), me] = np.where(blocked, cap, f)
        # a safety car closes the gaps
        if sc.any():
            idx = np.argsort(np.where(alive, new, 1e9 + new), axis=1)
            sorted_new = np.take_along_axis(new, idx, 1)
            bunch = sorted_new[:, :1] + 0.4 * np.arange(D)[None, :]
            bunched = np.where(sc[:, None], np.minimum(sorted_new, np.maximum(bunch, sorted_new[:, :1])), sorted_new)
            new = np.empty_like(new)
            np.put_along_axis(new, idx, bunched, 1)
        cum = new
    laps_done = np.minimum(out_lap, s.laps)
    key = np.where(out_lap < s.laps + 1, 1e6 + (s.laps - laps_done) * 1e3 + cum * 1e-3, cum)
    rank = np.argsort(np.argsort(key, axis=1), axis=1) + 1
    return rank
