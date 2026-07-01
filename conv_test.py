#!/usr/bin/env python3
"""
conv_test.py — one-time k-mesh + plane-wave cutoff convergence tests.

Derives single-point SCF inputs from each system's production `relax.in`,
varying ONE parameter at a time (ecutwfc, or the k-mesh) while holding
everything else — geometry, HUBBARD +U, nspin, smearing — identical to the
production run. Each job prints total energy, total force and pressure, which
are exactly the quantities that drive a vc-relax, so the coarsest setting that
converges them is a defensible choice for the relaxation stage.

Usage
-----
    python conv_test.py gen                # write <sys>/conv/*.scf.in
    python conv_test.py analyze            # tabulate <sys>/conv/*.scf.out

Design
------
  * ecutwfc sweep:  ecut in {40,50,60,70} at the production k-mesh (ecutrho=8*ecut)
  * k-mesh  sweep:  k in {2x2x4, 3x3x6, 4x4x8, 6x6x12} at ecutwfc=60
  * the shared (ecut=60, production mesh) point is generated once.

The relax mesh only has to converge FORCES and PRESSURE (not the fine detail of
the DOS), so the recommended relax setting is the coarsest mesh whose pressure
and energy/atom sit within the production thresholds of the dense reference.
"""

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# system dir -> (prefix, relax input filename under <sys>/relax/)
SYSTEMS = {
    "pristine":   ("SnO2_pristine", "SnO2_pristine.relax.in"),
    "ratio_1to1": ("SnO2_1to1",     "SnO2_1to1.relax.in"),
    "ratio_2to1": ("SnO2_2to1",     "SnO2_2to1.relax.in"),
    "TiO2":       ("TiO2_pristine", "TiO2_pristine.relax.in"),
}

ECUT_LIST = [40, 50, 60, 70]                 # Ry; ecutrho = 8 * ecutwfc (PAW)
KPTS_LIST = ["2 2 4", "3 3 6", "4 4 8", "6 6 12"]
BASE_ECUT = 60                               # Ry, held fixed for the k-mesh sweep
RHO_RATIO = 8                                # ecutrho / ecutwfc for these PAW pseudos

# Convergence tolerances used only to FLAG a recommendation in `analyze`.
TOL_E_MEV_PER_ATOM = 1.0                     # meV/atom vs dense reference
TOL_P_KBAR = 0.5                             # kbar  (= production press_conv_thr)
TOL_F_RY_BOHR = 1.0e-4                       # Ry/Bohr (= production forc_conv_thr)

RY_TO_EV = 13.605693122994


# --------------------------------------------------------------------------- #
# input-file parsing / rewriting
# --------------------------------------------------------------------------- #
def _split_namelists_cards(text):
    """Return (namelist_text, cards_text). Cards start at the first card keyword."""
    lines = text.splitlines()
    # Card headers are bare keywords (no '='); this guard keeps namelist keys
    # like `occupations = 'smearing'` from being mistaken for the ATOMIC_*/... cards.
    card_kw = ("ATOMIC_SPECIES", "ATOMIC_POSITIONS", "CELL_PARAMETERS",
               "K_POINTS", "HUBBARD", "OCCUPATIONS", "CONSTRAINTS",
               "ATOMIC_VELOCITIES", "ATOMIC_FORCES")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if "=" in s:
            continue
        tok = s.upper().split()[:1]
        if tok and tok[0] in card_kw:
            return "\n".join(lines[:i]), "\n".join(lines[i:])
    return text, ""


def _parse_namelists(nl_text):
    """Parse '&NAME ... /' blocks into {name_lower: {key: value}} preserving order."""
    out = {}
    pat = re.compile(r"&(\w+)(.*?)^\s*/\s*$", re.DOTALL | re.MULTILINE)
    for m in pat.finditer(nl_text):
        name = m.group(1).lower()
        body = m.group(2)
        d = {}
        for raw in body.splitlines():
            line = raw.split("!", 1)[0].strip().rstrip(",")
            if not line:
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            d[key.strip()] = val.strip()
        out[name] = d
    return out


def _emit_namelist(name, d):
    lines = ["&{}".format(name.upper())]
    for k, v in d.items():
        lines.append("  {} = {}".format(k, v))
    lines.append("/")
    return "\n".join(lines)


