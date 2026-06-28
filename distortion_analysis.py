#!/usr/bin/env python3
"""
distortion_analysis.py
======================
Quantifies the lattice distortion caused by self-doping (oxygen vacancies) and
correlates it with the band gap. This turns the "self-doping distorts the lattice
-> gap narrows" narrative into a quantitative, reviewer-defensible result.

For pristine / 1:1 / 2:1 it reads the relaxed structure from each vc-relax output
and computes:
  * cell response          : a, b, c, V and their change vs pristine
  * Sn-O bond statistics    : mean, std, min, max (minimum-image, < CUTOFF)
  * per-Sn coordination     : number of O neighbours (drops where Vo removes one)
  * octahedral distortion   : bond-length distortion index Delta, averaged over Sn

It then reads the band gaps from dft_extracted_values.txt (written by
extract_dft_values.py) if present, and plots a distortion metric vs gap / Vo%.

Reuses the parser and cell-inverse from update_geometry.py — no geometry-parsing
logic is re-implemented here.

Usage:
    python distortion_analysis.py
"""

import os
import sys
import math

# --- Reuse the vetted geometry parser from update_geometry --------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from update_geometry import parse_final_structure   # noqa: E402

CUTOFF = 2.6     # Angstrom; rutile Sn-O bonds are ~1.95-2.06, so 2.6 captures the
                 # full octahedron while excluding second-neighbour O.
CATION = "Sn"
ANION = "O"

# (label, relax output, nominal Vo%) — pristine first as the reference.
SYSTEMS = [
    ("pristine", "pristine/relax/SnO2_pristine.relax.out", 0.0),
    ("1:1",      "ratio_1to1/relax/SnO2_1to1.relax.out",  12.50),
    ("2:1",      "ratio_2to1/relax/SnO2_2to1.relax.out",  18.75),
]

EXTRACTED_VALUES = "dft_extracted_values.txt"


# -----------------------------------------------------------------------------
# Geometry helpers
# -----------------------------------------------------------------------------
def neighbour_dists(cell, cp, anions, cutoff):
    """
    All cation-anion distances < cutoff, enumerating periodic images (n in -1..1).

    NOTE: a single minimum-image distance per atom is NOT enough here — the
    supercell is only one rutile repeat along c (c = 3.186 A), so the same O atom
    coordinates the cation through two different images. Enumerating images is
    required to recover the correct 6-fold (octahedral) coordination; plain MIC
    would undercount it as 4.
    """
    A = cell
    out = []
    for ap in anions:
        bx, by, bz = (ap[0] - cp[0], ap[1] - cp[1], ap[2] - cp[2])
        for n1 in (-1, 0, 1):
            for n2 in (-1, 0, 1):
                for n3 in (-1, 0, 1):
                    dx = bx + n1 * A[0][0] + n2 * A[1][0] + n3 * A[2][0]
                    dy = by + n1 * A[0][1] + n2 * A[1][1] + n3 * A[2][1]
                    dz = bz + n1 * A[0][2] + n2 * A[1][2] + n3 * A[2][2]
                    r = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if 0.1 < r < cutoff:
                        out.append(r)
    return out


def cell_params(cell):
    """Return (a, b, c, volume) from lattice-vector rows."""
    def norm(v):
        return math.sqrt(sum(x * x for x in v))
    a, b, c = (norm(cell[0]), norm(cell[1]), norm(cell[2]))
    # volume = a1 . (a2 x a3)
    a1, a2, a3 = cell
    cross = (a2[1] * a3[2] - a2[2] * a3[1],
             a2[2] * a3[0] - a2[0] * a3[2],
             a2[0] * a3[1] - a2[1] * a3[0])
    vol = abs(a1[0] * cross[0] + a1[1] * cross[1] + a1[2] * cross[2])
    return a, b, c, vol


