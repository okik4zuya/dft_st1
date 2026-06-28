#!/usr/bin/env python3
"""
update_geometry.py  --  propagate a relaxed structure into downstream pw.x inputs.

Reads the 'Begin final coordinates ... End final coordinates' block from a QE
vc-relax/relax output, validates it (minimum-image cation-anion bond lengths),
and overwrites the CELL_PARAMETERS and ATOMIC_POSITIONS blocks of each target
pw.x input file (scf / nscf / bands).

Usage:
    python3 update_geometry.py RELAX_OUT TARGET.in [TARGET2.in ...]

Exit codes:
    0  success (all targets updated)
    2  geometry failed the bond-length sanity check  -> caller must NOT proceed
    3  could not parse a final structure from RELAX_OUT
    4  a target file could not be updated (block not found / atom-count mismatch)

This is the safety net that prevents a bad geometry (e.g. the 1737 kbar O-position
bug) from silently propagating through scf -> nscf -> bands and wasting hours.
"""
import re
import sys

# Cation species we apply the short-bond guard against (vs O).
CATIONS = {"Sn", "Ti"}
ANION = "O"
MIN_CATION_ANION = 1.80   # Angstrom; correct rutile M-O is ~1.95-2.06
MIN_ANY_PAIR = 1.00       # Angstrom; anything closer = overlapping atoms

_FLOAT = r"[-+]?\d+\.?\d*(?:[eEdD][-+]?\d+)?"
_ATOM_RE = re.compile(rf"^\s*([A-Z][a-zA-Z]?)\s+({_FLOAT})\s+({_FLOAT})\s+({_FLOAT})")
_VEC_RE = re.compile(rf"^\s*({_FLOAT})\s+({_FLOAT})\s+({_FLOAT})")


def _f(x):
    return float(x.replace("D", "E").replace("d", "e"))


def parse_final_structure(out_path):
    """Return (cell_unit, cell[3][3], pos_unit, atoms[(sym,x,y,z)]) or None."""
    with open(out_path, "r", errors="replace") as fh:
        text = fh.read()

    # Use the LAST final-coordinates block (the converged one).
    starts = [m.end() for m in re.finditer(r"Begin final coordinates", text)]
    if not starts:
        return None
    block = text[starts[-1]:]
    end = block.find("End final coordinates")
    if end != -1:
        block = block[:end]
    lines = block.splitlines()

    cell_unit, cell = None, []
    pos_unit, atoms = None, []

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if "CELL_PARAMETERS" in line:
            m = re.search(r"\((.*?)\)", line)
            cell_unit = m.group(1).strip() if m else "angstrom"
            cell = []
            j = i + 1
            while j < n and len(cell) < 3:
                vm = _VEC_RE.match(lines[j])
                if vm:
                    cell.append([_f(vm.group(1)), _f(vm.group(2)), _f(vm.group(3))])
                elif lines[j].strip():
                    break
                j += 1
            i = j
            continue
        if "ATOMIC_POSITIONS" in line:
            m = re.search(r"\((.*?)\)", line)
            pos_unit = m.group(1).strip() if m else "angstrom"
            atoms = []
            j = i + 1
            while j < n:
                am = _ATOM_RE.match(lines[j])
                if am:
                    atoms.append((am.group(1), _f(am.group(2)),
                                  _f(am.group(3)), _f(am.group(4))))
                elif lines[j].strip():
                    break
                j += 1
            i = j
            continue
        i += 1

    if len(cell) != 3 or not atoms:
        return None
    return cell_unit, cell, pos_unit, atoms


