"""
Lab-to-Industry Scaling for LFP Battery Recycling Analysis
===========================================================

PROBLEM:
  You have lab-scale recycling data (e.g., 5 kg/day throughput) and want to 
  project it to industrial scale (e.g., 10,000 t/yr). How do you translate 
  per-kg chemical/energy consumption into a full production facility?

SOLUTION:
  This module shows:
  1. How to extract per-kg metrics from lab work
  2. How to feed them into the EverBatt cost model
  3. How to account for Economy of Scale (labor costs scale by throughput^0.6)
  4. How to scale CapEx non-linearly (typical exponent: 0.6-0.8)
  5. Sensitivity analysis across production scales

KEY CONCEPTS:
  - Variable Costs (chemicals, energy): scale linearly with throughput
  - Fixed Costs (labor, depreciation): scale by power law (0.6-0.8 exponent)
  - CapEx: typically scales at 0.6-0.8 (not linearly)
  - Economy of Scale: doubling throughput doesn't double costs

USAGE:
  1. Fill in LAB_DATA with your experimental measurements
  2. Run: python scale_lab_to_industry.py
  3. Check output CSV: scaling_results.csv
  4. Modify scale factors and re-run if needed

REFERENCES:
  - EverBatt 2019 Documentation (ANL-19/16), Tables 10-15
  - Xu et al. (Joule 2020) — cost model validation
  - Chemical plant scaling: typical exponent 0.6-0.8 (Alibaba rule)
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Import the main analysis module
import lfp_analysis_verified as lfp

# ============================================================
# PART 1: DEFINE YOUR LAB-SCALE DATA
# ============================================================

LAB_DATA = {
    'method': 'Direct',  # Which recycling method: 'Pyro', 'Hydro', or 'Direct'
    
    'lab_scale': {
        'throughput_kg_per_day': 5,      # Your lab processes 5 kg/day
        'operating_days_per_year': 250,  # Lab operation: ~250 days/year
        # Lab scale: 5 kg/day * 250 = 1,250 kg/yr = 1.25 t/yr
    },
    
    'chemical_consumption_per_kg': {
        # Measure these in your lab! (kg chemical / kg battery input)
        'Lithium Carbonate': 0.004,      # Slightly different from default 0.003
        'Carbon Dioxide': 0.12,          # Slightly more CO2 needed in lab (less efficient)
    },
    
    'energy_consumption_per_kg': {
        # Measure these with energy meters in lab!
        'Natural gas (MJ)': 2.5,         # Lab setup may be less efficient
        'Electricity (kWh)': 1.1,        # kWh per kg
    },
    
    'recovery_rates': {
        # These are what you actually achieve in lab experiments
        'LFP cathode': 0.92,             # 92% cathode recovery (vs 90% EverBatt baseline)
        'Graphite': 0.88,                # 88% (vs 90%)
        'Binder (PVDF)': 0.88,           # (vs 90%)
        'Carbon black': 0.88,            # (vs 90%)
        'Copper': 0.92,                  # (vs 90%)
        'Aluminum': 0.92,                # (vs 90%)
        'Steel': 0.92,                   # (vs 90%)
        'Electrolyte (LiPF6 + solvents)': 0.55,  # (vs 50%)
        'Plastics': 0.55,                # (vs 50%)
        'Li as Li2CO3': 0.0,             # Direct recycling: Li stays in cathode
    },
    
    'capex_baseline': 12e6,              # Your estimated CapEx for 10,000 t/yr plant
    'capex_scale_factor': 0.7,           # Typical for chemical/recycling plants (0.6-0.8)
    'capex_reference_capacity': 10000,   # 10,000 t/yr reference capacity
}

# ============================================================
# PART 2: UPDATE MODEL PARAMETERS WITH LAB DATA
# ============================================================

def update_model_with_lab_data(lab_data):
    """
    Modify lfp_analysis_verified.py parameters to use your lab measurements.
    
    Args:
        lab_data (dict): Lab measurements from above
    
    Returns:
        None (modifies global lfp module parameters)
    """
    method = lab_data['method']
    
    # Update chemical consumption
    if 'chemical_consumption_per_kg' in lab_data:
        for chem, qty in lab_data['chemical_consumption_per_kg'].items():
            lfp.CHEMICALS_PER_KG[method][chem] = qty
    
    # Update energy consumption
    if 'energy_consumption_per_kg' in lab_data:
        for energy_type, qty in lab_data['energy_consumption_per_kg'].items():
            lfp.ENERGY_PER_KG[method][energy_type] = qty
    
    # Update recovery rates
    if 'recovery_rates' in lab_data:
        for material, rate in lab_data['recovery_rates'].items():
            if material in lfp.RECOVERY[method]:
                lfp.RECOVERY[method][material] = rate
    
    print(f"✓ Model parameters updated with {method} lab data")
    print(f"  - Lab scale: {lab_data['lab_scale']['throughput_kg_per_day']} kg/day")
    print(f"  - Annual equivalent: {lab_data['lab_scale']['throughput_kg_per_day'] * lab_data['lab_scale']['operating_days_per_year'] / 1000:.1f} t/yr")


# ============================================================
# PART 3: CAPEX SCALING FUNCTION
# ============================================================

def scale_capex(method, throughput, lab_data):
    """
    Scale capital cost from reference capacity to target throughput.
    
    Uses: CapEx(T) = CapEx_base * (T / T_base) ^ scale_factor
    
    Typical values:
      - scale_factor = 0.6: "six-tenths rule" for simple equipment
      - scale_factor = 0.7: chemical/recycling plants (more complex)
      - scale_factor = 0.8: large, complex facilities
    
    Args:
        method (str): 'Pyro', 'Hydro', or 'Direct'
        throughput (float): Target capacity in tonnes/year
        lab_data (dict): Must include capex_baseline, capex_reference_capacity, capex_scale_factor
    
    Returns:
        float: Scaled CapEx in USD
    
    Example:
        scale_capex('Direct', 1000, lab_data)  # CapEx for 1,000 t/yr plant
        scale_capex('Direct', 50000, lab_data) # CapEx for 50,000 t/yr plant
    """
    capex_base = lab_data['capex_baseline']
    ref_capacity = lab_data['capex_reference_capacity']
    scale_factor = lab_data['capex_scale_factor']
    
    capex_scaled = capex_base * (throughput / ref_capacity) ** scale_factor
    return capex_scaled


# ============================================================
# PART 4: MODIFY CAPEX IN ANALYSIS
# ============================================================

def analyze_method_with_scaled_capex(method, throughput, prices, battery_fee, lab_data):
    """
    Wrapper around lfp.analyze_method() that uses scaled CapEx instead of fixed.
    
    Args:
        method (str): 'Pyro', 'Hydro', or 'Direct'
        throughput (float): Annual capacity in tonnes
        prices (dict): Material prices (use lfp.PRICES_2019 or PRICES_2023)
        battery_fee (float): Gate fee in $/kg (negative = recycler gets paid)
        lab_data (dict): Lab configuration with CapEx scaling info
    
    Returns:
        dict: Results from lfp.analyze_method()
    """
    # Call original analysis
    result = lfp.analyze_method(method, throughput, prices, battery_fee)
    
    # Override CapEx with scaled version
    original_capex = lfp.CAPEX[method]
    scaled_capex = scale_capex(method, throughput, lab_data)
    lfp.CAPEX[method] = scaled_capex
    
    # Recalculate cost with scaled CapEx
    result = lfp.analyze_method(method, throughput, prices, battery_fee)
    
    # Restore original for other methods
    lfp.CAPEX[method] = original_capex
    
    return result


# ============================================================
# PART 5: SENSITIVITY ANALYSIS
# ============================================================

def run_scaling_analysis(lab_data, prices, battery_fee, throughput_range=None):
    """
    Run full economic analysis across multiple production scales.
    
    Compares:
      - Variable costs (chemicals, energy) — scale linearly
      - Fixed costs (labor) — scale by throughput^0.6
      - CapEx — scale by throughput^0.7 (or configured exponent)
    
    Args:
        lab_data (dict): Lab data with method and scaling params
        prices (dict): lfp.PRICES_2019 or PRICES_2023
        battery_fee (float): Gate fee in $/kg
        throughput_range (list): Capacities to test (default: [10, 50, 100, 500, 1000, 5000, 10000, 50000])
    
    Returns:
        pd.DataFrame: Results at each scale
    """
    if throughput_range is None:
        throughput_range = [10, 50, 100, 500, 1000, 5000, 10000, 50000]
    
    method = lab_data['method']
    results = []
    
    print(f"\n{'='*100}")
    print(f"SCALING ANALYSIS FOR {method.upper()} RECYCLING")
    print(f"{'='*100}")
    print(f"{'Throughput':<15} {'CapEx':<15} {'Cost/kg':<12} {'Revenue/kg':<12} {'Profit/kg':<12} {'GHG/kg':<12}")
    print(f"{'(t/yr)':<15} {'($M)':<15} {'($/kg)':<12} {'($/kg)':<12} {'($/kg)':<12} {'(kg CO2/kg)':<12}")
    print("-" * 100)
    
    for throughput in throughput_range:
        # Use original fixed CapEx from model (for baseline)
        result_baseline = lfp.analyze_method(method, throughput, prices, battery_fee)
        
        # Also compute with scaled CapEx for comparison
        capex_scaled = scale_capex(method, throughput, lab_data)
        
        # Per-kg metrics
        cost_per_kg = result_baseline['cost'] / (throughput * 1000)
        revenue_per_kg = result_baseline['revenue'] / (throughput * 1000)
        profit_per_kg = result_baseline['profit'] / (throughput * 1000)
        ghg_per_kg = result_baseline['net_ghg_kg'] / (throughput * 1000)
        
        # Compute breakeven: at what throughput does profit = 0?
        # (approximately, for linear interpolation later)
        
        results.append({
            'Throughput (t/yr)': throughput,
            'CapEx_baseline ($M)': lfp.CAPEX[method] / 1e6,
            'CapEx_scaled ($M)': capex_scaled / 1e6,
            'Cost ($M/yr)': result_baseline['cost'] / 1e6,
            'Revenue ($M/yr)': result_baseline['revenue'] / 1e6,
            'Profit ($M/yr)': result_baseline['profit'] / 1e6,
            'Cost ($/kg)': cost_per_kg,
            'Revenue ($/kg)': revenue_per_kg,
            'Profit ($/kg)': profit_per_kg,
            'GHG (kg CO2-eq/kg)': ghg_per_kg,
            'Labor cost ($M/yr)': result_baseline['cost_detail'].get('Labor', 0) / 1e6,
        })
        
        # Print one row
        print(f"{throughput:<15.0f} {capex_scaled/1e6:<15.1f} {cost_per_kg:<12.2f} "
              f"{revenue_per_kg:<12.2f} {profit_per_kg:<12.2f} {ghg_per_kg:<12.2f}")
    
    print("-" * 100)
    
    df = pd.DataFrame(results)
    return df


# ============================================================
# PART 6: VISUALIZATION
# ============================================================

def plot_scaling_analysis(df, method):
    """
    Create 4-panel comparison of scaling effects.
    
    Panels:
      1. Cost/Revenue/Profit per kg vs throughput
      2. Profit vs throughput (breakeven analysis)
      3. CapEx vs throughput (linear vs scaled)
      4. Labor cost as % of total cost
    """
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f'Scaling Analysis: {method} Recycling\n(Lab → Industrial Scale)', 
                 fontsize=14, fontweight='bold')
    
    # Panel 1: Per-kg economics
    ax = axes[0, 0]
    ax.plot(df['Throughput (t/yr)'], df['Revenue ($/kg)'], 'o-', label='Revenue', color='#2ECC71', linewidth=2)
    ax.plot(df['Throughput (t/yr)'], df['Cost ($/kg)'], 's-', label='Cost', color='#E74C3C', linewidth=2)
    ax.plot(df['Throughput (t/yr)'], df['Profit ($/kg)'], '^-', label='Profit', color='#3498DB', linewidth=2)
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('USD / kg feedstock')
    ax.set_title('Per-kg Economics vs Scale')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Panel 2: Profit vs throughput (breakeven)
    ax = axes[0, 1]
    colors = ['#E74C3C' if p < 0 else '#2ECC71' for p in df['Profit ($/kg)']]
    ax.bar(range(len(df)), df['Profit ($/kg)'], color=colors, edgecolor='black', linewidth=1.5)
    ax.axhline(y=0, color='black', linewidth=2)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels([f"{int(t)}" for t in df['Throughput (t/yr)']], rotation=45)
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('Profit ($/kg)')
    ax.set_title('Breakeven Analysis: Find Minimum Viable Scale')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Panel 3: CapEx comparison
    ax = axes[1, 0]
    ax.plot(df['Throughput (t/yr)'], df['CapEx_baseline ($M)'], 'o-', 
            label='Fixed CapEx (baseline model)', color='#95A5A6', linewidth=2, linestyle='--')
    ax.plot(df['Throughput (t/yr)'], df['CapEx_scaled ($M)'], 's-', 
            label=f"Scaled CapEx (exponent={LAB_DATA['capex_scale_factor']})", color='#E67E22', linewidth=2)
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('CapEx (Million USD)')
    ax.set_title('Capital Cost: Baseline vs Realistic Scaling')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Panel 4: Labor cost as % of total
    ax = axes[1, 1]
    labor_pct = (df['Labor cost ($M/yr)'] / df['Cost ($M/yr)']) * 100
    ax.plot(df['Throughput (t/yr)'], labor_pct, 'D-', color='#9B59B6', linewidth=2, markersize=8)
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('Labor as % of Total Cost')
    ax.set_title('Economy of Scale: Labor Cost Contribution')
    ax.set_xscale('log')
    ax.grid(True, alpha=0.3)
    ax.fill_between(df['Throughput (t/yr)'], 0, labor_pct, alpha=0.2, color='#9B59B6')
    
    plt.tight_layout()
    plt.savefig('scaling_analysis.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Chart saved: scaling_analysis.png")
    plt.close()


# ============================================================
# PART 7: MAIN EXECUTION
# ============================================================

def main():
    print("\n" + "="*100)
    print("  LAB-TO-INDUSTRY SCALING ANALYSIS FOR LFP BATTERY RECYCLING")
    print("="*100)
    
    # Step 1: Update model with lab data
    print("\n[1/4] Updating model with lab data...")
    update_model_with_lab_data(LAB_DATA)
    
    # Step 2: Show lab scale
    lab_scale_annual = (LAB_DATA['lab_scale']['throughput_kg_per_day'] * 
                        LAB_DATA['lab_scale']['operating_days_per_year'] / 1000)
    print(f"\n[2/4] Lab-scale production:")
    print(f"      Throughput: {LAB_DATA['lab_scale']['throughput_kg_per_day']} kg/day")
    print(f"      Annual (250 days): {lab_scale_annual:.2f} t/yr")
    print(f"      Scaling factor to 10,000 t/yr: {10000/lab_scale_annual:.0f}x")
    
    # Step 3: Run sensitivity analysis
    print(f"\n[3/4] Running scaling sensitivity analysis...")
    df_results = run_scaling_analysis(LAB_DATA, lfp.PRICES_2019, -2.0)
    
    # Step 4: Visualize
    print(f"\n[4/4] Generating charts...")
    plot_scaling_analysis(df_results, LAB_DATA['method'])
    
    # Save results to CSV
    csv_path = 'scaling_results.csv'
    df_results.to_csv(csv_path, index=False)
    print(f"✓ Results exported: {csv_path}")
    
    # Find breakeven
    print(f"\n{'='*100}")
    print("  KEY INSIGHTS")
    print(f"{'='*100}")
    
    breakeven_rows = df_results[df_results['Profit ($/kg)'] > 0]
    if len(breakeven_rows) > 0:
        breakeven = breakeven_rows.iloc[0]
        print(f"\n✓ Breakeven capacity: ~{breakeven['Throughput (t/yr)']:.0f} t/yr")
        print(f"  At this scale:")
        print(f"    - Cost: ${breakeven['Cost ($/kg)']:.2f}/kg")
        print(f"    - Revenue: ${breakeven['Revenue ($/kg)']:.2f}/kg")
        print(f"    - Profit: ${breakeven['Profit ($/kg)']:.2f}/kg")
        print(f"    - CapEx: ${breakeven['CapEx_scaled ($M)']:.1f}M")
    else:
        print(f"\n⚠ No breakeven found in tested range. Model is unprofitable even at 50,000 t/yr.")
    
    # Show scaling effect on labor costs
    print(f"\n✓ Economy of Scale (labor):")
    lab_10t = df_results[df_results['Throughput (t/yr)'] == 10].iloc[0]
    lab_10kt = df_results[df_results['Throughput (t/yr)'] == 10000].iloc[0]
    labor_ratio = lab_10kt['Labor cost ($M/yr)'] / lab_10t['Labor cost ($M/yr)']
    print(f"  10 t/yr vs 10,000 t/yr: labor scales by {labor_ratio:.1f}x (not 1000x)")
    print(f"  This is because labor scales by throughput^0.6, not throughput^1")
    print(f"  Cost per kg improvement: {lab_10t['Cost ($/kg)']:.2f} → {lab_10kt['Cost ($/kg)']:.2f} (${lab_10t['Cost ($/kg)'] - lab_10kt['Cost ($/kg)']:.2f}/kg saved)")
    
    print(f"\n{'='*100}\n")
    
    return df_results


# ============================================================
# EXAMPLE: HOW TO MODIFY LAB DATA FOR YOUR OWN WORK
# ============================================================

"""
EXAMPLE 1: You have different recovery rates
==============================================

