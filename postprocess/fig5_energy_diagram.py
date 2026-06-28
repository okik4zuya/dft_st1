#!/usr/bin/env python3
"""
fig5_energy_diagram.py
======================
Figure 5 — DFT-derived band alignment energy diagram.

Shows VBM/CBM positions of all four systems on a common absolute
energy scale (O 1s core-level alignment), with:
  - Charge transfer arrows (auto-drawn based on relative band positions)
  - Mechanism label (Type-II / Z-scheme / S-scheme)
  - NHE scale on right axis
  - Experimental Eg values from Kubelka-Munk

Output: fig5_energy_diagram.png / .pdf

IMPORTANT: Fill in the ALIGNED_VBM values below after running
           band_alignment.py → read from its printed output.
"""

import sys, os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

sys.path.insert(0, os.path.dirname(__file__))
from plot_config import (apply_style, COLORS, LABELS, EG_EXP,
                         SINGLE_COL, DOUBLE_COL, cm2in)

apply_style()

# ── FILL IN AFTER band_alignment.py ─────────────────────────────────────────
# VBM positions on the aligned absolute scale (eV, TiO₂ VBM = 0 reference)
# These come from band_alignment.py printed output

ALIGNED_VBM = {
    'TiO2'          :  0.00,   # reference
    'SnO2_pristine' :  0.00,   # FILL IN → e.g. +0.25 or −0.40
    'SnO2_1to1'     :  0.00,   # FILL IN
    'SnO2_2to1'     :  0.00,   # FILL IN
}

# Computed CBM = VBM + Eg_exp
def get_cbm(sys_key):
    return ALIGNED_VBM[sys_key] + EG_EXP[sys_key]

# ── Demo values (used when ALIGNED_VBM all = 0) ─────────────────────────────
# Physically representative Type-II heterojunction as placeholder
DEMO_VBM = {
    'TiO2'          :  0.00,
    'SnO2_pristine' : -0.35,
    'SnO2_1to1'     : -0.55,
    'SnO2_2to1'     : -0.70,
}

all_zero = all(v == 0.0 for k, v in ALIGNED_VBM.items() if k != 'TiO2')
if all_zero:
    print("  NOTE: Using DEMO band alignment values.")
    print("  Run band_alignment.py and fill in ALIGNED_VBM above.")
    VBM = DEMO_VBM
else:
    VBM = ALIGNED_VBM

CBM = {k: VBM[k] + EG_EXP[k] for k in VBM}

# ── NHE conversion ───────────────────────────────────────────────────────────
# Vacuum level ≈ −4.44 eV vs NHE (standard value)
# E_NHE = E_vac + 4.44  where E_vac is our aligned scale
# Our scale: TiO2 VBM = 0
# Literature: rutile TiO2 VBM ≈ +2.91 V vs NHE
TIO2_VBM_NHE = 2.91   # V vs NHE

def to_nhe(e_aligned):
    return TIO2_VBM_NHE - e_aligned   # higher on our scale = lower on NHE

# ── Determine mechanism ───────────────────────────────────────────────────────

def classify_mechanism(vbm_A, cbm_A, vbm_B, cbm_B):
    """
    A = TiO2, B = SnO2-x.
    Returns mechanism string and electron/hole transfer directions.
    """
    delta_vbm = vbm_B - vbm_A
    delta_cbm = cbm_B - cbm_A

    if delta_cbm < 0 and delta_vbm < 0:
        mech = 'Type-II'
        e_dir = 'B→A (SnO₂₋ₓ→TiO₂)'
        h_dir = 'A→B (TiO₂→SnO₂₋ₓ)'
    elif delta_cbm > 0 and delta_vbm > 0:
        mech = 'Type-II'
        e_dir = 'A→B (TiO₂→SnO₂₋ₓ)'
        h_dir = 'B→A (SnO₂₋ₓ→TiO₂)'
    elif delta_cbm * delta_vbm < 0:
        mech = 'Z-scheme / S-scheme'
        e_dir = 'recombine at interface'
        h_dir = 'both materials retain holes'
    else:
        mech = 'Type-I'
        e_dir = 'both→lower gap'
        h_dir = 'both→lower gap'

    return mech, e_dir, h_dir

