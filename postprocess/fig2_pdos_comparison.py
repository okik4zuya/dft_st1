#!/usr/bin/env python3
"""
fig2_pdos_comparison.py
=======================
Figure 2 — PDOS detail comparison across all four systems,
aligned to a common energy reference using core-level shift
(from band_alignment.py output).

Layout (single-column, stacked):
  ┌──────────────────────┐
  │ (a) TiO₂             │  Ti 3d + O 2p
  ├──────────────────────┤
  │ (b) SnO₂ pristine    │  Sn 5s + Sn 4d + O 2p
  ├──────────────────────┤
  │ (c) SnO₂₋ₓ  1:1     │  Sn 5s + Sn 4d + O 2p  + Vo state
  ├──────────────────────┤
  │ (d) SnO₂₋ₓ  2:1     │  Sn 5s + Sn 4d + O 2p  + Vo state
  └──────────────────────┘

Output: fig2_pdos_comparison.png / .pdf
"""

import sys, os, glob, json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.dirname(__file__))
from plot_config import (apply_style, COLORS, LABELS, EG_EXP,
                         DOUBLE_COL, SINGLE_COL, cm2in,
                         add_fermi_line, shade_gap)

apply_style()

BASE = os.path.join(os.path.dirname(__file__), '..')

# ── Core-level shift values ─────────────────────────────────────────────────
# Auto-loaded from ../band_alignment.json (written by band_alignment.py).
# These align each system's energy axis to the same absolute scale
# (O 1s core-level alignment). If the JSON is absent, all shifts default to 0
# (each panel is then plotted relative to its own Fermi level).
CORE_SHIFT = {
    'TiO2'          : 0.000,
    'SnO2_pristine' : 0.000,
    'SnO2_1to1'     : 0.000,
    'SnO2_2to1'     : 0.000,
}
_ALIGN_JSON = os.path.join(BASE, 'band_alignment.json')
if os.path.exists(_ALIGN_JSON):
    with open(_ALIGN_JSON) as _f:
        _al = json.load(_f)
    for _s in CORE_SHIFT:
        if _s in _al and _al[_s].get('delta_core') is not None:
            CORE_SHIFT[_s] = _al[_s]['delta_core']
    print(f"  Loaded core-level shifts from {os.path.basename(_ALIGN_JSON)}: "
          + ", ".join(f"{k}={v:+.3f}" for k, v in CORE_SHIFT.items()))
else:
    print("  NOTE: band_alignment.json not found — CORE_SHIFT=0 (Fermi-referenced).")

SYSTEMS = {
    'TiO2': {
        'pdos_glob'  : f'{BASE}/TiO2/dos/TiO2_pristine_pdos.pdos_atm*',
        'scf_out'    : f'{BASE}/TiO2/scf/TiO2_pristine.scf.out',
        'color'      : COLORS['TiO2'],
        'eg_exp'     : EG_EXP['TiO2'],
        'species_map': {
            '(Ti)_wfc#3(d)' : ('Ti 3d', COLORS['Ti_3d']),
            '(O)_wfc#2(p)'  : ('O 2p',  COLORS['O_2p']),
        },
        'panel' : 'a',
    },
    'SnO2_pristine': {
        'pdos_glob'  : f'{BASE}/pristine/dos/SnO2_pristine_pdos.pdos_atm*',
        'scf_out'    : f'{BASE}/pristine/scf/SnO2_pristine.scf.out',
        'color'      : COLORS['SnO2_pristine'],
        'eg_exp'     : EG_EXP['SnO2_pristine'],
        'species_map': {
            '(Sn)_wfc#1(s)' : ('Sn 5s', COLORS['Sn_5s']),
            '(Sn)_wfc#2(d)' : ('Sn 4d', COLORS['Sn_4d']),
            '(O)_wfc#2(p)'  : ('O 2p',  COLORS['O_2p']),
        },
        'panel' : 'b',
    },
    'SnO2_1to1': {
        'pdos_glob'  : f'{BASE}/ratio_1to1/dos/SnO2_1to1_pdos.pdos_atm*',
        'scf_out'    : f'{BASE}/ratio_1to1/scf/SnO2_1to1.scf.out',
        'color'      : COLORS['SnO2_1to1'],
        'eg_exp'     : EG_EXP['SnO2_1to1'],
        'species_map': {
            '(Sn)_wfc#1(s)' : ('Sn 5s', COLORS['Sn_5s']),
            '(Sn)_wfc#2(d)' : ('Sn 4d', COLORS['Sn_4d']),
            '(O)_wfc#2(p)'  : ('O 2p',  COLORS['O_2p']),
        },
        'panel' : 'c',
        'has_vo': True,
    },
    'SnO2_2to1': {
        'pdos_glob'  : f'{BASE}/ratio_2to1/dos/SnO2_2to1_pdos.pdos_atm*',
        'scf_out'    : f'{BASE}/ratio_2to1/scf/SnO2_2to1.scf.out',
        'color'      : COLORS['SnO2_2to1'],
        'eg_exp'     : EG_EXP['SnO2_2to1'],
        'species_map': {
            '(Sn)_wfc#1(s)' : ('Sn 5s', COLORS['Sn_5s']),
            '(Sn)_wfc#2(d)' : ('Sn 4d', COLORS['Sn_4d']),
            '(O)_wfc#2(p)'  : ('O 2p',  COLORS['O_2p']),
        },
        'panel' : 'd',
        'has_vo': True,
    },
}