def analyse(cell, atoms):
    """Compute bond / coordination / distortion metrics for one structure."""
    cations = [(x, y, z) for (s, x, y, z) in atoms if s == CATION]
    anions  = [(x, y, z) for (s, x, y, z) in atoms if s == ANION]

    all_bonds = []
    coord_numbers = []
    distortion_indices = []   # per-cation bond-length distortion index

    for cp in cations:
        bonds = sorted(neighbour_dists(cell, cp, anions, CUTOFF))
        coord_numbers.append(len(bonds))
        all_bonds.extend(bonds)
        if bonds:
            dmean = sum(bonds) / len(bonds)
            di = sum(((d - dmean) / dmean) ** 2 for d in bonds) / len(bonds)
            distortion_indices.append(di)

    a, b, c, vol = cell_params(cell)
    n = len(all_bonds)
    bmean = sum(all_bonds) / n if n else float("nan")
    bstd = math.sqrt(sum((d - bmean) ** 2 for d in all_bonds) / n) if n else float("nan")

    return {
        "a": a, "b": b, "c": c, "vol": vol,
        "n_cation": len(cations), "n_anion": len(anions),
        "bond_mean": bmean, "bond_std": bstd,
        "bond_min": min(all_bonds) if all_bonds else float("nan"),
        "bond_max": max(all_bonds) if all_bonds else float("nan"),
        "coord_mean": sum(coord_numbers) / len(coord_numbers) if coord_numbers else float("nan"),
        "coord_numbers": coord_numbers,
        "distortion_index": (sum(distortion_indices) / len(distortion_indices)
                             if distortion_indices else float("nan")),
    }


# -----------------------------------------------------------------------------
# Gap lookup (optional) from extract_dft_values.py output
# -----------------------------------------------------------------------------
def load_gaps(path):
    """Parse dft_extracted_values.txt -> {system_key: Eg or None}. Best-effort."""
    gaps = {}
    if not os.path.exists(path):
        return gaps
    cur = None
    vbm = cbm = None
    with open(path) as f:
        for line in f:
            line = line.rstrip()
            if line.startswith("[") and line.endswith("]"):
                if cur and vbm is not None and cbm is not None:
                    gaps[cur] = cbm - vbm
                cur, vbm, cbm = line[1:-1], None, None
            elif "VBM_DFT" in line:
                vbm = _safe_float(line.split("=")[-1])
            elif "CBM_DFT" in line:
                cbm = _safe_float(line.split("=")[-1])
        if cur and vbm is not None and cbm is not None:
            gaps[cur] = cbm - vbm
    return gaps


def _safe_float(s):
    try:
        return float(s.strip())
    except (ValueError, AttributeError):
        return None