def _inv3(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise ValueError("singular cell matrix")
    inv = [
        [(e * i - f * h), (c * h - b * i), (b * f - c * e)],
        [(f * g - d * i), (a * i - c * g), (c * d - a * f)],
        [(d * h - e * g), (b * g - a * h), (a * e - b * d)],
    ]
    return [[inv[r][k] / det for k in range(3)] for r in range(3)]


def check_bonds(cell, pos_unit, atoms):
    """Minimum-image bond check. Returns (ok, message). Only valid for angstrom."""
    if pos_unit.lower() not in ("angstrom", "ang"):
        return True, (f"positions in '{pos_unit}' (not angstrom) -- bond guard "
                      f"SKIPPED; verify geometry manually")

    # rows of `cell` are lattice vectors a1,a2,a3 (angstrom).
    A = cell
    Ainv = _inv3(A)  # cart = frac . A   =>   frac = cart . Ainv

    def mic_dist(p, q):
        d = [p[k] - q[k] for k in range(3)]
        # to fractional
        fr = [sum(d[k] * Ainv[k][c] for k in range(3)) for c in range(3)]
        fr = [v - round(v) for v in fr]
        dc = [sum(fr[k] * A[k][c] for k in range(3)) for c in range(3)]
        return (dc[0] ** 2 + dc[1] ** 2 + dc[2] ** 2) ** 0.5

    cats = [(s, (x, y, z)) for (s, x, y, z) in atoms if s in CATIONS]
    ans = [(s, (x, y, z)) for (s, x, y, z) in atoms if s == ANION]

    min_mo = float("inf")
    min_mo_pair = None
    for cs, cp in cats:
        for _, ap in ans:
            dd = mic_dist(cp, ap)
            if dd < min_mo:
                min_mo, min_mo_pair = dd, (cs, cp, ap)

    # global overlap check (all pairs)
    min_any = float("inf")
    P = [(s, (x, y, z)) for (s, x, y, z) in atoms]
    for a in range(len(P)):
        for b in range(a + 1, len(P)):
            dd = mic_dist(P[a][1], P[b][1])
            if dd < min_any:
                min_any = dd

    if min_any < MIN_ANY_PAIR:
        return False, f"FATAL: overlapping atoms, min pair distance {min_any:.3f} A"
    if min_mo < MIN_CATION_ANION:
        cs, cp, ap = min_mo_pair
        return False, (f"FATAL: shortest cation-anion bond {min_mo:.3f} A "
                       f"(< {MIN_CATION_ANION} A) {cs}{tuple(round(v,3) for v in cp)}"
                       f"-O{tuple(round(v,3) for v in ap)} -- BAD GEOMETRY, aborting")
    return True, f"OK: min {ANION}-cation bond {min_mo:.3f} A, min any pair {min_any:.3f} A"


def _fmt_cell(unit, cell):
    out = [f"CELL_PARAMETERS {unit}"]
    for v in cell:
        out.append(f"  {v[0]:14.9f} {v[1]:14.9f} {v[2]:14.9f}")
    return out


def _fmt_pos(unit, atoms):
    out = [f"ATOMIC_POSITIONS {unit}"]
    for s, x, y, z in atoms:
        out.append(f"  {s:<3s} {x:14.9f} {y:14.9f} {z:14.9f}")
    return out


def _replace_block(lines, keyword, new_lines, is_atom_block, expect_n=None):
    """Replace the `keyword` card (header + following data lines) with new_lines."""
    idx = next((k for k, ln in enumerate(lines)
                if ln.lstrip().upper().startswith(keyword)), None)
    if idx is None:
        raise ValueError(f"'{keyword}' not found")
    j = idx + 1
    data = _ATOM_RE if is_atom_block else _VEC_RE
    count = 0
    limit = expect_n if (is_atom_block and expect_n) else (3 if not is_atom_block else None)
    while j < len(lines):
        if limit is not None and count >= limit:
            break
        if data.match(lines[j]):
            count += 1
            j += 1
        elif lines[j].strip() == "" and count == 0:
            # allow a single blank between header and data
            j += 1
        else:
            break
    return lines[:idx] + new_lines + lines[j:], count


def update_target(path, cell_unit, cell, pos_unit, atoms):
    with open(path, "r", errors="replace") as fh:
        lines = fh.read().splitlines()

    lines, _ = _replace_block(lines, "CELL_PARAMETERS",
                              _fmt_cell(cell_unit, cell), is_atom_block=False)
    lines, nat = _replace_block(lines, "ATOMIC_POSITIONS",
                                _fmt_pos(pos_unit, atoms),
                                is_atom_block=True, expect_n=len(atoms))
    if nat != len(atoms):
        raise ValueError(f"atom-count mismatch: wrote {len(atoms)}, "
                         f"old block had {nat} -- check nat in {path}")

    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 1
    relax_out, targets = argv[1], argv[2:]

    parsed = parse_final_structure(relax_out)
    if parsed is None:
        print(f"[update_geometry] ERROR: no converged 'final coordinates' block in "
              f"{relax_out} -- did vc-relax finish?", file=sys.stderr)
        return 3
    cell_unit, cell, pos_unit, atoms = parsed

    ok, msg = check_bonds(cell, pos_unit, atoms)
    print(f"[update_geometry] {len(atoms)} atoms, cell unit '{cell_unit}'. {msg}")
    if not ok:
        return 2

    for t in targets:
        try:
            update_target(t, cell_unit, cell, pos_unit, atoms)
            print(f"[update_geometry] updated geometry in {t}")
        except (ValueError, OSError) as e:
            print(f"[update_geometry] ERROR updating {t}: {e}", file=sys.stderr)
            return 4
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