def _replace_kmesh(cards_text, kmesh):
    """Replace the grid line following 'K_POINTS automatic' with `kmesh`  0 0 0."""
    lines = cards_text.splitlines()
    out = []
    expect_grid = False
    for ln in lines:
        if expect_grid and ln.strip():
            out.append("  {}  0 0 0".format(kmesh))
            expect_grid = False
            continue
        out.append(ln)
        if ln.strip().upper().startswith("K_POINTS"):
            expect_grid = True
    return "\n".join(out)


def _tag(ecut, kmesh):
    kx, ky, kz = kmesh.split()
    return "e{}_k{}x{}x{}".format(ecut, kx, ky, kz)


def _build_input(base_text, prefix, ecut, kmesh):
    nl_text, cards_text = _split_namelists_cards(base_text)
    nls = _parse_namelists(nl_text)

    ctrl = nls.get("control", {})
    ctrl["calculation"] = "'scf'"
    ctrl["prefix"] = "'{}_{}'".format(prefix, _tag(ecut, kmesh))
    ctrl["outdir"] = "'./tmp'"
    ctrl["tprnfor"] = ".true."
    ctrl["tstress"] = ".true."
    for k in ("forc_conv_thr", "etot_conv_thr", "nstep"):
        ctrl.pop(k, None)

    system = nls.get("system", {})
    system["ecutwfc"] = str(ecut)
    system["ecutrho"] = str(ecut * RHO_RATIO)

    electrons = nls.get("electrons", {})

    parts = [
        "! AUTO-GENERATED by conv_test.py — convergence test, do not hand-edit.",
        "! Single-point SCF derived from {}/relax; only ecutwfc/k-mesh vary.".format(prefix),
        _emit_namelist("control", ctrl),
        "",
        _emit_namelist("system", system),
        "",
        _emit_namelist("electrons", electrons),
        "",
        _replace_kmesh(cards_text, kmesh),
        "",
    ]
    return "\n".join(parts)


def cmd_gen(_args):
    jobs = []  # (ecut, kmesh)
    for e in ECUT_LIST:
        jobs.append((e, "4 4 8"))          # ecut sweep at production mesh
    for k in KPTS_LIST:
        jobs.append((BASE_ECUT, k))        # k sweep at ecut=60
    # dedup while preserving order
    seen, uniq = set(), []
    for j in jobs:
        if j not in seen:
            seen.add(j)
            uniq.append(j)

    total = 0
    for sysdir, (prefix, relax_in) in SYSTEMS.items():
        base_path = os.path.join(ROOT, sysdir, "relax", relax_in)
        if not os.path.isfile(base_path):
            print("[WARN] missing {} — skipping {}".format(base_path, sysdir))
            continue
        with open(base_path, "r", encoding="utf-8", errors="replace") as fh:
            base_text = fh.read()
        conv_dir = os.path.join(ROOT, sysdir, "conv")
        os.makedirs(conv_dir, exist_ok=True)
        for ecut, kmesh in uniq:
            tag = _tag(ecut, kmesh)
            fname = "{}.conv_{}.scf.in".format(prefix, tag)
            with open(os.path.join(conv_dir, fname), "w", encoding="utf-8") as out:
                out.write(_build_input(base_text, prefix, ecut, kmesh))
            total += 1
        print("[gen] {:<11s}: {} inputs -> {}/conv/".format(sysdir, len(uniq), sysdir))
    print("[gen] {} input files written across {} systems.".format(total, len(SYSTEMS)))
    print("[gen] Next: bash run_conv.sh   (then: python conv_test.py analyze)")


# --------------------------------------------------------------------------- #
# output parsing / analysis
# --------------------------------------------------------------------------- #
def _parse_out(path):
    """Return dict with energy(Ry), force(Ry/Bohr), pressure(kbar), nat, done."""
    res = {"energy": None, "force": None, "pressure": None, "nat": None, "done": False}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if "JOB DONE" in ln:
                res["done"] = True
            elif ln.lstrip().startswith("!"):
                m = re.search(r"=\s*(-?\d+\.\d+)\s*Ry", ln)
                if m:
                    res["energy"] = float(m.group(1))
            elif "Total force" in ln:
                m = re.search(r"Total force\s*=\s*(-?\d+\.\d+)", ln)
                if m:
                    res["force"] = float(m.group(1))
            elif "P=" in ln and "stress" in ln:
                m = re.search(r"P=\s*(-?\d+\.\d+)", ln)
                if m:
                    res["pressure"] = float(m.group(1))
            elif "number of atoms/cell" in ln:
                m = re.search(r"=\s*(\d+)", ln)
                if m:
                    res["nat"] = int(m.group(1))
    return res