# ── Plotting ─────────────────────────────────────────────────────────────────

SYSTEMS = ['TiO2', 'SnO2_pristine', 'SnO2_1to1', 'SnO2_2to1']
PANEL_LABELS = {
    'TiO2'          : 'TiO₂',
    'SnO2_pristine' : 'SnO₂\n(pristine)',
    'SnO2_1to1'     : 'SnO₂₋ₓ\n1:1\n(Vo=12.5%)',
    'SnO2_2to1'     : 'SnO₂₋ₓ\n2:1\n(Vo=18.75%)',
}

BAR_W  = 0.45
X_POS  = np.array([0, 1, 2.2, 3.2])   # slightly separate the two SnO2-x

fig, ax = plt.subplots(figsize=(DOUBLE_COL, cm2in(13)))
fig.subplots_adjust(left=0.12, right=0.82, top=0.92, bottom=0.14)

e_min_plot = min(VBM.values()) - 0.8
e_max_plot = max(CBM.values()) + 0.9

for xi, sys_key in zip(X_POS, SYSTEMS):
    vbm   = VBM[sys_key]
    cbm   = CBM[sys_key]
    color = COLORS[sys_key]
    eg    = EG_EXP[sys_key]

    # Valence band block
    ax.fill_betweenx([e_min_plot, vbm],
                     xi - BAR_W/2, xi + BAR_W/2,
                     color=color, alpha=0.30, zorder=2)
    ax.hlines(vbm, xi - BAR_W/2, xi + BAR_W/2,
              colors=color, lw=2.2, zorder=4)
    ax.text(xi, vbm - 0.08, f'{vbm:.2f}',
            ha='center', va='top', fontsize=7.5, color=color)

    # Conduction band block
    ax.fill_betweenx([cbm, e_max_plot],
                     xi - BAR_W/2, xi + BAR_W/2,
                     color=color, alpha=0.30, zorder=2)
    ax.hlines(cbm, xi - BAR_W/2, xi + BAR_W/2,
              colors=color, lw=2.2, zorder=4)
    ax.text(xi, cbm + 0.08, f'{cbm:.2f}',
            ha='center', va='bottom', fontsize=7.5, color=color)

    # Eg annotation inside gap
    ax.annotate('', xy=(xi, vbm + 0.05),
                xytext=(xi, cbm - 0.05),
                arrowprops=dict(arrowstyle='<->', color=color, lw=1.0))
    ax.text(xi + BAR_W/2 + 0.04,
            (vbm + cbm) / 2,
            f'{eg:.2f} eV', va='center', fontsize=7, color=color)

    # System label below
    ax.text(xi, e_min_plot - 0.25, PANEL_LABELS[sys_key],
            ha='center', va='top', fontsize=8, color=color,
            fontweight='bold', multialignment='center')

# ── Charge transfer arrows ───────────────────────────────────────────────────
for sno2_key, xi_sno2 in zip(['SnO2_1to1', 'SnO2_2to1'],
                               [X_POS[2], X_POS[3]]):
    xi_tio2 = X_POS[0]
    mech, e_dir, h_dir = classify_mechanism(
        VBM['TiO2'], CBM['TiO2'],
        VBM[sno2_key], CBM[sno2_key])

    # Electron arrow (CBM level)
    cbm_tio2 = CBM['TiO2']
    cbm_sno2 = CBM[sno2_key]
    e_start  = (xi_tio2 + BAR_W/2, cbm_tio2)
    e_end    = (xi_sno2 - BAR_W/2, cbm_sno2)

    ax.annotate('e⁻', xy=e_end, xytext=e_start,
                arrowprops=dict(arrowstyle='->', color='#2980B9',
                                lw=1.3, connectionstyle='arc3,rad=-0.2'),
                fontsize=7, color='#2980B9', va='center')

    # Hole arrow (VBM level)
    vbm_tio2 = VBM['TiO2']
    vbm_sno2 = VBM[sno2_key]
    h_start  = (xi_tio2 + BAR_W/2, vbm_tio2)
    h_end    = (xi_sno2 - BAR_W/2, vbm_sno2)

    ax.annotate('h⁺', xy=h_end, xytext=h_start,
                arrowprops=dict(arrowstyle='->', color='#C0392B',
                                lw=1.3, connectionstyle='arc3,rad=0.2'),
                fontsize=7, color='#C0392B', va='center')

