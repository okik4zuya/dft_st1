#!/usr/bin/env python3
"""
band_alignment.py
=================
Core-level band alignment for SnO2-x/TiO2 heterojunction.

Method: O 1s core-level alignment (MacFarlane method)
Reference: Van de Walle & Martin, Phys. Rev. B 35, 8154 (1987)
           Wei & Zunger, Appl. Phys. Lett. 72, 2011 (1998)

Principle:
  - O atoms are present in ALL systems (TiO2, SnO2-x 1:1, SnO2-x 2:1)
  - O 1s core level position is a stable internal reference
  - VBM offset between two materials = difference in (VBM - E_O1s) values
  - Apply correction: VBM_absolute = VBM_DFT + delta_core

Usage:
  1. Run projwfc.x on all systems (pdos inputs already set up)
  2. Read O 1s peak position from each PDOS output
  3. Run this script with the extracted values

Inputs required (fill in after running DFT):
  - Fermi energy (from SCF output)
  - VBM position relative to Fermi level (from bands output)
  - O 1s core level peak position (from PDOS output)
  - Experimental band gap (from Kubelka-Munk)
"""

import sys
import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')            # headless compute node / batch wrapper: never open a window
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

# This script prints Unicode (Δ, μ, subscripts). On a Windows console (cp1252)
# that raises UnicodeEncodeError; force UTF-8 so it runs locally as well as on
# the Linux compute server.
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

# =============================================================================
# SECTION 1: FILL IN AFTER RUNNING DFT
# =============================================================================
# All energies in eV, relative to Fermi level (E_F = 0)
# Read from QE output files as described in comments

data = {
    'TiO2': {
        # From TiO2/scf/TiO2_pristine.scf.out:
        # grep "highest occupied" TiO2_pristine.scf.out
        'VBM_DFT'    : None,    # e.g. -0.02 eV (highest occupied level)

        # From TiO2/bands/TiO2_pristine.bands.out:
        # grep "lowest unoccupied" TiO2_pristine.bands.out
        'CBM_DFT'    : None,    # e.g. 2.08 eV (lowest unoccupied level)

        # From TiO2/dos/TiO2_pristine_pdos.*O*s*:
        # Find the peak of O 1s (lowest energy peak, around -15 to -18 eV)
        # Use: grep maximum or plot the file and read peak position
        'O1s_DFT'    : None,    # e.g. -17.3 eV

        # Experimental band gap
        'Eg_exp'     : 3.00,    # eV — rutile TiO2 experimental value

        'label'      : 'TiO₂',
        'color'      : '#2196F3',    # blue
    },

    'SnO2_pristine': {
        # From pristine/scf/SnO2_pristine.scf.out
        'VBM_DFT'    : None,
        'CBM_DFT'    : None,
        # From pristine/dos/SnO2_pristine_pdos.*O*s*
        'O1s_DFT'    : None,
        'Eg_exp'     : 3.60,    # eV — stoichiometric SnO2
        'label'      : 'SnO₂\n(pristine)',
        'color'      : '#9E9E9E',    # grey
    },

    'SnO2_1to1': {
        # From ratio_1to1/scf/SnO2_1to1.scf.out
        'VBM_DFT'    : None,
        'CBM_DFT'    : None,
        # From ratio_1to1/dos/SnO2_1to1_pdos.*O*s*
        'O1s_DFT'    : None,
        'Eg_exp'     : 2.41,    # eV — from Kubelka-Munk (1:1 sample)
        'label'      : 'SnO₂₋ₓ\n(1:1, 12.5% Vo)',
        'color'      : '#FF9800',    # orange
    },

    'SnO2_2to1': {
        # From ratio_2to1/scf/SnO2_2to1.scf.out
        'VBM_DFT'    : None,
        'CBM_DFT'    : None,
        # From ratio_2to1/dos/SnO2_2to1_pdos.*O*s*
        'O1s_DFT'    : None,
        'Eg_exp'     : 2.21,    # eV — from Kubelka-Munk (2:1 sample)
        'label'      : 'SnO₂₋ₓ\n(2:1, 18.75% Vo)',
        'color'      : '#F44336',    # red
    },
}

