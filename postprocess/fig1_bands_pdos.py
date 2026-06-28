#!/usr/bin/env python3
"""
fig1_bands_pdos.py
==================
Figure 1 — Band structure + PDOS panel for:
  Left column  : SnO₂₋ₓ 1:1  (12.5% Vo, Eg = 2.41 eV)
  Right column : SnO₂₋ₓ 2:1  (18.75% Vo, Eg = 2.21 eV)

Each column: [band structure | PDOS] sharing the energy y-axis.

Layout (double-column, 17.8 cm wide):
  ┌────────────────┬────────────────┐
  │  bands  │ DOS │  bands  │ DOS  │
  │  1:1        │  2:1             │
  └────────────────┴────────────────┘

Output: fig1_bands_pdos.png / .pdf
"""

import sys, os, glob
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

sys.path.insert(0, os.path.dirname(__file__))
from plot_config import (apply_style, COLORS, LABELS, EG_EXP,
                         DOUBLE_COL, cm2in, add_fermi_line, shade_gap)

apply_style()

# ── paths ──────────────────────────────────────────────────────────────────
BASE = os.path.join(os.path.dirname(__file__), '..')

SYSTEMS = {
    '1to1': {
        'bands_dat' : f'{BASE}/ratio_1to1/bands/SnO2_1to1_bands.dat',
        'pdos_glob' : f'{BASE}/ratio_1to1/dos/SnO2_1to1_pdos.pdos_atm*',
        'scf_out'   : f'{BASE}/ratio_1to1/scf/SnO2_1to1.scf.out',
        'color'     : COLORS['SnO2_1to1'],
        'label'     : 'SnO₂₋ₓ  1:1  (Vo = 12.5%)',
        'eg_exp'    : EG_EXP['SnO2_1to1'],
    },
    '2to1': {
        'bands_dat' : f'{BASE}/ratio_2to1/bands/SnO2_2to1_bands.dat',
        'pdos_glob' : f'{BASE}/ratio_2to1/dos/SnO2_2to1_pdos.pdos_atm*',
        'scf_out'   : f'{BASE}/ratio_2to1/scf/SnO2_2to1.scf.out',
        'color'     : COLORS['SnO2_2to1'],
        'label'     : 'SnO₂₋ₓ  2:1  (Vo = 18.75%)',
        'eg_exp'    : EG_EXP['SnO2_2to1'],
    },
}

E_MIN, E_MAX = -6.0, 4.0    # eV window around Fermi level

# ── readers ────────────────────────────────────────────────────────────────

def read_fermi(scf_out):
    """Extract Fermi energy from SCF output."""
    import re
    if not os.path.exists(scf_out):
        return 0.0
    with open(scf_out) as f:
        txt = f.read()
    m = re.search(r'the Fermi energy is\s+([-\d.]+)', txt, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r'highest occupied.*?level.*?:\s+([-\d.]+)', txt, re.I)
    return float(m.group(1)) if m else 0.0


def read_bands(bands_dat, fermi):
    """
    Parse bands.x output (bands.dat).
    Returns: list of numpy arrays, one per spin channel.
             Each array shape = (n_kpoints, n_bands).
    k_coords: 1-D array of cumulative k distances.
    high_sym_k: list of (k_coord, label) for high-symmetry points.
    """
    if not os.path.exists(bands_dat):
        print(f"  WARNING: {bands_dat} not found — using demo sine waves")
        return None, None, None

    with open(bands_dat) as f:
        lines = f.readlines()

    # Find header line: &plot ... /
    data_lines = []
    header_done = False
    nks, nbnd = 0, 0
    for line in lines:
        s = line.strip()
        if s.startswith('&plot'):
            continue
        if not header_done:
            if 'nbnd' in s.lower():
                import re
                m = re.search(r'nbnd\s*=\s*(\d+)', s)
                if m:
                    nbnd = int(m.group(1))
            if 'nks' in s.lower():
                import re
                m = re.search(r'nks\s*=\s*(\d+)', s)
                if m:
                    nks = int(m.group(1))
            if s == '/':
                header_done = True
            continue
        data_lines.append(s)

    # Parse k-path and eigenvalues
    k_coords  = []
    all_bands = []
    current_bands = []
    current_k = None

    i = 0
    flat = []
    for dl in data_lines:
        flat.extend(dl.split())

    # bands.dat format: k_x k_y k_z  then eigenvalues in rows of 10
    idx = 0
    kpts = []
    bands_all = []
    while idx < len(flat):
        try:
            kx, ky, kz = float(flat[idx]), float(flat[idx+1]), float(flat[idx+2])
        except (ValueError, IndexError):
            break
        idx += 3
        kpts.append([kx, ky, kz])
        eigs = []
        while len(eigs) < nbnd and idx < len(flat):
            try:
                eigs.append(float(flat[idx]))
                idx += 1
            except ValueError:
                break
        bands_all.append(eigs)

    if not kpts:
        print(f"  WARNING: Could not parse {bands_dat}")
        return None, None, None

    kpts = np.array(kpts)
    bands_arr = np.array(bands_all)   # shape: (nks, nbnd)

    # Compute cumulative k distance
    dk = np.zeros(len(kpts))
    for i in range(1, len(kpts)):
        dk[i] = dk[i-1] + np.linalg.norm(kpts[i] - kpts[i-1])

    # Shift to Fermi level
    bands_arr -= fermi

    return dk, bands_arr, kpts


