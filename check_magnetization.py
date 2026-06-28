#!/usr/bin/env python3
"""
check_magnetization.py
======================
Diagnostic for the spin treatment of the self-doped (SnO2-x) cells.

The doped inputs force  nspin = 2, starting_magnetization(Sn) = 0.5  on the
assumption that the oxygen-vacancy electrons localise and carry a moment. But
Sn(2+) is a 5s^2 lone pair (non-magnetic) and the donor electrons most likely
delocalise into Sn 5s conduction states. This script reads the converged
total/absolute magnetization from each relax and scf output and flags whether
nspin = 2 is actually justified.

Decision rule (printed per system):
  |M_tot| < 0.1 muB  ->  no moment: nspin = 2 is unjustified overhead.
                         Either document why it is kept or drop to nspin = 1.
  |M_tot| >= 0.1 muB ->  finite moment: confirm it is physical (localised
                         polaron-like state) and NOT an artifact of the forced
                         starting_magnetization guess.

This is a DIAGNOSTIC only — it changes no inputs. Run after relax/scf finish.

Usage:
    python check_magnetization.py
"""

import os
import re

BASE_DIR = '.'

# (system label, nspin in the input, list of candidate output files)
SYSTEMS = [
    ('SnO2_pristine', 1, ['pristine/relax/SnO2_pristine.relax.out',
                          'pristine/scf/SnO2_pristine.scf.out']),
    ('SnO2_1to1',     2, ['ratio_1to1/relax/SnO2_1to1.relax.out',
                          'ratio_1to1/scf/SnO2_1to1.scf.out']),
    ('SnO2_2to1',     2, ['ratio_2to1/relax/SnO2_2to1.relax.out',
                          'ratio_2to1/scf/SnO2_2to1.scf.out']),
    ('TiO2_pristine', 1, ['TiO2/relax/TiO2_pristine.relax.out',
                          'TiO2/scf/TiO2_pristine.scf.out']),
]

MOMENT_THRESH = 0.1   # muB; below this we treat the cell as non-magnetic

# QE prints, at every SCF iteration:
#     total magnetization       =    X.XX Bohr mag/cell
#     absolute magnetization    =    Y.YY Bohr mag/cell
_TOT_RE = re.compile(r'total magnetization\s*=\s*([-\d.]+)', re.I)
_ABS_RE = re.compile(r'absolute magnetization\s*=\s*([-\d.]+)', re.I)


def last_magnetization(path):
    """Return (total, absolute) magnetization from the LAST SCF iteration, or None."""
    try:
        with open(path, errors='replace') as f:
            content = f.read()
    except OSError:
        return None
    tot = _TOT_RE.findall(content)
    ab  = _ABS_RE.findall(content)
    if not tot:
        return None
    total    = float(tot[-1])
    absolute = float(ab[-1]) if ab else None
    return total, absolute


def main():
    print("=" * 64)
    print("  MAGNETIZATION DIAGNOSTIC  (nspin justification for doped cells)")
    print("=" * 64)

    for label, nspin, candidates in SYSTEMS:
        print(f"\nSystem: {label}   (input nspin = {nspin})")

        found_any = False
        for rel in candidates:
            path = os.path.join(BASE_DIR, rel)
            if not os.path.exists(path):
                print(f"  - {rel}: (not found)")
                continue
            found_any = True
            mag = last_magnetization(path)
            if mag is None:
                if nspin == 1:
                    print(f"  - {rel}: nspin=1, no magnetization printed (expected).")
                else:
                    print(f"  - {rel}: WARNING no magnetization line found "
                          f"(did this run use nspin=2?).")
                continue

            total, absolute = mag
            ab_txt = f"{absolute:.3f}" if absolute is not None else "n/a"
            print(f"  - {rel}:  M_tot = {total:+.3f}  |  M_abs = {ab_txt}  muB/cell")

            if nspin == 2:
                if abs(total) < MOMENT_THRESH:
                    print(f"      => |M_tot| < {MOMENT_THRESH} muB: NO net moment. "
                          f"nspin=2 is unjustified overhead for this cell —")
                    print(f"         document why it is kept, or rerun with nspin=1.")
                else:
                    print(f"      => finite moment ({total:+.3f} muB): confirm it is a "
                          f"physical localised state,")
                    print(f"         not an artifact of starting_magnetization(Sn)=0.5.")

        if not found_any:
            print("  (no outputs yet — run relax/scf first)")

    print("\n" + "=" * 64)
    print("Reminder: in SnO2, vacancy electrons are Sn 5s-like and tend to")
    print("delocalise; a near-zero moment is the physically expected result.")
    print("=" * 64)


if __name__ == '__main__':
    main()
