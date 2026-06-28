# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python analysis of **LFP (LiFePO4) battery recycling economics and GHG emissions**, comparing three methods: Pyrometallurgical, Hydrometallurgical, and Direct Recycling. Data and methodology are based on Argonne National Lab's **EverBatt** model (ANL-19/16), an Excel-based lifecycle analysis tool.

## Key Files

| File | Role |
|---|---|
| `lfp_analysis_verified.py` | **Primary analysis script** — verified against EverBatt documentation. Runs all three methods, prints tables, generates `LFP_Recycling_Verified.png` |
| `lfp_analysis.py` | Initial/exploratory version of the same analysis (simpler model, less verified) |
| `read_everbatt.py` | Tool to fix XML compatibility issues in `EverBatt 2023.xlsm` and read all 17 sheets via openpyxl |
| `新手完全指南.md` | Chinese beginner's guide explaining the methodology, data sources, and how to run/verify the analysis |
| `EverBatt 2023.xlsm` | The original Argonne model (macro-enabled Excel, ~2MB) |
| `EverBatt 2019 Documentation.pdf` | 88-page official methodology document (ANL-19/16) |
| `EverBatt 2023 User's Manual.pdf` | User manual for the 2023 Excel model |

## How to Run

```bash
# Main analysis
python lfp_analysis_verified.py

# Read the Excel model (fixes XML, then reads all sheets)
python read_everbatt.py

# Dependencies
pip install numpy pandas matplotlib openpyxl scipy seaborn
```

## EverBatt xlsm Reading

The `EverBatt 2023.xlsm` file cannot be opened directly by openpyxl due to XML values that exceed valid ranges (font family > 14, theme > 10, indexed color > 65). `read_everbatt.py` solves this:

1. Unzips the xlsm (it's a ZIP archive)
2. Walks all `.xml`/`.rels` files, fixing out-of-range attribute values via ElementTree
3. Re-zips to a temp file
4. Opens the fixed file with `openpyxl.load_workbook(data_only=True)`

The model has 17 sheets; the key ones for analysis are `CM Rec Par.` (cathode material recovery), `Materials` (price database), `Output`, and `Report`.

## Analysis Methodology

Both analysis scripts follow the same structure:

1. **Parameters**: Battery composition (9-component wt%), material prices, chemical costs/consumption, energy consumption, recovery rates per method, CapEx, GHG factors — all from EverBatt Tables 10-15
2. **Revenue**: Recovered material mass × market price, plus battery gate fee (LFP recyclers get paid ~$2/kg for taking waste batteries)
3. **Cost**: Full chemical plant cost model — chemicals + energy + labor + depreciation + maintenance + fixed charges + plant overhead + GSA + waste disposal
4. **GHG**: Energy emissions + chemical production emissions + combustion emissions − avoided virgin material production credits
5. **Output**: Per-method revenue/cost/profit/GHG tables + 6-panel comparison chart

Key difference between the two scripts: `lfp_analysis_verified.py` uses the full EverBatt cost model (CapEx depreciation, labor scaling by throughput^0.6, fixed charges, overhead, GSA) and recovery rates from Table 12, while `lfp_analysis.py` uses a simplified opex-only model with estimated rates.

## Parameter Tuning

All key parameters are at the top of `lfp_analysis_verified.py`:
- `THROUGHPUT_TONNES`: Plant scale (default 10000 tonnes/yr)
- `P`: Switch between `PRICES_2019` and `PRICES_2023` for material prices
- `BATTERY_FEE`: Gate fee — critical swing factor for LFP profitability (2019: -$2/kg, 2023: ~$0/kg)
- `ELEC_PRICE`, `NG_PRICE`: Utility costs
- Recovery rates in `RECOVERY` dict, chemical consumption in `CHEMICALS_PER_KG`

## Key Findings (consistent with literature)

- **Direct Recycling > Hydrometallurgical > Pyrometallurgical** for LFP economics
- Pyro loses money on LFP (no Co/Ni to recover, Li lost to slag)
- Hydro viability depends on Li2CO3 market price
- Direct recycling is profitable because LFP cathode powder is recovered intact (~$10/kg value)