# Reference system for alignment (use TiO2 as anchor)
REFERENCE = 'TiO2'

# =============================================================================
# SECTION 2: DATA SOURCE — dft_values.json (preferred) or DEMO fallback
# =============================================================================
# Preferred path: extract_dft_values.py writes dft_values.json; we load real
# VBM_DFT / CBM_DFT / O1s_DFT / Eg_exp from it automatically (no manual paste).
# If that file is absent, fall back to DEMO placeholder values so the script
# still runs and the plot renders (clearly marked as demo).
DEMO_MODE = True   # auto-set to False below if dft_values.json is loaded

_JSON_IN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dft_values.json')
if os.path.exists(_JSON_IN):
    with open(_JSON_IN) as _f:
        _ext = json.load(_f)
    loaded = []
    for _sys in data:
        if _sys in _ext:
            for _k in ('VBM_DFT', 'CBM_DFT', 'O1s_DFT', 'Eg_exp'):
                if _ext[_sys].get(_k) is not None:
                    data[_sys][_k] = _ext[_sys][_k]
            loaded.append(_sys)
    if loaded:
        DEMO_MODE = False
        print("=" * 60)
        print(f"  Loaded real DFT values from {os.path.basename(_JSON_IN)}")
        print(f"  Systems: {', '.join(loaded)}")
        print("=" * 60)

if DEMO_MODE:
    print("=" * 60)
    print("  RUNNING IN DEMO MODE — placeholder values only")
    print("  (dft_values.json not found — run extract_dft_values.py first)")
    print("=" * 60)
    data['TiO2'].update({
        'VBM_DFT': -0.05, 'CBM_DFT': 2.10, 'O1s_DFT': -17.40})
    data['SnO2_pristine'].update({
        'VBM_DFT': -0.03, 'CBM_DFT': 2.55, 'O1s_DFT': -17.80})
    data['SnO2_1to1'].update({
        'VBM_DFT': -0.04, 'CBM_DFT': 1.62, 'O1s_DFT': -17.65})
    data['SnO2_2to1'].update({
        'VBM_DFT': -0.06, 'CBM_DFT': 1.42, 'O1s_DFT': -17.55})

# =============================================================================
# SECTION 3: CORE-LEVEL ALIGNMENT CALCULATION
# =============================================================================

def check_inputs(data):
    """Verify all required values are filled in.

    VBM_DFT + O1s_DFT + Eg_exp are the alignment essentials (fig 5 / fig 2).
    CBM_DFT is OPTIONAL: the near-metallic doped SnO2-x cells print no
    'lowest unoccupied' level, so CBM_DFT is often None. It is only used for
    the DFT gap / scissor shift (optical branch), so a missing CBM_DFT is a
    warning, not a fatal error.
    """
    for system, vals in data.items():
        for key in ['VBM_DFT', 'O1s_DFT']:
            if vals[key] is None:
                raise ValueError(
                    f"Missing value: data['{system}']['{key}']\n"
                    f"Run DFT and fill in the value before proceeding."
                )
        if vals.get('CBM_DFT') is None:
            print(f"  NOTE: {system} has no CBM_DFT (near-metallic) — scissor "
                  f"shift unavailable; alignment uses Eg_exp for CBM.")
        # Eg_exp now drives every CBM position (see core_level_alignment): the
        # mechanism (Type-II / Z / S-scheme) depends on it, so a missing value
        # is fatal, not cosmetic.
        if vals.get('Eg_exp') is None:
            raise ValueError(
                f"Missing Eg_exp for data['{system}'].\n"
                f"CBM_aligned = VBM_aligned + Eg_exp, so the heterojunction "
                f"mechanism cannot be determined without it."
            )
    print("All DFT input values present. Proceeding with alignment.\n")

