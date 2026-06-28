#!/usr/bin/env python3
"""
fig4_optical_absorption.py
==========================
Figure 4 — Optical absorption coefficient α(ω) comparison:
  TiO₂ | SnO₂ pristine | SnO₂₋ₓ 1:1 | SnO₂₋ₓ 2:1

Layout (double-column):
  Main panel: α(ω) vs photon energy (eV)
  Inset:      Tauc plot  (αhν)^(1/2) vs hν  for direct comparison with K-M

Output: fig4_optical_absorption.png / .pdf
"""

import sys, os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

sys.path.insert(0, os.path.dirname(__file__))
from plot_config import (apply_style, COLORS, LABELS, EG_EXP,
                         DOUBLE_COL, cm2in)

apply_style()

BASE = os.path.join(os.path.dirname(__file__), '..')

SYSTEMS_ORDER = ['TiO2', 'SnO2_pristine', 'SnO2_1to1', 'SnO2_2to1']

EPSILON_FILES = {
    'TiO2'          : f'{BASE}/TiO2/optical/',
    'SnO2_pristine' : f'{BASE}/pristine/optical/',
    'SnO2_1to1'     : f'{BASE}/ratio_1to1/optical/',
    'SnO2_2to1'     : f'{BASE}/ratio_2to1/optical/',
}

# ── Physics ──────────────────────────────────────────────────────────────────

def alpha_from_epsilon(energy_eV, eps1, eps2):
    """
    Absorption coefficient from complex dielectric function.
    α(ω) = (√2 · ω/c) · √[ √(ε₁² + ε₂²) − ε₁ ]   [m⁻¹]
    Convert to cm⁻¹.
    """
    hbar_eV  = 6.582119e-16   # eV·s
    c_cms    = 2.998e10       # cm/s
    omega    = energy_eV / hbar_eV               # rad/s
    mod_eps  = np.sqrt(eps1**2 + eps2**2)
    n2       = (mod_eps - eps1) / 2.0            # n²  (real part of √ε)
    n2       = np.maximum(n2, 0)                 # numerical safety
    alpha    = (np.sqrt(2) * omega / c_cms) * np.sqrt(n2)   # cm⁻¹
    return alpha


def read_epsilon(folder):
    """Read epsilon_re.dat and epsilon_im.dat from epsilon.x output."""
    re_path = os.path.join(folder, 'epsilon_re.dat')
    im_path = os.path.join(folder, 'epsilon_im.dat')

    if not (os.path.exists(re_path) and os.path.exists(im_path)):
        return None, None, None

    try:
        re_data = np.loadtxt(re_path, comments='#')
        im_data = np.loadtxt(im_path, comments='#')
    except Exception as e:
        print(f"  WARNING: {folder}: {e}")
        return None, None, None

    energy = re_data[:, 0]
    eps1   = re_data[:, 1]
    eps2   = im_data[:, 1]
    return energy, eps1, eps2


def make_demo_epsilon(eg, n=1000):
    """
    Demo dielectric function consistent with a semiconductor of gap eg.
    Lorentz oscillator model.
    """
    energy = np.linspace(0.1, 6.5, n)
    omega0 = eg + 0.3          # resonance just above gap
    gamma  = 0.2               # damping
    f      = 8.0               # oscillator strength

    denom  = (omega0**2 - energy**2)**2 + (gamma * energy)**2
    eps1   = 1 + f * (omega0**2 - energy**2) / denom
    eps2   = f * gamma * energy / denom
    # Add second oscillator at higher energy
    omega0b = eg + 1.5
    denomB  = (omega0b**2 - energy**2)**2 + (0.4 * energy)**2
    eps2   += 15.0 * 0.4 * energy / denomB

    return energy, eps1, eps2


# ── Tauc plot ────────────────────────────────────────────────────────────────

def tauc(energy, alpha, transition='indirect'):
    """
    Tauc plot: (αhν)^n vs hν
    n = 1/2 for indirect, n = 2 for direct.
    Rutile SnO2 and TiO2: indirect allowed → use n=1/2.
    """
    n   = 0.5 if transition == 'indirect' else 2.0
    hnu = energy
    val = (alpha * hnu) ** n
    return hnu, val


# ── figure ───────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(DOUBLE_COL, cm2in(11)))
ax  = fig.add_axes([0.11, 0.13, 0.62, 0.82])   # main panel
ax2 = fig.add_axes([0.77, 0.30, 0.21, 0.55])   # Tauc inset

max_alpha = 0

