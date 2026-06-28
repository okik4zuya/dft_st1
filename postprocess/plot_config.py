"""
plot_config.py
==============
Shared publication-quality style settings for all figure scripts.
Journal target: Applied Catalysis B / ACS Catalysis / JMCA
Column widths: single = 8.6 cm, double = 17.8 cm
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# ── Colour palette ─────────────────────────────────────────────────────────
# Chosen for colourblind accessibility and print/screen parity
COLORS = {
    'TiO2'           : '#1A6FBF',   # steel blue
    'SnO2_pristine'  : '#555555',   # neutral grey
    'SnO2_1to1'      : '#E07B00',   # amber        (1:1, 12.5% Vo, 2.41 eV)
    'SnO2_2to1'      : '#C0392B',   # crimson      (2:1, 18.75% Vo, 2.21 eV)
    'spin_up'        : '#2E86C1',   # cerulean
    'spin_dn'        : '#E74C3C',   # coral
    'Sn_5s'          : '#27AE60',   # emerald
    'Sn_4d'          : '#8E44AD',   # violet
    'O_2p'           : '#E07B00',   # amber
    'Ti_3d'          : '#1A6FBF',   # steel blue
    'Vo_state'       : '#C0392B',   # crimson (highlight)
    'visible_light'  : '#FFF9C4',   # pale yellow band
    'uv_light'       : '#E8D5F5',   # pale violet band
    'accumulation'   : '#E74C3C',   # charge gain  (delta_rho +)
    'depletion'      : '#2980B9',   # charge loss  (delta_rho -)
}

LABELS = {
    'TiO2'          : 'TiO₂',
    'SnO2_pristine' : 'SnO₂ (pristine)',
    'SnO2_1to1'     : 'SnO₂₋ₓ 1:1  (Vo = 12.5%)',
    'SnO2_2to1'     : 'SnO₂₋ₓ 2:1  (Vo = 18.75%)',
}

EG_EXP = {
    'TiO2'          : 3.00,
    'SnO2_pristine' : 3.60,
    'SnO2_1to1'     : 2.41,
    'SnO2_2to1'     : 2.21,
}

# ── RC params ──────────────────────────────────────────────────────────────
RC = {
    # Font
    'font.family'        : 'sans-serif',
    'font.sans-serif'    : ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size'          : 9,
    'axes.titlesize'     : 10,
    'axes.labelsize'     : 9,
    'xtick.labelsize'    : 8,
    'ytick.labelsize'    : 8,
    'legend.fontsize'    : 8,
    # Lines
    'lines.linewidth'    : 1.5,
    'axes.linewidth'     : 0.8,
    'xtick.major.width'  : 0.8,
    'ytick.major.width'  : 0.8,
    'xtick.minor.width'  : 0.5,
    'ytick.minor.width'  : 0.5,
    'xtick.direction'    : 'in',
    'ytick.direction'    : 'in',
    'xtick.major.size'   : 4,
    'ytick.major.size'   : 4,
    'xtick.minor.size'   : 2,
    'ytick.minor.size'   : 2,
    # Legend
    'legend.frameon'     : True,
    'legend.framealpha'  : 0.9,
    'legend.edgecolor'   : '0.8',
    # Save
    'savefig.dpi'        : 300,
    'savefig.bbox'       : 'tight',
    'savefig.pad_inches' : 0.05,
    # Other
    'axes.spines.top'    : False,
    'axes.spines.right'  : False,
}

def apply_style():
    """Apply journal RC params globally."""
    mpl.rcParams.update(RC)

# cm → inches helper
def cm2in(cm):
    return cm / 2.54

# Figure width presets (cm)
SINGLE_COL = cm2in(8.6)
DOUBLE_COL = cm2in(17.8)

def add_zero_line(ax, orientation='h', color='k', lw=0.6, ls='--', alpha=0.4):
    """Draw E=0 / x=0 reference line."""
    if orientation == 'h':
        ax.axhline(0, color=color, lw=lw, ls=ls, alpha=alpha)
    else:
        ax.axvline(0, color=color, lw=lw, ls=ls, alpha=alpha)

def add_fermi_line(ax, orientation='h', **kw):
    """Dashed Fermi level line at 0."""
    defaults = dict(color='k', lw=0.8, ls='--', alpha=0.5,
                    label='$E_F$')
    defaults.update(kw)
    if orientation == 'h':
        ax.axhline(0, **defaults)
    else:
        ax.axvline(0, **defaults)

def shade_gap(ax, vbm, cbm, orientation='v', alpha=0.08, color='grey'):
    """Shade the band gap region."""
    if orientation == 'v':
        ax.axvspan(vbm, cbm, alpha=alpha, color=color, zorder=0)
    else:
        ax.axhspan(vbm, cbm, alpha=alpha, color=color, zorder=0)
