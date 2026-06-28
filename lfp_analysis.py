"""
LFP Battery Recycling Economic & GHG Analysis
Based on Argonne National Lab EverBatt 2023 methodology
Comparing three recycling methods: Pyrometallurgical, Hydrometallurgical, Direct Recycling
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
import seaborn as sns

# ============================================================
# 1. CONFIGURATION & PARAMETERS (from EverBatt 2023 defaults)
# ============================================================

# --- Plant scale ---
THROUGHPUT_TONNES_PER_YEAR = 10000  # tonnes of batteries recycled per year

# --- LFP Battery Pack Composition (wt%) ---
# From EverBatt Materials database
LFP_COMPOSITION = {
    'LFP cathode': 0.28,
    'Graphite': 0.16,
    'Binder (PVDF)': 0.03,
    'Carbon black': 0.03,
    'Copper': 0.15,
    'Aluminum': 0.20,
    'Steel': 0.08,
    'Electrolyte (LiPF6 + solvents)': 0.05,
    'Plastics': 0.02,
}

# --- Material prices from EverBatt 2023 ($/kg) ---
MATERIAL_PRICES = {
    'Aluminum': 1.12,
    'Copper': 7.11,
    'Steel': 0.33,
    'Plastics': 0.20,
    'Graphite': 0.20,
    'Electrolyte organics': 0.15,
    'LFP cathode': 10.00,
    'Lithium carbonate': 17.14,
    'Lithium hydroxide': 34.89,
    'Phosphoric acid': 1.14,
    'Iron sulfate': 0.65,
    'Soda ash': 0.14,
    'Sulfuric acid': 0.08,
    'Hydrogen peroxide': 1.46,
    'Sodium hydroxide': 0.45,
}

# --- Chemical costs from EverBatt 2023 ($/kg) ---
CHEMICAL_COSTS = {
    'Sulfuric acid': 0.083,
    'Hydrogen peroxide': 1.459,
    'Sodium hydroxide': 0.45,
    'Soda ash': 0.143,
    'Phosphoric acid': 1.142,
    'Hydrochloric acid': 0.566,
    'Lime': 0.132,
    'Coke': 0.307,
    'Iron sulfate': 0.646,
}

# --- Utility costs from EverBatt 2023 ---
UTILITY_COSTS = {
    'Electricity': 0.07,     # $/kWh
    'Natural gas': 4.50,     # $/MMBTU
    'Water': 0.005,          # $/gallon
}

# --- Waste disposal costs ---
LANDFILL_TIP_FEE = 50.0  # $/tonne

# ============================================================
# 2. RECYCLING METHOD PARAMETERS
# ============================================================

# Recovery rates for each method (fraction of material recovered)
RECOVERY_RATES = {
    'Pyro': {
        'LFP cathode': 0.00,      # LFP cathode structure destroyed in smelting
        'Graphite': 0.00,          # Burned as fuel
        'Binder (PVDF)': 0.00,     # Burned
        'Carbon black': 0.00,      # Burned
        'Copper': 0.90,            # Recovered from alloy
        'Aluminum': 0.00,          # Oxidized to slag
        'Steel': 0.90,             # Recovered
        'Electrolyte (LiPF6 + solvents)': 0.00,  # Burned
        'Plastics': 0.00,          # Burned
    },
    'Hydro': {
        'LFP cathode': 0.00,      # Decomposed, but Li can be recovered separately
        'Graphite': 0.85,          # Recovered by flotation/filtration
        'Binder (PVDF)': 0.00,
        'Carbon black': 0.80,
        'Copper': 0.95,
        'Aluminum': 0.90,
        'Steel': 0.95,
        'Electrolyte (LiPF6 + solvents)': 0.70,  # Solvents condensed, LiPF6 decomposed
        'Plastics': 0.80,
    },
    'Direct': {
        'LFP cathode': 0.90,      # Directly recovered and regenerated
        'Graphite': 0.90,
        'Binder (PVDF)': 0.00,
        'Carbon black': 0.85,
        'Copper': 0.95,
        'Aluminum': 0.92,
        'Steel': 0.95,
        'Electrolyte (LiPF6 + solvents)': 0.75,
        'Plastics': 0.85,
    },
}

# Additional lithium recovery as Li2CO3 (key for LFP economics)
# Pyro: Li goes to slag, minimal recovery
# Hydro: Li can be precipitated as Li2CO3
# Direct: LFP cathode recovered whole, no separate Li recovery
LI_RECOVERY_AS_CARBONATE = {
    'Pyro': 0.00,    # Li lost to slag
    'Hydro': 0.75,   # Li precipitated as Li2CO3
    'Direct': 0.00,  # Li stays in LFP cathode structure
}

# LFP cathode contains ~4.4 wt% Lithium
LI_IN_LFP = 0.044
# Li2CO3 is ~18.8% Li by mass
LI_IN_LI2CO3 = 0.188

# --- Process costs per kg feedstock ($/kg) ---
# These are representative values from EverBatt / published Argonne studies
PROCESS_COSTS = {
    'Pyro': {
        'Feedstock logistics': 0.25,
        'Disassembly & pretreatment': 0.15,
        'Smelting operation': 0.55,
        'Slag treatment': 0.10,
        'Gas treatment': 0.08,
        'Wastewater treatment': 0.02,
        'Landfill disposal': 0.05,
    },
    'Hydro': {
        'Feedstock logistics': 0.25,
        'Disassembly & pretreatment': 0.15,
        'Leaching (H2SO4 + H2O2)': 0.35,
        'Solvent extraction': 0.20,
        'Precipitation / crystallization': 0.18,
        'Li2CO3 recovery': 0.15,
        'Wastewater treatment': 0.08,
        'Landfill disposal': 0.03,
    },
    'Direct': {
        'Feedstock logistics': 0.25,
        'Disassembly & pretreatment': 0.15,
        'Physical separation': 0.20,
        'Cathode regeneration': 0.30,
        'Electrolyte recovery': 0.08,
        'Wastewater treatment': 0.03,
        'Landfill disposal': 0.02,
    },
}

# --- Energy consumption per kg feedstock (MJ/kg) ---
ENERGY_CONSUMPTION = {
    'Pyro': {
        'Disassembly': 1.5,
        'Smelting furnace': 18.0,
        'Gas treatment': 2.5,
        'Other': 1.0,
    },
    'Hydro': {
        'Disassembly': 1.5,
        'Leaching & heating': 8.0,
        'Separation & extraction': 6.0,
        'Precipitation & drying': 5.0,
        'Other': 1.5,
    },
    'Direct': {
        'Disassembly': 1.5,
        'Physical separation': 4.0,
        'Cathode regeneration (calcination)': 8.0,
        'Electrolyte recovery': 2.0,
        'Other': 1.0,
    },
}

# --- GHG emission factors (g CO2-eq per MJ energy) ---
# US grid mix average
GHG_PER_MJ_ELECTRICITY = 115  # g CO2-eq/MJ
GHG_PER_MJ_NATURAL_GAS = 62   # g CO2-eq/MJ

# --- Chemical GHG footprints (kg CO2-eq per kg chemical) ---
CHEMICAL_GHG = {
    'Sulfuric acid': 0.15,
    'Hydrogen peroxide': 0.95,
    'Sodium hydroxide': 1.10,
    'Soda ash': 0.90,
    'Phosphoric acid': 0.85,
    'Hydrochloric acid': 0.80,
    'Lime': 0.75,
    'Coke': 3.20,
    'Iron sulfate': 0.30,
}

# --- Chemical consumption per kg feedstock (kg chemical / kg feedstock) ---
CHEMICAL_CONSUMPTION = {
    'Pyro': {
        'Coke': 0.08,
        'Lime': 0.15,
    },
    'Hydro': {
        'Sulfuric acid': 0.50,
        'Hydrogen peroxide': 0.15,
        'Sodium hydroxide': 0.20,
        'Soda ash': 0.10,
        'Phosphoric acid': 0.05,
    },
    'Direct': {
        'Sodium hydroxide': 0.02,
        'Phosphoric acid': 0.01,
    },
}

# --- Avoided virgin material production GHG credits (kg CO2-eq per kg material) ---
AVOIDED_VIRGIN_GHG = {
    'Aluminum': 11.5,
    'Copper': 5.5,
    'Steel': 1.8,
    'Plastics': 2.5,
    'Graphite': 4.0,
    'LFP cathode': 5.2,
    'Lithium carbonate': 8.5,
    'Electrolyte organics': 3.0,
}


# ============================================================
# 3. CALCULATION FUNCTIONS
# ============================================================

def calculate_material_mass(composition, throughput):
    """Calculate mass of each material in the feedstock (tonnes/yr)"""
    return {mat: frac * throughput for mat, frac in composition.items()}


def calculate_revenue(material_mass, method):
    """Calculate revenue from recovered materials ($/yr)"""
    revenue = 0
    revenue_breakdown = {}

    rates = RECOVERY_RATES[method]
    li_rate = LI_RECOVERY_AS_CARBONATE[method]

    for material, mass in material_mass.items():
        recovered = mass * rates[material]
        if material == 'LFP cathode' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['LFP cathode']
            revenue += val
            revenue_breakdown['LFP cathode'] = val
        elif material == 'Copper' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['Copper']
            revenue += val
            revenue_breakdown['Copper'] = val
        elif material == 'Aluminum' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['Aluminum']
            revenue += val
            revenue_breakdown['Aluminum'] = val
        elif material == 'Steel' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['Steel']
            revenue += val
            revenue_breakdown['Steel'] = val
        elif material == 'Graphite' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['Graphite']
            revenue += val
            revenue_breakdown['Graphite'] = val
        elif material == 'Electrolyte (LiPF6 + solvents)' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['Electrolyte organics']
            revenue += val
            revenue_breakdown['Electrolyte'] = val
        elif material == 'Plastics' and recovered > 0:
            val = recovered * 1000 * MATERIAL_PRICES['Plastics']
            revenue += val
            revenue_breakdown['Plastics'] = val

    # Lithium carbonate recovery (from Hydro leaching)
    if li_rate > 0:
        lfp_mass = material_mass['LFP cathode']
        li_mass = lfp_mass * LI_IN_LFP  # lithium content in LFP
        li2co3_mass = li_mass / LI_IN_LI2CO3 * li_rate  # Li2CO3 produced
        val = li2co3_mass * 1000 * MATERIAL_PRICES['Lithium carbonate']
        revenue += val
        revenue_breakdown['Lithium carbonate'] = val

    return revenue, revenue_breakdown


def calculate_cost(material_mass, method, throughput):
    """Calculate total recycling cost ($/yr)"""
    costs = PROCESS_COSTS[method]
    total_cost = 0
    cost_breakdown = {}

    for item, unit_cost in costs.items():
        annual_cost = unit_cost * throughput * 1000  # $/yr
        total_cost += annual_cost
        cost_breakdown[item] = annual_cost

    # Add chemical costs
    chem_consumption = CHEMICAL_CONSUMPTION[method]
    chem_total = 0
    for chem, qty_per_kg in chem_consumption.items():
        annual_chem_cost = qty_per_kg * throughput * 1000 * CHEMICAL_COSTS[chem]
        chem_total += annual_chem_cost
        cost_breakdown[f'Chemical: {chem}'] = annual_chem_cost
    total_cost += chem_total

    # Add energy costs
    energy = ENERGY_CONSUMPTION[method]
    energy_total = 0
    for process, mj_per_kg in energy.items():
        mj_total = mj_per_kg * throughput * 1000  # total MJ
        kwh_total = mj_total / 3.6  # MJ to kWh
        elec_cost = kwh_total * UTILITY_COSTS['Electricity']
        energy_total += elec_cost
    total_cost += energy_total
    cost_breakdown['Energy (electricity)'] = energy_total

    return total_cost, cost_breakdown


def calculate_ghg(material_mass, method, throughput):
    """Calculate net GHG emissions (kg CO2-eq/yr)"""
    total_ghg = 0
    ghg_breakdown = {}

    # 1. Energy-related GHG
    energy = ENERGY_CONSUMPTION[method]
    energy_ghg = 0
    for process, mj_per_kg in energy.items():
        mj_total = mj_per_kg * throughput * 1000
        ghg = mj_total * GHG_PER_MJ_ELECTRICITY / 1000  # kg CO2-eq
        energy_ghg += ghg
    total_ghg += energy_ghg
    ghg_breakdown['Energy consumption'] = energy_ghg

    # 2. Chemical-related GHG
    chem_consumption = CHEMICAL_CONSUMPTION[method]
    chem_ghg = 0
    for chem, qty_per_kg in chem_consumption.items():
        ghg = qty_per_kg * throughput * 1000 * CHEMICAL_GHG[chem]
        chem_ghg += ghg
    total_ghg += chem_ghg
    ghg_breakdown['Chemical production'] = chem_ghg

    # 3. Landfill GHG (methane from organic waste decomposition)
    landfill_mass = 0
    rates = RECOVERY_RATES[method]
    for material, mass in material_mass.items():
        landfill_mass += mass * (1 - rates[material])
    landfill_ghg = landfill_mass * 1000 * 0.5 * 0.25  # kg CO2-eq/kg waste (CH4 GWP=25, conservative)
    total_ghg += landfill_ghg
    ghg_breakdown['Landfill decomposition'] = landfill_ghg

    # 4. Avoided virgin material production (GHG credit)
    avoided_ghg = 0
    avoided_breakdown = {}
    rates = RECOVERY_RATES[method]
    li_rate = LI_RECOVERY_AS_CARBONATE[method]

    for material, mass in material_mass.items():
        recovered = mass * rates[material]
        if recovered > 0 and material in AVOIDED_VIRGIN_GHG:
            credit = recovered * 1000 * AVOIDED_VIRGIN_GHG[material]
            avoided_ghg += credit
            avoided_breakdown[material] = -credit

    if li_rate > 0:
        lfp_mass = material_mass['LFP cathode']
        li_mass = lfp_mass * LI_IN_LFP
        li2co3_mass = li_mass / LI_IN_LI2CO3 * li_rate
        credit = li2co3_mass * 1000 * AVOIDED_VIRGIN_GHG['Lithium carbonate']
        avoided_ghg += credit
        avoided_breakdown['Lithium carbonate'] = -credit

    ghg_breakdown['Avoided virgin (credit)'] = -avoided_ghg
    net_ghg = total_ghg - avoided_ghg

    return net_ghg, ghg_breakdown, avoided_breakdown


# ============================================================
# 4. RUN ANALYSIS
# ============================================================

material_mass = calculate_material_mass(LFP_COMPOSITION, THROUGHPUT_TONNES_PER_YEAR)

methods = ['Pyro', 'Hydro', 'Direct']
method_labels = ['Pyrometallurgical\n(Fire smelting)', 'Hydrometallurgical\n(Chemical leaching)', 'Direct Recycling\n(Physical recovery)']

results = {}
for method in methods:
    revenue, rev_detail = calculate_revenue(material_mass, method)
    cost, cost_detail = calculate_cost(material_mass, method, THROUGHPUT_TONNES_PER_YEAR)
    profit = revenue - cost
    net_ghg, ghg_detail, avoided_detail = calculate_ghg(material_mass, method, THROUGHPUT_TONNES_PER_YEAR)

    results[method] = {
        'revenue': revenue,
        'cost': cost,
        'profit': profit,
        'net_ghg_kg': net_ghg,
        'net_ghg_tonne': net_ghg / 1000,
        'revenue_detail': rev_detail,
        'cost_detail': cost_detail,
        'ghg_detail': ghg_detail,
        'avoided_detail': avoided_detail,
    }


# ============================================================
# 5. DISPLAY RESULTS
# ============================================================

print("=" * 80)
print("  LFP BATTERY RECYCLING: ECONOMIC & ENVIRONMENTAL ANALYSIS")
print(f"  Throughput: {THROUGHPUT_TONNES_PER_YEAR:,} tonnes/year")
print(f"  Based on Argonne National Lab EverBatt 2023 methodology")
print("=" * 80)

print("\n--- LFP Battery Pack Composition ---")
for mat, frac in LFP_COMPOSITION.items():
    mass = material_mass[mat]
    print(f"  {mat:<35s}: {frac*100:5.1f}%  ({mass:6.0f} tonnes/yr)")

print("\n\n--- ECONOMIC ANALYSIS ---")
print(f"{'Metric':<25s} {'Pyro':>16s} {'Hydro':>16s} {'Direct':>16s}")
print("-" * 73)
for label, key in [('Revenue ($M/yr)', 'revenue'), ('Cost ($M/yr)', 'cost'), ('Profit ($M/yr)', 'profit')]:
    vals = [results[m][key] / 1e6 for m in methods]
    print(f"{label:<25s} {vals[0]:>14.2f}M {vals[1]:>14.2f}M {vals[2]:>14.2f}M")

for label, key in [('Revenue ($/kg feed)', 'revenue'), ('Cost ($/kg feed)', 'cost'), ('Profit ($/kg feed)', 'profit')]:
    vals = [results[m][key] / (THROUGHPUT_TONNES_PER_YEAR * 1000) for m in methods]
    print(f"{label:<25s} ${vals[0]:>13.2f}  ${vals[1]:>13.2f}  ${vals[2]:>13.2f}")

print("\n\n--- GHG EMISSIONS ---")
for label, key in [('Net GHG (tonne CO2-eq/yr)', 'net_ghg_tonne'), ('Net GHG (kg CO2-eq/kg feed)', 'net_ghg_kg')]:
    if 'kg feed' in label:
        vals = [results[m][key] / (THROUGHPUT_TONNES_PER_YEAR * 1000) for m in methods]
        print(f"{label:<25s} {vals[0]:>14.2f}  {vals[1]:>14.2f}  {vals[2]:>14.2f}")
    else:
        vals = [results[m][key] for m in methods]
        print(f"{label:<25s} {vals[0]:>14.0f}  {vals[1]:>14.0f}  {vals[2]:>14.0f}")

print("\n--- Revenue Breakdown by Material ($M/yr) ---")
all_materials = set()
for m in methods:
    all_materials.update(results[m]['revenue_detail'].keys())
all_materials = sorted(all_materials)
print(f"{'Material':<25s} {'Pyro':>14s} {'Hydro':>14s} {'Direct':>14s}")
print("-" * 67)
for mat in all_materials:
    vals = [results[m]['revenue_detail'].get(mat, 0) / 1e6 for m in methods]
    print(f"{mat:<25s} {vals[0]:>12.2f}M {vals[1]:>12.2f}M {vals[2]:>12.2f}M")


# ============================================================
# 6. VISUALIZATION
# ============================================================

sns.set_style("whitegrid")
plt.rcParams.update({
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.titleweight': 'bold',
    'figure.dpi': 150,
})

colors = ['#E74C3C', '#3498DB', '#2ECC71']
method_names = ['Pyrometallurgical', 'Hydrometallurgical', 'Direct Recycling']

fig, axes = plt.subplots(2, 3, figsize=(18, 11))
fig.suptitle('LFP Battery Recycling: Three-Method Comparison\n'
             f'(Throughput: {THROUGHPUT_TONNES_PER_YEAR:,} tonnes/year | EverBatt 2023 Methodology)',
             fontsize=16, fontweight='bold', y=1.01)

# --- Chart 1: Cost vs Revenue vs Profit (bar chart) ---
ax = axes[0, 0]
x = np.arange(len(methods))
width = 0.25
revenues = [results[m]['revenue'] / 1e6 for m in methods]
costs = [results[m]['cost'] / 1e6 for m in methods]
profits = [results[m]['profit'] / 1e6 for m in methods]
bars1 = ax.bar(x - width, revenues, width, label='Revenue', color='#2ECC71', edgecolor='white')
bars2 = ax.bar(x, costs, width, label='Cost', color='#E74C3C', edgecolor='white')
bars3 = ax.bar(x + width, profits, width, label='Profit', color='#3498DB', edgecolor='white')
ax.set_ylabel('Million USD / year')
ax.set_title('Cost, Revenue & Profit Comparison')
ax.set_xticks(x)
ax.set_xticklabels(method_names)
ax.legend(loc='upper left', frameon=True)
ax.axhline(y=0, color='black', linewidth=0.8)
for bar, val in zip(bars3, profits):
    color = '#2ECC71' if val > 0 else '#E74C3C'
    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.3,
            f'${val:.1f}M', ha='center', fontweight='bold', fontsize=10, color=color)

# --- Chart 2: Per-kg economics ---
ax = axes[0, 1]
kg_revenues = [results[m]['revenue'] / (THROUGHPUT_TONNES_PER_YEAR * 1000) for m in methods]
kg_costs = [results[m]['cost'] / (THROUGHPUT_TONNES_PER_YEAR * 1000) for m in methods]
kg_profits = [results[m]['profit'] / (THROUGHPUT_TONNES_PER_YEAR * 1000) for m in methods]
bars1 = ax.bar(x - width, kg_revenues, width, label='Revenue', color='#2ECC71', edgecolor='white')
bars2 = ax.bar(x, kg_costs, width, label='Cost', color='#E74C3C', edgecolor='white')
bars3 = ax.bar(x + width, kg_profits, width, label='Profit', color='#3498DB', edgecolor='white')
ax.set_ylabel('USD / kg feedstock')
ax.set_title('Per-kg Economics')
ax.set_xticks(x)
ax.set_xticklabels(method_names)
ax.legend(loc='upper left', frameon=True)
ax.axhline(y=0, color='black', linewidth=0.8)

# --- Chart 3: GHG Emissions (net) ---
ax = axes[0, 2]
net_ghg_tonnes = [results[m]['net_ghg_tonne'] for m in methods]
bars = ax.bar(method_names, net_ghg_tonnes, color=colors, edgecolor='white', width=0.5)
ax.set_ylabel('tonne CO2-eq / year')
ax.set_title('Net GHG Emissions')
for bar, val in zip(bars, net_ghg_tonnes):
    color = '#E74C3C' if val > 0 else '#2ECC71'
    label = f'{val:+.0f} t' if abs(val) < 1000 else f'{val/1000:+.1f}k t'
    y_pos = bar.get_height() + 200 if val >= 0 else bar.get_height() - 800
    ax.text(bar.get_x() + bar.get_width()/2., y_pos, label, ha='center', fontweight='bold', fontsize=11, color=color)
ax.axhline(y=0, color='black', linewidth=0.8)

# --- Chart 4: Revenue waterfall by material ---
ax = axes[1, 0]
all_mats = sorted(set().union(*[results[m]['revenue_detail'].keys() for m in methods]))
x_mat = np.arange(len(all_mats))
width_mat = 0.25
for i, method in enumerate(methods):
    vals = [results[method]['revenue_detail'].get(mat, 0) / 1e6 for mat in all_mats]
    ax.bar(x_mat + i * width_mat, vals, width_mat, label=method, color=colors[i], edgecolor='white')
ax.set_ylabel('Million USD / year')
ax.set_title('Revenue by Material')
ax.set_xticks(x_mat + width_mat)
ax.set_xticklabels([m.replace('Lithium carbonate', 'Li₂CO₃') for m in all_mats], rotation=30, ha='right', fontsize=9)
ax.legend(frameon=True)

# --- Chart 5: Cost breakdown ---
ax = axes[1, 1]
cost_categories = set()
for m in methods:
    cost_categories.update(results[m]['cost_detail'].keys())
cost_categories = sorted(cost_categories)
x_cost = np.arange(len(methods))
width_cost = 0.2
bottom = np.zeros(len(methods))
category_colors = plt.cm.tab20(np.linspace(0, 1, len(cost_categories)))
for i, cat in enumerate(cost_categories):
    vals = np.array([results[m]['cost_detail'].get(cat, 0) / 1e6 for m in methods])
    ax.bar(x_cost, vals, width_cost, bottom=bottom, label=cat, color=category_colors[i], edgecolor='white', linewidth=0.3)
    bottom += vals
ax.set_ylabel('Million USD / year')
ax.set_title('Cost Breakdown by Method')
ax.set_xticks(x_cost)
ax.set_xticklabels(method_names)
ax.legend(loc='upper right', fontsize=6, ncol=2, frameon=True)

# --- Chart 6: Material Recovery Rate Comparison ---
ax = axes[1, 2]
materials_list = ['LFP cathode', 'Graphite', 'Copper', 'Aluminum', 'Steel', 'Electrolyte', 'Plastics']
x_radar = np.arange(len(materials_list))
width_radar = 0.25
for i, method in enumerate(methods):
    rates = [RECOVERY_RATES[method].get(m, 0) * 100 for m in materials_list]
    bars = ax.bar(x_radar + i * width_radar, rates, width_radar, label=method, color=colors[i], edgecolor='white')
ax.set_ylabel('Recovery Rate (%)')
ax.set_title('Material Recovery Rates')
ax.set_xticks(x_radar + width_radar)
ax.set_xticklabels(materials_list, rotation=30, ha='right', fontsize=9)
ax.set_ylim(0, 105)
ax.legend(frameon=True)
for spine in ax.spines.values():
    spine.set_visible(True)

plt.tight_layout()
plt.savefig('LFP_Recycling_Analysis.png',
            dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
print("\n\n[Chart saved: LFP_Recycling_Analysis.png]")


# ============================================================
# 7. SUMMARY TABLE (DataFrame)
# ============================================================

print("\n\n--- SUMMARY TABLE ---")
summary = pd.DataFrame({
    'Metric': [
        'Revenue ($M/yr)',
        'Cost ($M/yr)',
        'Profit ($M/yr)',
        'Revenue ($/kg)',
        'Cost ($/kg)',
        'Profit ($/kg)',
        'Net GHG (t CO₂-eq/yr)',
        'Net GHG (kg CO₂-eq/kg feed)',
    ],
    'Pyrometallurgical': [
        f"{results['Pyro']['revenue']/1e6:.2f}",
        f"{results['Pyro']['cost']/1e6:.2f}",
        f"{results['Pyro']['profit']/1e6:.2f}",
        f"{results['Pyro']['revenue']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Pyro']['cost']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Pyro']['profit']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Pyro']['net_ghg_tonne']:.0f}",
        f"{results['Pyro']['net_ghg_kg']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
    ],
    'Hydrometallurgical': [
        f"{results['Hydro']['revenue']/1e6:.2f}",
        f"{results['Hydro']['cost']/1e6:.2f}",
        f"{results['Hydro']['profit']/1e6:.2f}",
        f"{results['Hydro']['revenue']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Hydro']['cost']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Hydro']['profit']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Hydro']['net_ghg_tonne']:.0f}",
        f"{results['Hydro']['net_ghg_kg']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
    ],
    'Direct Recycling': [
        f"{results['Direct']['revenue']/1e6:.2f}",
        f"{results['Direct']['cost']/1e6:.2f}",
        f"{results['Direct']['profit']/1e6:.2f}",
        f"{results['Direct']['revenue']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Direct']['cost']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Direct']['profit']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
        f"{results['Direct']['net_ghg_tonne']:.0f}",
        f"{results['Direct']['net_ghg_kg']/(THROUGHPUT_TONNES_PER_YEAR*1000):.2f}",
    ],
})
print(summary.to_string(index=False))


# ============================================================
# 8. KEY INSIGHTS
# ============================================================

print("\n" + "=" * 80)
print("  KEY INSIGHTS")
print("=" * 80)
print("""
1. DIRECT RECYCLING is the most profitable for LFP:
   - LFP cathode powder recovered directly ($10/kg value)
   - Lower chemical and energy costs than hydro
   - Best for LFP because cathode is the main value driver

2. HYDROMETALLURGICAL is intermediate:
   - Li₂CO₃ recovery adds revenue stream
   - Higher chemical costs (H₂SO₄, H₂O₂, NaOH)
   - More complex process with wastewater treatment needs

3. PYROMETALLURGICAL performs worst for LFP:
   - No valuable Co/Ni to recover (unlike NMC batteries)
   - Li and Al lost to slag
   - Mainly recovers Cu and steel (low value)
   - High energy consumption from smelting furnace

4. GHG: Direct recycling has the lowest net emissions
   - Less energy-intensive than pyro
   - Fewer chemicals than hydro
   - Higher avoided virgin material credits
""")