for sys_key in SYSTEMS_ORDER:
    color  = COLORS[sys_key]
    label  = LABELS[sys_key]
    eg     = EG_EXP[sys_key]
    folder = EPSILON_FILES[sys_key]

    energy, eps1, eps2 = read_epsilon(folder)

    if energy is None:
        print(f"  Using DEMO epsilon for {sys_key}")
        energy, eps1, eps2 = make_demo_epsilon(eg)

    alpha = alpha_from_epsilon(energy, eps1, eps2)

    # ── Main plot ──────────────────────────────────────────────────────
    mask = (energy >= 0.5) & (energy <= 6.5)
    ax.plot(energy[mask], alpha[mask] / 1e4,   # convert to 10⁴ cm⁻¹
            color=color, lw=1.8, label=label, zorder=3)

    # Mark onset with vertical dashed line
    ax.axvline(eg, color=color, lw=0.9, ls=':', alpha=0.7)
    ax.text(eg + 0.04, 0.5,
            f'{eg:.2f} eV\n({1240/eg:.0f} nm)',
            color=color, fontsize=6.5, va='bottom', rotation=90)

    max_alpha = max(max_alpha, (alpha[mask] / 1e4).max())

    # ── Tauc inset ─────────────────────────────────────────────────────
    hnu_t, tauc_val = tauc(energy, alpha, transition='indirect')
    m2 = (energy >= eg * 0.6) & (energy <= eg * 1.6)
    tauc_norm = tauc_val[m2] / tauc_val[m2].max() if tauc_val[m2].max() > 0 else tauc_val[m2]
    ax2.plot(hnu_t[m2], tauc_norm, color=color, lw=1.3, label=label)

    # Linear extrapolation for gap reading
    idx_mid   = np.argmax(tauc_val[m2] > 0.3 * tauc_val[m2].max())
    idx_range = slice(max(0, idx_mid - 10), min(len(tauc_val[m2]), idx_mid + 10))
    if tauc_val[m2][idx_range].std() > 0:
        p = np.polyfit(hnu_t[m2][idx_range], tauc_val[m2][idx_range], 1)
        e_onset = -p[1] / p[0] if p[0] > 0 else eg
        ax2.axvline(e_onset, color=color, lw=0.8, ls='--', alpha=0.6)

# ── Main axes formatting ───────────────────────────────────────────────────
ax.set_xlabel('Photon energy (eV)', fontsize=9)
ax.set_ylabel(r'Absorption coefficient $\alpha$  (10⁴ cm⁻¹)', fontsize=9)
ax.set_xlim(0.5, 6.5)
ax.set_ylim(0, max_alpha * 1.12)

# Visible / UV shading
ax.axvspan(1.77, 3.10, alpha=0.07, color='#FFFF00', zorder=0)
ax.axvspan(3.10, 6.50, alpha=0.05, color='#9B59B6', zorder=0)
ax.text(2.4, max_alpha * 1.04, 'Visible', ha='center',
        fontsize=7, color='#B7950B')
ax.text(4.5, max_alpha * 1.04, 'UV', ha='center',
        fontsize=7, color='#6C3483')

ax.legend(loc='upper left', fontsize=8, framealpha=0.9,
          handlelength=1.5, borderpad=0.6)
ax.yaxis.set_minor_locator(ticker.AutoMinorLocator(2))
ax.xaxis.set_minor_locator(ticker.AutoMinorLocator(2))
ax.tick_params(which='both', direction='in')

# ── Tauc inset formatting ──────────────────────────────────────────────────
ax2.set_xlabel('$h\\nu$ (eV)', fontsize=7)
ax2.set_ylabel(r'$(\alpha h\nu)^{1/2}$ (norm.)', fontsize=7)
ax2.set_title('Tauc plot\n(indirect)', fontsize=7, pad=3)
ax2.tick_params(labelsize=6)
ax2.set_xlim(1.5, 4.5)
ax2.set_ylim(0, 1.1)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.text(0.05, 0.95,
         'Linear extrapolation\n→ $E_g$ intercept',
         transform=ax2.transAxes, fontsize=6, va='top', color='0.5')

fig.suptitle('Optical Absorption Spectra — SnO₂₋ₓ/TiO₂ System',
             fontsize=10, fontweight='bold', y=0.99)

out_dir = os.path.dirname(__file__)
for ext in ('png', 'pdf'):
    path = os.path.join(out_dir, f'fig4_optical_absorption.{ext}')
    fig.savefig(path)
    print(f"Saved: {path}")
plt.close()