def core_level_alignment(data, reference):
    """
    Align VBM of all systems to a common absolute scale using O 1s core level.

    For each system:
        delta_core = O1s_ref - O1s_system
        VBM_aligned = VBM_DFT + delta_core
        CBM_aligned = VBM_aligned + Eg_exp
    """
    O1s_ref  = data[reference]['O1s_DFT']
    VBM_ref  = data[reference]['VBM_DFT']

    results = {}
    print(f"Reference system: {reference}")
    print(f"  O 1s (DFT): {O1s_ref:.4f} eV")
    print(f"  VBM  (DFT): {VBM_ref:.4f} eV")
    print()

    for system, vals in data.items():
        delta = O1s_ref - vals['O1s_DFT']   # core-level shift
        VBM_aligned = vals['VBM_DFT'] + delta
        # CBM MUST be built from the EXPERIMENTAL gap, never Eg_DFT: PBEsol
        # underestimates the gap by ~1 eV (and U on Sn 4d does not fix it), which
        # would push every CBM down and can FLIP the mechanism (Type-II vs Z/S).
        # Only the VBM offset (VBM_aligned) is the DFT-derived quantity here.
        CBM_aligned = VBM_aligned + vals['Eg_exp']
        # Eg_DFT / scissor need CBM_DFT, which is absent for near-metallic cells.
        if vals.get('CBM_DFT') is not None:
            Eg_DFT  = vals['CBM_DFT'] - vals['VBM_DFT']
            scissor = vals['Eg_exp'] - Eg_DFT
        else:
            Eg_DFT  = None
            scissor = None

        results[system] = {
            'label'       : vals['label'],
            'color'       : vals['color'],
            'VBM_aligned' : VBM_aligned,
            'CBM_aligned' : CBM_aligned,
            'Eg_exp'      : vals['Eg_exp'],
            'Eg_DFT'      : Eg_DFT,
            'scissor'     : scissor,
            'delta_core'  : delta,
        }

        print(f"System: {system}")
        print(f"  O 1s (DFT)     : {vals['O1s_DFT']:.4f} eV")
        print(f"  Core shift (Δ) : {delta:+.4f} eV")
        print(f"  VBM (aligned)  : {VBM_aligned:.4f} eV")
        print(f"  CBM (aligned)  : {CBM_aligned:.4f} eV")
        print(f"  Eg_DFT (PBE+U) : {Eg_DFT:.4f} eV" if Eg_DFT is not None
              else "  Eg_DFT (PBE+U) : n/a (no CBM_DFT — near-metallic)")
        print(f"  Eg_exp (K-M)   : {vals['Eg_exp']:.4f} eV")
        print(f"  Scissor shift  : {scissor:+.4f} eV  ← use in epsilon.in" if scissor is not None
              else "  Scissor shift  : n/a (needs CBM_DFT)")
        print()

    return results

def identify_mechanism(results):
    """
    Identify heterojunction type from VBM/CBM positions.
    Compares TiO2 and the two SnO2-x systems.
    """
    tio2 = results['TiO2']
    print("=" * 50)
    print("HETEROJUNCTION TYPE ANALYSIS")
    print("=" * 50)
    print("NOTE: VBM offsets are the DFT-derived part (O 1s core alignment).")
    print("      CBM positions rest on the EXPERIMENTAL gap (Eg_exp), not the")
    print("      PBEsol gap. Interpret the mechanism on that basis.")

    for key in ['SnO2_1to1', 'SnO2_2to1']:
        sno2 = results[key]
        label = sno2['label'].replace('\n', ' ')

        VBM_offset = sno2['VBM_aligned'] - tio2['VBM_aligned']
        CBM_offset = sno2['CBM_aligned'] - tio2['CBM_aligned']

        print(f"\nTiO₂ vs {label}:")
        print(f"  ΔVBM (SnO2-x minus TiO2) : {VBM_offset:+.4f} eV")
        print(f"  ΔCBM (SnO2-x minus TiO2) : {CBM_offset:+.4f} eV")

        # Classification
        same_sign = (VBM_offset > 0) == (CBM_offset > 0)

        if same_sign and abs(VBM_offset) > 0.1 and abs(CBM_offset) > 0.1:
            mech = "Type-II (staggered gap)"
            detail = ("Electrons → lower CBM (SnO₂₋ₓ side)\n"
                      "  Holes    → higher VBM (TiO₂ side)" if CBM_offset < 0
                      else "Electrons → lower CBM (TiO₂ side)\n"
                           "  Holes    → higher VBM (SnO₂₋ₓ side)")
        elif not same_sign:
            mech = "Z-scheme or S-scheme (straddling/broken gap)"
            detail = "VBM and CBM offsets have opposite signs → charge recombines at interface"
        else:
            mech = "Type-I (straddling gap) — check values"
            detail = "Both VBM and CBM offsets very small — near flat-band condition"

        print(f"  → Mechanism: {mech}")
        print(f"     {detail}")

    print()