# label in SYSTEMS -> key used in dft_extracted_values.txt
GAP_KEY = {"pristine": "SnO2_pristine", "1:1": "SnO2_1to1", "2:1": "SnO2_2to1"}


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("  LATTICE DISTORTION ANALYSIS  (self-doping -> distortion -> gap)")
    print("=" * 70)

    results = {}
    ref = None
    for label, relpath, vo in SYSTEMS:
        path = os.path.join(".", relpath)
        if not os.path.exists(path):
            print(f"\n[{label}] relax output not found: {relpath} (skipped)")
            continue
        parsed = parse_final_structure(path)
        if parsed is None:
            print(f"\n[{label}] no converged final coordinates in {relpath} (skipped)")
            continue
        _, cell, _, atoms = parsed
        m = analyse(cell, atoms)
        m["Vo%"] = vo
        results[label] = m
        if label == "pristine":
            ref = m

        print(f"\n[{label}]  Vo = {vo:.2f}%   ({m['n_cation']} Sn, {m['n_anion']} O)")
        print(f"  cell a/b/c (A)      : {m['a']:.4f} / {m['b']:.4f} / {m['c']:.4f}")
        print(f"  volume (A^3)        : {m['vol']:.3f}")
        if ref and label != "pristine":
            da = 100 * (m['a'] - ref['a']) / ref['a']
            dc = 100 * (m['c'] - ref['c']) / ref['c']
            dv = 100 * (m['vol'] - ref['vol']) / ref['vol']
            print(f"  vs pristine         : da={da:+.2f}%  dc={dc:+.2f}%  dV={dv:+.2f}%")
        print(f"  Sn-O bond mean/std  : {m['bond_mean']:.4f} / {m['bond_std']:.4f} A")
        print(f"  Sn-O bond min/max   : {m['bond_min']:.4f} / {m['bond_max']:.4f} A")
        print(f"  mean coordination   : {m['coord_mean']:.3f} O per Sn")
        print(f"  octahedral distort. : {m['distortion_index']:.3e}")

    if not results:
        print("\nNo relaxed structures available yet — run PHASE 1 (vc-relax) first.")
        return

    # --- write summary table -------------------------------------------------
    gaps = load_gaps(EXTRACTED_VALUES)
    out_txt = "distortion_metrics.txt"
    with open(out_txt, "w") as f:
        f.write("# Lattice distortion metrics — SnO2-x\n")
        f.write(f"# bond cutoff = {CUTOFF} A\n")
        hdr = ("system", "Vo%", "a", "c", "V", "bond_mean", "bond_std",
               "coord", "distort_idx", "Eg_DFT")
        f.write("{:<9}{:>7}{:>9}{:>9}{:>10}{:>11}{:>10}{:>8}{:>13}{:>9}\n".format(*hdr))
        for label, m in results.items():
            eg = gaps.get(GAP_KEY.get(label, ""), None)
            eg_txt = f"{eg:.3f}" if isinstance(eg, float) else "n/a"
            f.write("{:<9}{:>7.2f}{:>9.4f}{:>9.4f}{:>10.3f}{:>11.4f}{:>10.4f}"
                    "{:>8.2f}{:>13.3e}{:>9}\n".format(
                        label, m["Vo%"], m["a"], m["c"], m["vol"],
                        m["bond_mean"], m["bond_std"], m["coord_mean"],
                        m["distortion_index"], eg_txt))
    print(f"\nSummary written to: {out_txt}")

    # --- plot distortion vs gap / Vo% ---------------------------------------
    _plot(results, gaps)


def _plot(results, gaps):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available — skipping plot.")
        return

    labels = list(results.keys())
    vo   = [results[l]["Vo%"] for l in labels]
    dist = [results[l]["distortion_index"] for l in labels]
    egs  = [gaps.get(GAP_KEY.get(l, ""), None) for l in labels]
    have_gap = all(isinstance(e, float) for e in egs)

    fig, ax1 = plt.subplots(figsize=(7, 5))
    color1 = "#F44336"
    ax1.plot(vo, dist, "o-", color=color1, lw=2, label="octahedral distortion")
    ax1.set_xlabel("Oxygen vacancy concentration (%)")
    ax1.set_ylabel("SnO$_6$ distortion index", color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)
    for x, y, l in zip(vo, dist, labels):
        ax1.annotate(l, (x, y), textcoords="offset points", xytext=(6, 6), fontsize=9)

    if have_gap:
        ax2 = ax1.twinx()
        color2 = "#2196F3"
        ax2.plot(vo, egs, "s--", color=color2, lw=2, label="Eg (DFT)")
        ax2.set_ylabel("Band gap Eg$_{DFT}$ (eV)", color=color2)
        ax2.tick_params(axis="y", labelcolor=color2)
    else:
        print("  (gaps not available in dft_extracted_values.txt — plotting "
              "distortion vs Vo% only)")

    ax1.set_title("Self-doping: lattice distortion vs band gap")
    fig.tight_layout()
    out_png = "distortion_vs_gap.png"
    fig.savefig(out_png, dpi=300)
    print(f"Plot written to: {out_png}")


if __name__ == "__main__":
    main()
