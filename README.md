# makefun-btc-race-17nov-r4

[![make.fun](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/Mansyur0523/makefun-btc-race-17nov-r4/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/Mansyur0523/makefun-btc-race-17nov-r4/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

Dip-recovery trading bot for the make.fun BTC race
(`btc-race-24h-20261117-0603`): it trades Coinbase Wrapped BTC (cbBTC)
against USDC, one minute bar at a time, in the `agent-fun/bars-replay/v1`
replay.

## Strategy

BTC rarely falls in a straight line for an hour and then keeps falling. The
bot buys when the close has dropped hard over the last hour but the last
quarter-hour has already turned back up — the slide is stabilising — and
lets the bounce pay for the round trip.

- **Entry:** close ≥ 60 bps below the close 60 bars ago **and** ≥ 10 bps
  above the close 15 bars ago. Size: 85% of cash on hand.
- **Exits (checked on every close while holding):** take profit +120 bps,
  stop loss −150 bps, trailing stop 90 bps under the post-entry peak,
  time stop after 300 bars, then a 60-bar cooldown before the next entry.
- Long only, one position at a time, fully deterministic (integer math,
  no clock, no randomness).

## Local backtest

Replayed on the kit dev window (1,440 one-minute bars) with the
competition's fill model (4 bps fee, 2 bps slippage, constant-product
impact against the bar's open depth):

- Net PnL: **+$16.27** on a $1,000 start
- Trades: 6
- Max drawdown: 0.94%
- Two runs produce byte-identical replies (deterministic)

## Run

The entrypoint is `main.py` at the repository root (Python 3.13, standard
library only; the protocol shim is vendored under `vendor/`):

```sh
python3 -P -s main.py
```

It speaks `agent-fun/bars-replay/v1` on stdin/stdout: one `hello`, one
batch per minute, one reply per batch.