# =============================================================================
# SECTION 4: ENERGY DIAGRAM FIGURE
# =============================================================================

def plot_energy_diagram(results, save_path='energy_diagram.png'):
    """
    Publication-quality energy diagram showing VBM/CBM positions
    of all four systems on the same absolute energy scale.
    """
    fig, ax = plt.subplots(figsize=(10, 7))

    systems   = list(results.keys())
    x_centers = np.arange(len(systems))
    bar_width  = 0.55
    bar_gap    = 0.05   # gap between VBM top and label

    ref_VBM = results['TiO2']['VBM_aligned']   # set TiO2 VBM as visual anchor

    for i, (sys, res) in enumerate(results.items()):
        VBM = res['VBM_aligned'] - ref_VBM    # shift so TiO2 VBM = 0
        CBM = res['CBM_aligned'] - ref_VBM
        color = res['color']
        x = x_centers[i]

        # Draw VBM bar (valence band region, filled downward)
        ax.fill_betweenx([VBM - 2.5, VBM], x - bar_width/2, x + bar_width/2,
                         color=color, alpha=0.25, linewidth=0)
        ax.hlines(VBM, x - bar_width/2, x + bar_width/2,
                  colors=color, linewidths=2.5)

        # Draw CBM bar (conduction band region, filled upward)
        ax.fill_betweenx([CBM, CBM + 1.5], x - bar_width/2, x + bar_width/2,
                         color=color, alpha=0.25, linewidth=0)
        ax.hlines(CBM, x - bar_width/2, x + bar_width/2,
                  colors=color, linewidths=2.5)

        # Band gap labels inside the gap
        mid_gap = (VBM + CBM) / 2
        ax.text(x, mid_gap, f'Eg = {res["Eg_exp"]:.2f} eV',
                ha='center', va='center', fontsize=9,
                color=color, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                          edgecolor=color, alpha=0.8))

        # VBM value label
        ax.text(x, VBM - bar_gap, f'{VBM:.2f} eV',
                ha='center', va='top', fontsize=8, color=color)

        # CBM value label
        ax.text(x, CBM + bar_gap, f'{CBM:.2f} eV',
                ha='center', va='bottom', fontsize=8, color=color)

    # Draw charge transfer arrows for the mechanism
    # (will update automatically once real values are filled in)
    tio2_x  = x_centers[0]
    sno2_1x = x_centers[2]
    sno2_2x = x_centers[3]
    tio2_res  = list(results.values())[0]
    sno2_1res = list(results.values())[2]
    sno2_2res = list(results.values())[3]

    for sno2_x, sno2_res in [(sno2_1x, sno2_1res), (sno2_2x, sno2_2res)]:
        VBM_tio2 = tio2_res['VBM_aligned']  - ref_VBM
        CBM_tio2 = tio2_res['CBM_aligned']  - ref_VBM
        VBM_sno2 = sno2_res['VBM_aligned']  - ref_VBM
        CBM_sno2 = sno2_res['CBM_aligned']  - ref_VBM

        # Electron transfer arrow (CBM to CBM)
        ax.annotate('', xy=(tio2_x + bar_width/2, CBM_tio2),
                    xytext=(sno2_x - bar_width/2, CBM_sno2),
                    arrowprops=dict(arrowstyle='->', color='blue',
                                   lw=1.5, linestyle='dashed'))

        # Hole transfer arrow (VBM to VBM)
        ax.annotate('', xy=(tio2_x + bar_width/2, VBM_tio2),
                    xytext=(sno2_x - bar_width/2, VBM_sno2),
                    arrowprops=dict(arrowstyle='->', color='red',
                                   lw=1.5, linestyle='dashed'))

    # Formatting
    ax.set_xticks(x_centers)
    ax.set_xticklabels(
        [r['label'] for r in results.values()],
        fontsize=11, multialignment='center'
    )
    ax.set_ylabel('Energy (eV, relative to TiO₂ VBM)', fontsize=12)
    ax.set_title('DFT Band Alignment — SnO₂₋ₓ/TiO₂ Heterojunction\n'
                 '(Core-level O 1s alignment method)', fontsize=13)

    # Legend
    e_patch = mpatches.Patch(color='blue', label='Electron transfer (CB → CB)')
    h_patch = mpatches.Patch(color='red',  label='Hole transfer (VB → VB)')
    ax.legend(handles=[e_patch, h_patch], loc='upper right', fontsize=10)

    ax.set_xlim(-0.6, len(systems) - 0.4)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Energy diagram saved to: {save_path}")
    plt.show()