def read_pdos(pdos_glob, fermi, species_map):
    """
    Read projected DOS files and return dict of {channel_name: (energy, dos)}.
    species_map: dict mapping filename substrings to channel labels.
    e.g. {'(Sn)_wfc#1(s)': 'Sn 5s', '(Sn)_wfc#2(d)': 'Sn 4d', '(O)_wfc#2(p)': 'O 2p'}
    """
    files = glob.glob(pdos_glob)
    channels = {}

    for f in files:
        fname = os.path.basename(f)
        matched_label = None
        for key, label in species_map.items():
            if key in fname:
                matched_label = label
                break
        if matched_label is None:
            continue

        try:
            raw = np.loadtxt(f, comments='#')
            if raw.ndim == 1:
                raw = raw.reshape(1, -1)
            energy = raw[:, 0] - fermi

            if raw.shape[1] >= 3:
                # spin-polarised
                dos_up = raw[:, 1]
                dos_dn = raw[:, 2]
            else:
                dos_up = raw[:, 1]
                dos_dn = None

            if matched_label not in channels:
                channels[matched_label] = {
                    'energy': energy, 'up': dos_up,
                    'dn': dos_dn if dos_dn is not None else np.zeros_like(dos_up)
                }
            else:
                # accumulate across atoms
                channels[matched_label]['up'] += dos_up
                if dos_dn is not None:
                    channels[matched_label]['dn'] += dos_dn

        except Exception as e:
            print(f"  WARNING: Could not read {f}: {e}")

    return channels

# ── demo data (used if real files absent) ──────────────────────────────────

def make_demo_bands(eg, n_kpts=180, n_bands=12):
    """Physically plausible demo band structure for SnO2-x."""
    k = np.linspace(0, 1, n_kpts)
    bands = []
    # Valence bands
    for i in range(8):
        base  = -5.5 + i * 0.7
        disp  = 0.4 * np.cos(np.pi * k) * (1 - 0.2 * i)
        bands.append(base + disp)
    # Vo in-gap state
    bands.append(-eg + 0.35 + 0.05 * np.sin(2 * np.pi * k))
    # CBM and higher
    for i in range(3):
        base = 0.15 + i * 0.6
        disp = 0.5 * np.cos(np.pi * k) * (-1) ** i
        bands.append(base + disp)
    return k, np.array(bands).T   # (nk, nbands)


def make_demo_pdos(eg):
    """Demo PDOS for SnO2-x."""
    e = np.linspace(-7, 4, 1000)
    def gauss(c, w, h): return h * np.exp(-((e - c) / w) ** 2)
    sn5s = gauss(-eg + 0.35, 0.15, 2.0) + gauss(1.5, 0.5, 0.3)
    sn4d = gauss(-5.0, 0.5, 3.0) + gauss(-eg + 0.35, 0.2, 1.0)
    o2p  = (gauss(-3.5, 1.2, 4.0) + gauss(-1.5, 0.8, 3.0)
            + gauss(-5.5, 0.4, 1.5))
    return e, {'Sn 5s': sn5s, 'Sn 4d': sn4d, 'O 2p': o2p}

# ── plotting ───────────────────────────────────────────────────────────────

SPECIES_MAP = {
    '(Sn)_wfc#1(s)' : 'Sn 5s',
    '(Sn)_wfc#2(d)' : 'Sn 4d',
    '(O)_wfc#2(p)'  : 'O 2p',
}

PDOS_STYLE = {
    'Sn 5s' : dict(color=COLORS['Sn_5s'], lw=1.4, label='Sn 5s'),
    'Sn 4d' : dict(color=COLORS['Sn_4d'], lw=1.4, label='Sn 4d'),
    'O 2p'  : dict(color=COLORS['O_2p'],  lw=1.4, label='O 2p'),
}


