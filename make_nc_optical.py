#!/usr/bin/env python3
"""
make_nc_optical.py — derive norm-conserving (NC) optical inputs from the
existing PAW scf/nscf inputs.

WHY: epsilon.x computes interband matrix elements only for norm-conserving
pseudopotentials ("USPP are not implemented" / grid_build error #1). The main
study uses PAW (kjpaw) pseudos, which are correct for total energies, bands,
DOS and gaps — but cannot be fed to epsilon.x. So the optical branch runs its
own SCF -> NSCF with NC pseudos on the SAME relaxed geometry, then epsilon.x.

This generator copies an scf/nscf input verbatim and only changes:
  - pseudo_dir          -> the NC pseudo directory
  - ATOMIC_SPECIES file -> the NC .UPF for each element (by symbol)
  - ecutwfc / ecutrho   -> NC-appropriate cutoffs

Everything else — CELL_PARAMETERS, ATOMIC_POSITIONS, HUBBARD, K_POINTS,
nbnd, nosym, tetrahedra_opt, nspin — is preserved, so the optical electronic
structure stays as close as possible to the rest of the study. The absorption
onset is pinned to experiment afterwards via the scissor `shift` in epsilon.in.

Usage:
  make_nc_optical.py --in scf.in  --out opt_scf.in  \
      --pseudo-dir ../../pseudo_nc --map Sn=Sn.upf,O=O.upf,Ti=Ti.upf \
      --ecutwfc 80 --ecutrho 320
"""
import argparse
import re
import sys


def parse_map(s):
    m = {}
    for pair in s.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            sys.exit(f"[make_nc_optical] bad --map entry (need El=file.upf): {pair!r}")
        el, fn = pair.split("=", 1)
        m[el.strip()] = fn.strip()
    return m


# ALL-CAPS card headers that terminate the ATOMIC_SPECIES block
_CARD = re.compile(r"^\s*[A-Z_]+(\s+.*)?$")


def transform(text, pseudo_dir, elmap, ecutwfc, ecutrho):
    out = []
    in_species = False
    seen = set()
    for line in text.splitlines():
        stripped = line.strip()

        # --- pseudo_dir ---
        m = re.match(r"^(\s*pseudo_dir\s*=\s*)'[^']*'(.*)$", line, re.IGNORECASE)
        if m:
            out.append(f"{m.group(1)}'{pseudo_dir}'{m.group(2)}")
            continue

        # --- cutoffs ---
        m = re.match(r"^(\s*ecutwfc\s*=\s*)[0-9.eEdD+-]+(.*)$", line, re.IGNORECASE)
        if m and ecutwfc is not None:
            out.append(f"{m.group(1)}{ecutwfc}{m.group(2)}")
            continue
        m = re.match(r"^(\s*ecutrho\s*=\s*)[0-9.eEdD+-]+(.*)$", line, re.IGNORECASE)
        if m and ecutrho is not None:
            out.append(f"{m.group(1)}{ecutrho}{m.group(2)}")
            continue

        # --- ATOMIC_SPECIES block: swap the pseudo filename per element ---
        if re.match(r"^\s*ATOMIC_SPECIES\b", line, re.IGNORECASE):
            in_species = True
            out.append(line)
            continue
        if in_species:
            # blank line, comment, or a new card header ends the block
            if stripped == "" or stripped.startswith("!"):
                out.append(line)
                continue
            parts = stripped.split()
            if len(parts) == 3 and parts[0] in elmap:
                el, mass, _old = parts
                seen.add(el)
                indent = line[: len(line) - len(line.lstrip())]
                out.append(f"{indent}{el}  {mass}  {elmap[el]}")
                continue
            # a recognised next card (e.g. CELL_PARAMETERS) -> leave species block
            if _CARD.match(line) and parts and parts[0].isupper():
                in_species = False
            out.append(line)
            continue

        out.append(line)

    missing = [el for el in elmap if el not in seen and _element_used(text, el)]
    if missing:
        sys.exit(f"[make_nc_optical] elements in --map never matched in ATOMIC_SPECIES: {missing}")
    return "\n".join(out) + "\n"


def _element_used(text, el):
    # only warn about a mapped element if it actually appears as a species line
    return re.search(rf"^\s*{re.escape(el)}\s+\d", text, re.MULTILINE) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--pseudo-dir", required=True)
    ap.add_argument("--map", required=True, help="El=file.upf,El2=file2.upf")
    ap.add_argument("--ecutwfc", type=str, default=None)
    ap.add_argument("--ecutrho", type=str, default=None)
    args = ap.parse_args()

    elmap = parse_map(args.map)
    with open(args.inp, "r", encoding="utf-8") as f:
        text = f.read()
    new = transform(text, args.pseudo_dir, elmap, args.ecutwfc, args.ecutrho)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"[make_nc_optical] wrote {args.out} (NC pseudos: {elmap})")


if __name__ == "__main__":
    main()