# =============================================================================
# SECTION 5: SCISSOR SHIFT SUMMARY TABLE
# =============================================================================

def print_scissor_table(results):
    """Print the scissor shifts to fill into epsilon.in files."""
    print("=" * 60)
    print("SCISSOR SHIFTS FOR epsilon.in FILES")
    print("=" * 60)
    print(f"{'System':<20} {'Eg_DFT':>10} {'Eg_exp':>10} {'shift':>10}")
    print("-" * 55)
    mapping = {
        'TiO2'           : 'TiO2/optical/TiO2_pristine.epsilon.in',
        'SnO2_pristine'  : 'pristine/optical/SnO2_pristine.epsilon.in',
        'SnO2_1to1'      : 'ratio_1to1/optical/SnO2_1to1.epsilon.in',
        'SnO2_2to1'      : 'ratio_2to1/optical/SnO2_2to1.epsilon.in',
    }
    for sys, res in results.items():
        if res['scissor'] is None:
            print(f"  {sys:<18} {'n/a':>9} {res['Eg_exp']:>9.3f} "
                  f"  {'n/a (no CBM_DFT)':>12}")
        else:
            print(f"  {sys:<18} {res['Eg_DFT']:>9.3f} {res['Eg_exp']:>9.3f} "
                  f"  {res['scissor']:>+8.3f} eV")
    print()
    print("Action: open each epsilon.in and set  shift = <value above>")
    print()
    for sys, path in mapping.items():
        sc = results[sys]['scissor']
        print(f"  {path}")
        print(f"    shift = {sc:+.4f}" if sc is not None else "    shift = n/a (near-metallic, no CBM_DFT)")
    print()


def write_alignment_json(results, path='band_alignment.json'):
    """Emit machine-readable alignment consumed by fig2 (core shift) and
    fig5 (aligned VBM/CBM). Absolute VBM_aligned/CBM_aligned; figs rescale to
    the TiO2 = 0 reference themselves."""
    out = {}
    for sys, res in results.items():
        out[sys] = {
            'VBM_aligned' : res['VBM_aligned'],
            'CBM_aligned' : res['CBM_aligned'],
            'delta_core'  : res['delta_core'],
            'scissor'     : res['scissor'],
            'Eg_exp'      : res['Eg_exp'],
            'Eg_DFT'      : res['Eg_DFT'],
        }
    with open(path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f"Alignment written to: {path}  (consumed by fig2 + fig5)")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    check_inputs(data)
    results = core_level_alignment(data, reference=REFERENCE)
    identify_mechanism(results)
    print_scissor_table(results)
    write_alignment_json(results, path='band_alignment.json')
    plot_energy_diagram(results, save_path='energy_diagram.png')
