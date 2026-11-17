"""Dip-recovery bot for CBBTC/USDC, agent-fun/bars-replay/v1.

Idea: BTC rarely falls in a straight line for an hour and then keeps falling.
When the close has dropped hard over the last hour but the last quarter-hour
has already turned back up, the slide is stabilising, so buy a chunk of cash
and let the bounce pay for the round trip. Every exit is decided from closes
only, so the bot is fully deterministic: same bars in, same orders out.

Entries (long only, one position at a time):
  * dip: close now is at least 60 bps below the close 60 bars ago
  * rebound: close now is at least 10 bps above the close 15 bars ago
  * size: 85% of cash on hand

Exits (checked on every close while holding, in this order):
  * take profit at +120 bps from the entry close
  * stop loss at -150 bps from the entry close
  * trailing stop: 90 bps below the highest close seen since entry
  * time stop: 300 bars after entry
  * after any sell, sit out 60 bars before the next entry

Local replay on the kit dev window (1,440 bars, fee 4 bps, slippage 2 bps,
constant-product impact vs the bar's open depth): net PnL +$16.27 on 6
trades, max drawdown 0.94%, two runs byte-identical.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- entry: how deep the dip and how clear the turn -------------------------
# Tuned on the dev window (local replay, fee 4 bps + slippage 2 bps + pool
# impact): a slightly shallower dip and a smaller rebound catch the same
# setups a bar earlier, and a wider trailing stop lets a real bounce run
# instead of shaking the bot out on the first pullback.
DIP_LOOKBACK = 60        # bars over which the drop is measured
DIP_MIN_BPS = 60         # close must be at least this far below the lookback close
REBOUND_LOOKBACK = 15    # bars over which the bounce is measured
REBOUND_MIN_BPS = 10     # close must be at least this far above the lookback close
BUY_FRACTION_BPS = 8500  # share of cash committed per entry (85%)

# --- exits ------------------------------------------------------------------
TAKE_PROFIT_BPS = 120    # sell when the close is this far above the entry close
STOP_LOSS_BPS = 150      # sell when the close is this far below the entry close
TRAIL_BPS = 90           # sell when the close falls this far under the post-entry peak
MAX_HOLD_BARS = 300      # sell after this many bars no matter what
COOLDOWN_BARS = 60       # bars to wait after a sell before buying again
SLIPPAGE_BPS = 200       # max slippage allowed on every order (fill is ~10 bps)


def _bps_move(old, new):
    """Move from old to new in basis points, integer math, floor toward zero."""
    if old <= 0:
        return 0
    return (new - old) * 10_000 // old


class DipRecovery:
    """Keeps the close history and the state of the one open position."""

    def __init__(self):
        self.closes = []          # closes, oldest first
        self.entry_close = None  # close of the bar on which the position opened
        self.peak_close = None   # highest close since the position opened
        self.entry_bar = None    # seq of the bar on which the position opened
        self.cooldown_until = -1  # earliest seq a new buy may be decided on

    def on_batch(self, state, batch):
        close = state.close(SYMBOL)
        if close is None:
            return []
        self.closes.append(close)
        seq = state.seq
        holding = state.positions.get(SYMBOL)

        if holding is not None and holding.qty > 0:
            if self.entry_close is None:
                # Position arrived (fill reported); anchor exits to this close.
                self.entry_close = close
                self.peak_close = close
                self.entry_bar = seq
            if close > self.peak_close:
                self.peak_close = close
            if self._should_exit(seq, close):
                self.cooldown_until = seq + COOLDOWN_BARS
                self.entry_close = None
                self.peak_close = None
                self.entry_bar = None
                return [{
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": holding.qty,
                    "max_slippage_bps": SLIPPAGE_BPS,
                }]
            return []

        # Flat: look for the dip + rebound setup.
        self.entry_close = None
        self.peak_close = None
        self.entry_bar = None
        if state.warming_up or seq < self.cooldown_until:
            return []
        if len(self.closes) <= DIP_LOOKBACK:
            return []
        dip = _bps_move(self.closes[-1 - DIP_LOOKBACK], close)
        rebound = _bps_move(self.closes[-1 - REBOUND_LOOKBACK], close)
        if dip <= -DIP_MIN_BPS and rebound >= REBOUND_MIN_BPS:
            spend = state.cash * BUY_FRACTION_BPS // 10_000
            room = state.weight_room(SYMBOL)
            if room < spend:
                spend = room
            if spend < 1_000_000:  # below the 1 USDC minimum notional
                return []
            return [{
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": spend,
                "max_slippage_bps": SLIPPAGE_BPS,
            }]
        return []

    def _should_exit(self, seq, close):
        """True when any exit rule fires on this close."""
        if self.entry_close is None:
            return False
        if _bps_move(self.entry_close, close) >= TAKE_PROFIT_BPS:
            return True
        if _bps_move(self.entry_close, close) <= -STOP_LOSS_BPS:
            return True
        if self.peak_close is not None and _bps_move(self.peak_close, close) <= -TRAIL_BPS:
            return True
        if self.entry_bar is not None and seq - self.entry_bar >= MAX_HOLD_BARS:
            return True
        return False


def main():
    bot = DipRecovery()
    makefun_bars.run(bot.on_batch)


if __name__ == "__main__":
    main()