def plot_system(axes_bands, axes_pdos, key, cfg, panel_letter):
    """Plot one [bands | PDOS] column."""
    eg    = cfg['eg_exp']
    color = cfg['color']
    fermi = read_fermi(cfg['scf_out'])

    # ── Band structure ──────────────────────────────────────────────────
    ax = axes_bands
    k_coord, bands_arr, _ = read_bands(cfg['bands_dat'], fermi)

    if bands_arr is None:
        print(f"  Using DEMO band data for {key}")
        k_coord, bands_arr = make_demo_bands(eg)

    for b in range(bands_arr.shape[1]):
        ax.plot(k_coord, bands_arr[:, b], color=color, lw=0.8, alpha=0.75)

    # Highlight Vo state (band closest to -eg + 0.3 window)
    vo_target = -eg + 0.35
    if bands_arr is not None:
        mean_e = bands_arr.mean(axis=0)
        mask   = (mean_e > -eg + 0.1) & (mean_e < -0.05)
        if mask.any():
            for bi in np.where(mask)[0]:
                ax.plot(k_coord, bands_arr[:, bi],
                        color=COLORS['Vo_state'], lw=1.5, zorder=5)

    add_fermi_line(ax, orientation='h', label='$E_F$')
    shade_gap(ax, -eg, 0, orientation='h', alpha=0.07, color='grey')

    # Mark Eg
    ax.annotate('', xy=(k_coord[-1] * 0.95, 0),
                xytext=(k_coord[-1] * 0.95, -eg),
                arrowprops=dict(arrowstyle='<->', color='black', lw=0.9))
    ax.text(k_coord[-1] * 0.95, -eg / 2,
            f'$E_g$={eg:.2f} eV', ha='right', va='center',
            fontsize=7, color='black',
            bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none'))

    ax.set_xlim(k_coord[0], k_coord[-1])
    ax.set_ylim(E_MIN, E_MAX)
    ax.set_ylabel('Energy relative to $E_F$ (eV)', fontsize=8)
    ax.set_xlabel('Wave vector $k$', fontsize=8)
    ax.set_xticks([])
    ax.set_title(f'({panel_letter}) {cfg["label"]}', fontsize=9,
                 fontweight='bold', pad=6)

    # ── PDOS ────────────────────────────────────────────────────────────
    ax2 = axes_pdos
    channels = read_pdos(cfg['pdos_glob'], fermi, SPECIES_MAP)

    if not channels:
        print(f"  Using DEMO PDOS for {key}")
        e_demo, pdos_demo = make_demo_pdos(eg)
        channels = {k: {'energy': e_demo, 'up': v, 'dn': np.zeros_like(v)}
                    for k, v in pdos_demo.items()}

    max_dos = 0
    for ch, style in PDOS_STYLE.items():
        if ch not in channels:
            continue
        e   = channels[ch]['energy']
        dos = channels[ch]['up'] + channels[ch]['dn']
        mask = (e >= E_MIN) & (e <= E_MAX)
        ax2.plot(dos[mask], e[mask], **style, zorder=3)
        ax2.fill_betweenx(e[mask], 0, dos[mask],
                          alpha=0.12, color=style['color'], zorder=2)
        max_dos = max(max_dos, dos[mask].max())

    # Shade Vo state region
    ax2.axhspan(-eg + 0.05, -0.05, alpha=0.08,
                color=COLORS['Vo_state'], label='Vo defect band', zorder=1)

    add_fermi_line(ax2, orientation='h', label=None)
    shade_gap(ax2, -eg, 0, orientation='h', alpha=0.07, color='grey')
    ax2.set_ylim(E_MIN, E_MAX)
    ax2.set_xlim(0, max_dos * 1.15 if max_dos > 0 else 10)
    ax2.set_xlabel('PDOS (states/eV)', fontsize=8)
    ax2.set_yticklabels([])
    ax2.legend(loc='upper right', fontsize=7, handlelength=1.2)


# ── figure assembly ────────────────────────────────────────────────────────

fig = plt.figure(figsize=(DOUBLE_COL, cm2in(12)))

# 4 panels: [bands_1to1 | pdos_1to1 | bands_2to1 | pdos_2to1]
gs = fig.add_gridspec(1, 4, width_ratios=[2, 1, 2, 1],
                      wspace=0.08, left=0.09, right=0.97,
                      top=0.93, bottom=0.12)

ax_b1 = fig.add_subplot(gs[0])
ax_d1 = fig.add_subplot(gs[1])
ax_b2 = fig.add_subplot(gs[2])
ax_d2 = fig.add_subplot(gs[3])

# Share y-axis within each pair
ax_d1.sharey(ax_b1)
ax_d2.sharey(ax_b2)

plot_system(ax_b1, ax_d1, '1to1', SYSTEMS['1to1'], 'a')
plot_system(ax_b2, ax_d2, '2to1', SYSTEMS['2to1'], 'b')

# Remove duplicate y-label on right column
ax_b2.set_ylabel('')

# Vertical separator between the two systems
fig.add_artist(plt.Line2D([0.505, 0.505], [0.08, 0.97],
                           transform=fig.transFigure,
                           color='0.7', lw=0.8, ls='--'))

out_dir = os.path.dirname(__file__)
for ext in ('png', 'pdf'):
    path = os.path.join(out_dir, f'fig1_bands_pdos.{ext}')
    fig.savefig(path)
    print(f"Saved: {path}")
plt.close()
