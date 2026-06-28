# EverBatt LFP Battery Recycling Analysis

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python implementation of **Techno-Economic Analysis (TEA)** and **Life Cycle Assessment (LCA)** for LFP (LiFePO₄) battery recycling, based on Argonne National Lab's [EverBatt model](https://publications.anl.gov/anlpubs/2019/07/153050.pdf) (ANL-19/16).

Compare three recycling methods — **Pyrometallurgical**, **Hydrometallurgical**, and **Direct Recycling** — on cost, revenue, profit, and GHG emissions.

## Quick Start

```bash
pip install numpy pandas matplotlib openpyxl scipy seaborn
python lfp_analysis_verified.py
```

Output: terminal tables + `LFP_Recycling_Verified.png` (6-panel comparison chart).

## Results (10,000 tonnes/year LFP batteries)

| Method | Cost ($/kg) | Revenue ($/kg) | Profit ($/kg) | Net GHG |
|--------|:-----------:|:--------------:|:-------------:|:-------:|
| Pyrometallurgical | ~2.3 | ~1.4 | **−0.9** (loss) | Highest |
| Hydrometallurgical | ~2.2 | ~2.4 | **+0.2** (marginal) | Medium |
| Direct Recycling | ~1.7 | ~3.4 | **+1.7** (profit) | Lowest |

**Conclusion: Direct recycling > Hydrometallurgical > Pyrometallurgical** for LFP — consistent with Xu et al. (Joule 2020) and Ji et al. (Nat. Commun. 2024).

## Key Parameters

All parameters are at the top of `lfp_analysis_verified.py`:

- `THROUGHPUT_TONNES` — plant scale
- `P` — switch between `PRICES_2019` / `PRICES_2023`
- `BATTERY_FEE` — gate fee paid by battery manufacturers
- `ELEC_PRICE`, `NG_PRICE` — utility costs
- `RECOVERY` — material recovery rates per method

## Files

| File | Description |
|------|-------------|
| `lfp_analysis_verified.py` | **Main analysis** — verified against EverBatt documentation |
| `lfp_analysis.py` | Initial version (simpler cost model) |
| `read_everbatt.py` | Tool to fix XML issues and read the EverBatt Excel model |
| `新手完全指南.md` | Beginner's guide (Chinese) |
| `CLAUDE.md` | Guidance for Claude Code |

## Data Sources

- **EverBatt 2019 Documentation** (ANL-19/16) — Argonne National Laboratory
- Material prices and cost model from EverBatt Tables 10–15
- Benchmarked against Xu et al. (Joule, 2020) and Ji et al. (Nat. Commun., 2024)

## License

MIT — see [LICENSE](LICENSE) file.