E_MIN, E_MAX = -8.0, 5.0


def read_fermi(scf_out):
    import re
    if not os.path.exists(scf_out):
        return 0.0
    with open(scf_out) as f:
        txt = f.read()
    m = re.search(r'the Fermi energy is\s+([-\d.]+)', txt, re.I)
    return float(m.group(1)) if m else 0.0


def read_pdos_channel(pdos_glob, key_label_color_map, fermi, core_shift):
    """Read and aggregate PDOS, return dict {label: (energy, dos, color)}."""
    files = glob.glob(pdos_glob)
    result = {}

    for f in files:
        fname = os.path.basename(f)
        for key, (label, color) in key_label_color_map.items():
            if key not in fname:
                continue
            try:
                raw = np.loadtxt(f, comments='#')
                if raw.ndim == 1:
                    raw = raw.reshape(1, -1)
                energy = raw[:, 0] - fermi + core_shift
                dos    = raw[:, 1:].sum(axis=1)   # sum all spin channels

                if label not in result:
                    result[label] = {'e': energy, 'dos': dos, 'color': color}
                else:
                    result[label]['dos'] += dos
            except Exception as ex:
                print(f"  WARNING: {f}: {ex}")

    return result


def make_demo_pdos(sys_key, eg):
    """Demo PDOS."""
    e = np.linspace(E_MIN, E_MAX, 1200)
    def g(c, w, h): return h * np.exp(-((e - c) / w) ** 2)

    if sys_key == 'TiO2':
        return {
            'Ti 3d' : {'e': e, 'dos': g(0.3, 0.9, 5) + g(2.5, 0.8, 2),
                       'color': COLORS['Ti_3d']},
            'O 2p'  : {'e': e, 'dos': g(-3.5, 1.0, 4) + g(-1.5, 0.8, 3),
                       'color': COLORS['O_2p']},
        }
    elif sys_key == 'SnO2_pristine':
        return {
            'Sn 5s' : {'e': e, 'dos': g(1.5, 0.6, 2),
                       'color': COLORS['Sn_5s']},
            'Sn 4d' : {'e': e, 'dos': g(-5.0, 0.5, 4),
                       'color': COLORS['Sn_4d']},
            'O 2p'  : {'e': e, 'dos': g(-3.5, 1.0, 4) + g(-1.5, 0.8, 3),
                       'color': COLORS['O_2p']},
        }
    else:
        vo_height = 1.8 if sys_key == 'SnO2_1to1' else 2.8
        vo_width  = 0.12 if sys_key == 'SnO2_1to1' else 0.22
        return {
            'Sn 5s' : {'e': e,
                       'dos': g(-eg + 0.35, vo_width, vo_height) + g(1.5, 0.6, 2),
                       'color': COLORS['Sn_5s']},
            'Sn 4d' : {'e': e,
                       'dos': g(-5.0, 0.5, 4) + g(-eg + 0.35, vo_width * 1.5, 1.0),
                       'color': COLORS['Sn_4d']},
            'O 2p'  : {'e': e,
                       'dos': g(-3.5, 1.0, 4) + g(-1.5, 0.8, 3),
                       'color': COLORS['O_2p']},
        }