# Determine and print mechanism
mech_1, _, _ = classify_mechanism(
    VBM['TiO2'], CBM['TiO2'], VBM['SnO2_1to1'], CBM['SnO2_1to1'])
print(f"\nDetected heterojunction mechanism: {mech_1}")

# ── NHE right axis ───────────────────────────────────────────────────────────
ax_nhe = ax.twinx()
ax_nhe.set_ylim(to_nhe(e_max_plot), to_nhe(e_min_plot))
ax_nhe.set_ylabel('Potential vs NHE (V)', fontsize=8)
ax_nhe.tick_params(labelsize=7)

# O₂/H₂O and H₂/H⁺ reference lines
for e_nhe, lbl in [(0.0, 'H⁺/H₂  (0 V)'),
                   (1.23, 'O₂/H₂O  (1.23 V)')]:
    e_our = TIO2_VBM_NHE - e_nhe
    if e_min_plot <= e_our <= e_max_plot:
        ax.axhline(e_our, color='0.55', lw=0.8, ls='-.', alpha=0.7)
        ax.text(X_POS[-1] + BAR_W/2 + 0.1, e_our, lbl,
                va='center', fontsize=6.5, color='0.45')

# ── Labels and formatting ─────────────────────────────────────────────────────
ax.set_xlim(X_POS[0] - 0.8, X_POS[-1] + 0.9)
ax.set_ylim(e_min_plot, e_max_plot)
ax.set_ylabel('Energy (eV, aligned to TiO₂ VBM = 0)', fontsize=8.5)
ax.set_xticks([])
ax.spines['bottom'].set_visible(False)
ax.spines['top'].set_visible(False)

# VB / CB labels on left
ax.text(-0.07, (e_min_plot + VBM['TiO2'])/2,
        'Valence band', rotation=90, ha='center', va='center',
        fontsize=7, color='0.5', transform=ax.get_yaxis_transform())
ax.text(-0.07, (CBM['TiO2'] + e_max_plot)/2,
        'Conduction band', rotation=90, ha='center', va='center',
        fontsize=7, color='0.5', transform=ax.get_yaxis_transform())

# Legend
e_patch = mpatches.Patch(color='#2980B9', label='Electron transfer (e⁻)')
h_patch = mpatches.Patch(color='#C0392B', label='Hole transfer (h⁺)')
ax.legend(handles=[e_patch, h_patch], loc='upper right',
          fontsize=7.5, framealpha=0.9)

# Mechanism annotation
ax.text(0.50, 0.97,
        f'Mechanism: {mech_1}',
        transform=ax.transAxes, ha='center', va='top',
        fontsize=8.5, fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.3', fc='#EBF5FB', ec='#2980B9', lw=0.8))

fig.suptitle('DFT Band Alignment — SnO₂₋ₓ/TiO₂ Heterojunction\n'
             '(O 1s core-level alignment; CBM = VBM + $E_g^{exp}$)',
             fontsize=9.5, fontweight='bold', y=1.00)

if all_zero:
    ax.text(0.5, 0.5, 'DEMO VALUES\nReplace ALIGNED_VBM with real DFT data',
            transform=ax.transAxes, ha='center', va='center',
            fontsize=11, color='red', alpha=0.25,
            fontweight='bold', rotation=20)

out_dir = os.path.dirname(__file__)
for ext in ('png', 'pdf'):
    path = os.path.join(out_dir, f'fig5_energy_diagram.{ext}')
    fig.savefig(path)
    print(f"Saved: {path}")
plt.close()
