"""
实验室到工业规模扩展：LFP 电池回收模型产能放大方法
====================================================

问题：
  我们手里只有实验室规模的回收数据（例如 5 kg/day、几百克批量、少量试验）
  想把它扩展到模型中的工业规模（例如 10,000 t/yr），怎么做？

核心思路：
  1. 实验室数据首先转成“每 kg 原料进入”的指标
     - 化学品消耗量（kg/kg 投入）
     - 电能消耗（kWh/kg）
     - 天然气消耗（MJ/kg）
     - 材料回收率（%）
  2. 把这些指标写入模型中
  3. 产能扩大时分别考虑：
     - 变动成本：按线性比例放大
     - 劳动成本：按 throughput^0.6 放大（规模经济）
     - 资本投入：按 throughput^0.6~0.8 放大
  4. 扫描不同规模（如 10、100、500、1000、5000、10000、50000 t/yr）
     找到 breakeven 产能，即利润开始为正的最低规模

使用方法：
  1. 修改 LAB_DATA 中的实验室数据
  2. 运行：python scale_lab_to_industry_CN.py
  3. 输出：
       - scaling_results_CN.csv
       - scaling_analysis_CN.png

本脚本是对 lfp_analysis_verified.py 的扩展版，遵循相同的 EverBatt 模型框架。
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import lfp_analysis_verified as lfp

# ============================================================
# 1. 请在这里填写你的实验室数据
# ============================================================
LAB_DATA = {
    'method': 'Direct',  # 可选：'Pyro', 'Hydro', 'Direct'

    'lab_scale': {
        'throughput_kg_per_day': 5,      # 例如实验室每天处理 5 kg
        'operating_days_per_year': 250,  # 约 250 天/年
    },

    'chemical_consumption_per_kg': {
        # 这里必须填写“每 kg 电池输入”的化学品消耗量
        # 这些值应来自实验室试验或文献
        'Lithium Carbonate': 0.004,
        'Carbon Dioxide': 0.12,
    },

    'energy_consumption_per_kg': {
        'Natural gas (MJ)': 2.5,
        'Electricity (kWh)': 1.1,
    },

    'recovery_rates': {
        # 这里填写你获得的实际回收率
        'LFP cathode': 0.92,
        'Graphite': 0.88,
        'Binder (PVDF)': 0.88,
        'Carbon black': 0.88,
        'Copper': 0.92,
        'Aluminum': 0.92,
        'Steel': 0.92,
        'Electrolyte (LiPF6 + solvents)': 0.55,
        'Plastics': 0.55,
        'Li as Li2CO3': 0.0,
    },

    'capex_baseline': 12e6,
    'capex_reference_capacity': 10000,
    'capex_scale_factor': 0.7,
}

# ============================================================
# 2. 将实验室数据写入模型
# ============================================================
def update_model_with_lab_data(lab_data):
    """将实验室参数写入 lfp_analysis_verified.py 中的全局参数。"""
    method = lab_data['method']

    if 'chemical_consumption_per_kg' in lab_data:
        for chem, qty in lab_data['chemical_consumption_per_kg'].items():
            if chem in lfp.CHEMICALS_PER_KG[method]:
                lfp.CHEMICALS_PER_KG[method][chem] = qty

    if 'energy_consumption_per_kg' in lab_data:
        for energy_type, qty in lab_data['energy_consumption_per_kg'].items():
            if energy_type in lfp.ENERGY_PER_KG[method]:
                lfp.ENERGY_PER_KG[method][energy_type] = qty

    if 'recovery_rates' in lab_data:
        for mat, rate in lab_data['recovery_rates'].items():
            if mat in lfp.RECOVERY[method]:
                lfp.RECOVERY[method][mat] = rate

    print(f"已更新模型参数：{method}")
    annual_tpy = (lab_data['lab_scale']['throughput_kg_per_day'] *
                  lab_data['lab_scale']['operating_days_per_year'] / 1000)
    print(f"实验室等效规模：{annual_tpy:.2f} t/yr")


# ============================================================
# 3. 扩大产能时的资本投入缩放
# ============================================================
def scale_capex(method, throughput, lab_data):
    """
    资本成本按非线性关系扩展：
        CapEx = CapEx_base * (throughput / ref_capacity)^scale_factor
    
    典型 scale_factor = 0.6~0.8
    """
    capex_base = lab_data['capex_baseline']
    ref_cap = lab_data['capex_reference_capacity']
    factor = lab_data['capex_scale_factor']
    return capex_base * (throughput / ref_cap) ** factor


# ============================================================
# 4. 运行不同产能规模的灵敏度分析
# ============================================================
def run_scaling_analysis(lab_data, prices, battery_fee, throughput_range=None):
    """在多个产能点下计算经济性。"""
    if throughput_range is None:
        throughput_range = [10, 50, 100, 500, 1000, 5000, 10000, 50000]

    method = lab_data['method']
    rows = []

    for throughput in throughput_range:
        result = lfp.analyze_method(method, throughput, prices, battery_fee)
        capex_scaled = scale_capex(method, throughput, lab_data)

        rows.append({
            'Throughput (t/yr)': throughput,
            'CapEx_scaled ($M)': capex_scaled / 1e6,
            'Cost ($M/yr)': result['cost'] / 1e6,
            'Revenue ($M/yr)': result['revenue'] / 1e6,
            'Profit ($M/yr)': result['profit'] / 1e6,
            'Cost ($/kg)': result['cost'] / (throughput * 1000),
            'Revenue ($/kg)': result['revenue'] / (throughput * 1000),
            'Profit ($/kg)': result['profit'] / (throughput * 1000),
            'GHG (kg CO2-eq/kg)': result['net_ghg_kg'] / (throughput * 1000),
            'Labor ($M/yr)': result['cost_detail'].get('Labor', 0) / 1e6,
        })

    df = pd.DataFrame(rows)
    return df


# ============================================================
# 5. 可视化图表
# ============================================================
def plot_scaling_analysis(df, method):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f'{method} 回收工艺：实验室到工业规模扩展分析', fontsize=15, fontweight='bold')

    # 1. 成本/收入/利润 vs 产能
    ax = axes[0, 0]
    ax.plot(df['Throughput (t/yr)'], df['Revenue ($/kg)'], 'o-', label='Revenue', color='#2ECC71')
    ax.plot(df['Throughput (t/yr)'], df['Cost ($/kg)'], 's-', label='Cost', color='#E74C3C')
    ax.plot(df['Throughput (t/yr)'], df['Profit ($/kg)'], '^-', label='Profit', color='#3498DB')
    ax.axhline(0, color='black', lw=1, ls='--')
    ax.set_xscale('log')
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('USD / kg')
    ax.set_title('单位 kg 成本、收入与利润')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. 利润随规模变化
    ax = axes[0, 1]
    colors = ['#E74C3C' if p < 0 else '#2ECC71' for p in df['Profit ($/kg)']]
    ax.bar(range(len(df)), df['Profit ($/kg)'], color=colors, edgecolor='black', linewidth=1)
    ax.axhline(0, color='black', lw=1)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels([str(int(v)) for v in df['Throughput (t/yr)']], rotation=45)
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('Profit ($/kg)')
    ax.set_title('利润随规模变化（寻找盈亏平衡点）')

    # 3. CapEx 与产能关系
    ax = axes[1, 0]
    ax.plot(df['Throughput (t/yr)'], df['CapEx_scaled ($M)'], 'o-', color='#E67E22', label='Scaled CapEx')
    ax.set_xscale('log')
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('CapEx ($M)')
    ax.set_title('资本投入随产能增长')
    ax.grid(True, alpha=0.3)
    ax.legend()

    # 4. GHG vs scale
    ax = axes[1, 1]
    ax.plot(df['Throughput (t/yr)'], df['GHG (kg CO2-eq/kg)'], 'D-', color='#8E44AD')
    ax.set_xscale('log')
    ax.set_xlabel('Throughput (t/yr)')
    ax.set_ylabel('GHG (kg CO2-eq/kg)')
    ax.set_title('GHG 强度随规模变化')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('scaling_analysis_CN.png', dpi=150, bbox_inches='tight')
    print("已保存: scaling_analysis_CN.png")
    plt.close()


# ============================================================
# 6. 主函数
# ============================================================
def main():
    print("=" * 100)
    print("LFP 回收工艺：从实验室规模到工业规模扩展分析")
    print("=" * 100)

    # 第一步：将实验室数据写入模型
    update_model_with_lab_data(LAB_DATA)

    # 第二步：运行扫描分析
    throughput_range = [10, 50, 100, 500, 1000, 5000, 10000, 50000]
    df = run_scaling_analysis(LAB_DATA, lfp.PRICES_2019, -2.0, throughput_range)

    # 第三步：输出 CSV
    df.to_csv('scaling_results_CN.csv', index=False)
    print("已保存: scaling_results_CN.csv")

    # 第四步：绘图
    plot_scaling_analysis(df, LAB_DATA['method'])

    # 第五步：寻找盈亏平衡点
    profitable = df[df['Profit ($/kg)'] > 0]
    if len(profitable) > 0:
        best = profitable.iloc[0]
        print(f"\n盈亏平衡产能约为：{best['Throughput (t/yr)']:.0f} t/yr")
        print(f"对应利润：{best['Profit ($/kg)']:.2f} $/kg")
        print(f"对应成本：{best['Cost ($/kg)']:.2f} $/kg")
        print(f"对应收入：{best['Revenue ($/kg)']:.2f} $/kg")
    else:
        print("\n在当前测试范围内，未发现正利润规模；可能需要更大产能或更优参数。")

    print("\n说明：")
    print("- 变动成本（化学品、能耗）按吞吐量线性扩展")
    print("- 劳动成本：按 throughput^0.6 扩展（规模经济）")
    print("- 资本投入：按 throughput^0.6~0.8 扩展")
    print("- 若实验室数据不准，可继续更新 LAB_DATA 中的 chemical_consumption_per_kg / energy_consumption_per_kg / recovery_rates")
    print("=" * 100)


if __name__ == '__main__':
    main()