# ── figure ──────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(4, 1, figsize=(DOUBLE_COL, cm2in(20)),
                         sharex=True)
fig.subplots_adjust(hspace=0.08, left=0.1, right=0.97,
                    top=0.96, bottom=0.07)

for ax, (sys_key, cfg) in zip(axes, SYSTEMS.items()):
    fermi      = read_fermi(cfg['scf_out'])
    shift      = CORE_SHIFT[sys_key]
    channels   = read_pdos_channel(cfg['pdos_glob'], cfg['species_map'],
                                   fermi, shift)
    eg         = cfg['eg_exp']
    has_vo     = cfg.get('has_vo', False)

    if not channels:
        print(f"  Using DEMO PDOS for {sys_key}")
        channels = make_demo_pdos(sys_key, eg)

    max_dos = 0
    for label, ch in channels.items():
        e   = ch['e']
        dos = ch['dos']
        clr = ch['color']
        m   = (e >= E_MIN) & (e <= E_MAX)
        ax.plot(e[m], dos[m], color=clr, lw=1.3, label=label, zorder=3)
        ax.fill_between(e[m], 0, dos[m], alpha=0.10, color=clr, zorder=2)
        max_dos = max(max_dos, dos[m].max())

    # Vo defect band shading
    if has_vo:
        ax.axvspan(-eg + 0.05, -0.05, alpha=0.12,
                   color=COLORS['Vo_state'], zorder=1,
                   label='Vo defect states')
        # Annotate
        mid = (-eg + 0.05 + (-0.05)) / 2
        ax.text(mid, max_dos * 0.7, 'Vo\nstates',
                ha='center', va='center', fontsize=7,
                color=COLORS['Vo_state'], fontweight='bold')

    # Fermi line
    ax.axvline(0, color='k', lw=0.8, ls='--', alpha=0.5)

    # Gap shading
    shade_gap(ax, -eg, 0, orientation='v', alpha=0.06, color='grey')

    # Eg annotation
    ax.annotate('', xy=(0, max_dos * 0.88), xytext=(-eg, max_dos * 0.88),
                arrowprops=dict(arrowstyle='<->', color='k', lw=0.9))
    ax.text(-eg / 2, max_dos * 0.92,
            f'$E_g$ = {eg:.2f} eV', ha='center', va='bottom',
            fontsize=7, color='k')

    ax.set_ylim(0, max_dos * 1.15)
    ax.set_ylabel('PDOS (states/eV)', fontsize=8)
    ax.legend(loc='upper left', fontsize=7, ncol=2,
              handlelength=1.2, framealpha=0.9)

    # Panel label + system name
    panel_lbl = f'({cfg["panel"]}) {LABELS.get(sys_key, sys_key)}'
    ax.text(0.01, 0.96, panel_lbl, transform=ax.transAxes,
            fontsize=8, fontweight='bold', va='top')

    # Right-side colour tag
    ax.spines['left'].set_color(cfg['color'])
    ax.spines['left'].set_linewidth(2)

axes[-1].set_xlabel('Energy relative to $E_F$ (eV)', fontsize=9)
axes[-1].set_xlim(E_MIN, E_MAX)

out_dir = os.path.dirname(__file__)
for ext in ('png', 'pdf'):
    path = os.path.join(out_dir, f'fig2_pdos_comparison.{ext}')
    fig.savefig(path)
    print(f"Saved: {path}")
plt.close()