LAB_DATA['recovery_rates']['LFP cathode'] = 0.95  # Your lab gets 95% (better than 90%)

EXAMPLE 2: Your lab process is less efficient (more chemicals)
==============================================================

LAB_DATA['chemical_consumption_per_kg']['Lithium Carbonate'] = 0.006  # Uses more

EXAMPLE 3: Your facility is estimated to be smaller/cheaper than baseline
===========================================================================

LAB_DATA['capex_baseline'] = 8e6  # Only $8M for 10,000 t/yr (vs $12M default)
LAB_DATA['capex_scale_factor'] = 0.65  # More economies of scale

EXAMPLE 4: You want to compare two methods at different scales
===============================================================

1. Run with method='Direct':
   python scale_lab_to_industry.py
   # Check scaling_results.csv

2. Change method to 'Hydro' and re-run:
   LAB_DATA['method'] = 'Hydro'
   python scale_lab_to_industry.py
   
3. Compare CSV files side-by-side

EXAMPLE 5: Test sensitivity to material prices
===============================================

from scale_lab_to_industry import run_scaling_analysis
import lfp_analysis_verified as lfp

# Run with 2023 prices
df_2023 = run_scaling_analysis(LAB_DATA, lfp.PRICES_2023, -2.0)
df_2023.to_csv('scaling_results_2023.csv')

# Compare: which scaling scenario is more sensitive to Li prices?
"""

if __name__ == '__main__':
    df = main()
