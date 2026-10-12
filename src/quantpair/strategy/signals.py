"""Module D - threshold state machine turning a z-score into target positions.

position +1 = long spread (long y, short beta*x): taken when z <= -entry
position -1 = short spread (short y, long beta*x): taken when z >= +entry
Exits (checked in this order while a position is open):
  stop      z moved further against us beyond the stop threshold
  exit      z reverted inside the exit band (long: z >= -exit; short: z <= exit)
  max_hold  position held for max_hold sessions
After a stop or max-hold exit the pair is blocked until |z| < entry, so the
strategy does not instantly re-enter the trade it just abandoned. Positions
never flip in one bar: a long that overshoots to z >= +entry exits first and
can only go short on a later bar. A NaN z keeps the current state.
The output is the *desired* position at the close of each date; execution
(and its lag) is handled by the backtester.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_positions(z: pd.Series, entry: float, exit: float, stop: float | None = None,
                       max_hold: int | None = None, allow_entry: pd.Series | None = None) -> pd.DataFrame:
    """allow_entry (optional): boolean per date; False suppresses new entries only."""
    if not 0 <= exit < entry:
        raise ValueError("Require 0 <= exit < entry.")
    if stop is not None and stop <= entry:
        raise ValueError("stop must exceed entry.")
    pos, held, blocked = 0, 0, False
    out_pos = np.zeros(len(z), dtype=int)
    out_evt = np.full(len(z), "", dtype=object)
    allow = np.ones(len(z), bool) if allow_entry is None else allow_entry.to_numpy(bool)
    for i, zt in enumerate(z.to_numpy(dtype=float)):
        evt = ""
        if pos != 0:
            held += 1
        if np.isfinite(zt):
            if pos == 0:
                if blocked and abs(zt) < entry:
                    blocked = False
                if not blocked and allow[i]:
                    if zt <= -entry:
                        pos, held, evt = 1, 0, "enter_long"
                    elif zt >= entry:
                        pos, held, evt = -1, 0, "enter_short"
            elif stop is not None and pos * zt <= -stop:
                pos, evt, blocked = 0, "stop", True
            elif pos * zt >= -exit:
                pos, evt = 0, "exit"
            elif max_hold is not None and held >= max_hold:
                pos, evt, blocked = 0, "max_hold", True
        elif pos != 0 and max_hold is not None and held >= max_hold:
            pos, evt, blocked = 0, "max_hold", True
        out_pos[i], out_evt[i] = pos, evt
    return pd.DataFrame({"position": out_pos, "event": out_evt}, index=z.index)
