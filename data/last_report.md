# UAE Pick 3 Any-6 Tracker
_Generated: 30 Oct 2026, 2:23 AM Dubai (mode: reconcile)_
_Last predict run: 29 Oct 2026, 11:52 PM Dubai_
_Last reconcile run: 30 Oct 2026, 2:23 AM Dubai_

## History
- Draws on file: 512 (2025-06-04 to 2026-10-29)
- Last result: 261029: 3-6-4 (ABC)

## Reconciliation
- Record: 1 wins / 117 days resolved

## Model Selection
- UniformBaseline: log-loss=4.7875, top1_hit_rate=1.6484%, n_scored=364
- PerPositionFrequency: log-loss=4.8052, top1_hit_rate=2.1978%, n_scored=364
- MarkovOrder1: log-loss=4.8538, top1_hit_rate=0.5495%, n_scored=364
- MarkovOrder2: log-loss=4.8155, top1_hit_rate=1.6484%, n_scored=364
- MLClassifier: log-loss=6.1470, top1_hit_rate=0.5495%, n_scored=364
- **Selected:** PerPositionFrequency -- Forced override: predicting with PerPositionFrequency -- honest walk-forward selection would have picked UniformBaseline (no candidate beat chance by more than 1 standard error -- defaulting to UniformBaseline) (reconcile run -- results updated this run, no new pick generated)
- Log-loss computed over distinct-digit (ABC) draws only (~72% of days) -- non-distinct draws fall outside the Any-6 outcome space and always result in a loss for this play type.

## Tonight's Pick
- Play type: **Any 6** | Target draw: **261030** (2026-10-30) | Stake: AED 5
- Pick: **n/a -- run predict mode first**

## P&L Ledger
- Days played: 118 | Staked: AED 590 | Won: AED 425
- Net P&L: AED -165 | Actual RTP: 72.03% vs theoretical 51.00%
- Expected wins: 0.702 | Actual wins: 1

## Fairness Audit (not a predictor)
- d1: p=0.5263
- d2: p=0.5619
- d3: p=0.4577
- pattern split: p=0.2076

> Pick 3 is i.i.d. uniform. This pick does not beat the odds. Expected return ≈ 51% (≈49% expected loss). For entertainment; play at most AED 5/day.