def _tag_from_name(path):
    m = re.search(r"\.conv_e(\d+)_k(\d+)x(\d+)x(\d+)\.scf\.(in|out)$",
                  os.path.basename(path))
    if not m:
        return None
    ecut = int(m.group(1))
    kmesh = "{} {} {}".format(m.group(2), m.group(3), m.group(4))
    return ecut, kmesh


def _fmt(v, spec):
    return format(v, spec) if v is not None else "   --   "


def _report_sweep(title, rows, ref_key, nat):
    """rows: list of (label, data-dict). ref_key: label of dense reference."""
    print("\n  {}".format(title))
    print("  {:<12s} {:>14s} {:>12s} {:>10s} {:>12s}".format(
        "setting", "E (eV/atom)", "dE(meV/at)", "P (kbar)", "|F|(Ry/au)"))
    print("  " + "-" * 62)
    ref = dict(rows).get(ref_key)
    e_ref = (ref["energy"] * RY_TO_EV / nat) if (ref and ref["energy"] and nat) else None
    recommended = None
    for label, d in rows:
        e_per_atom = (d["energy"] * RY_TO_EV / nat) if (d["energy"] and nat) else None
        de = ((e_per_atom - e_ref) * 1000.0) if (e_per_atom is not None and e_ref is not None) else None
        mark = ""
        if d["done"] and de is not None and d["pressure"] is not None and ref:
            dp = abs(d["pressure"] - ref["pressure"])
            if abs(de) <= TOL_E_MEV_PER_ATOM and dp <= TOL_P_KBAR:
                mark = " converged"
                if recommended is None:
                    recommended = label
        if not d["done"]:
            mark = " (not done)"
        print("  {:<12s} {:>14s} {:>12s} {:>10s} {:>12s}{}".format(
            label, _fmt(e_per_atom, "14.6f"), _fmt(de, "12.3f"),
            _fmt(d["pressure"], "10.2f"), _fmt(d["force"], "12.6f"), mark))
    if recommended:
        print("  -> coarsest converged: {}  (dE<={} meV/atom, dP<={} kbar vs {})".format(
            recommended, TOL_E_MEV_PER_ATOM, TOL_P_KBAR, ref_key))
    else:
        print("  -> no setting flagged converged yet (missing runs, or widen tolerance).")


def cmd_analyze(_args):
    for sysdir, (prefix, _relax_in) in SYSTEMS.items():
        conv_dir = os.path.join(ROOT, sysdir, "conv")
        outs = sorted(glob.glob(os.path.join(conv_dir, "*.conv_*.scf.out")))
        if not outs:
            print("\n=== {} : no outputs yet in {}/conv/ ===".format(sysdir, sysdir))
            continue
        parsed = {}
        nat = None
        for p in outs:
            tag = _tag_from_name(p)
            if not tag:
                continue
            d = _parse_out(p)
            parsed[tag] = d
            if d["nat"]:
                nat = d["nat"]
        print("\n" + "=" * 66)
        print("=== {}  (prefix {}, nat={}) ===".format(sysdir, prefix, nat))

        # ecut sweep at production mesh (4 4 8)
        ecut_rows = []
        for e in ECUT_LIST:
            key = (e, "4 4 8")
            if key in parsed:
                ecut_rows.append(("ecut {}".format(e), parsed[key]))
        if ecut_rows:
            _report_sweep("ecutwfc sweep @ k=4x4x8 (ref = highest ecut):",
                          ecut_rows, "ecut {}".format(ECUT_LIST[-1]), nat)

        # k sweep at ecut=60
        k_rows = []
        for k in KPTS_LIST:
            key = (BASE_ECUT, k)
            if key in parsed:
                k_rows.append(("k {}".format(k.replace(" ", "x")), parsed[key]))
        if k_rows:
            _report_sweep("k-mesh sweep @ ecutwfc={} (ref = densest mesh):".format(BASE_ECUT),
                          k_rows, "k {}".format(KPTS_LIST[-1].replace(" ", "x")), nat)
    print("\nNote: relax needs only FORCE+PRESSURE convergence — pick the coarsest")
    print("mesh flagged 'converged'; keep the dense mesh for scf/nscf/dos/optical.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen", help="generate convergence SCF inputs")
    sub.add_parser("analyze", help="tabulate convergence outputs + flag recommendation")
    args = ap.parse_args()
    if args.cmd == "gen":
        cmd_gen(args)
    elif args.cmd == "analyze":
        cmd_analyze(args)


if __name__ == "__main__":
    sys.exit(main())
