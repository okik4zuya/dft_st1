# Norm-conserving (NC) pseudopotentials — for the optical branch ONLY

`epsilon.x` computes interband matrix elements **only** for norm-conserving
pseudopotentials. The main study uses PAW (`*_kjpaw_psl.1.0.0.UPF`, in
`../pseudo/`), which `epsilon.x` rejects with:

```
from grid_build : error #1
USPP are not implemented
```

So the optical step (`run.sh optical`) runs a separate **NC** SCF → NSCF on the
already-relaxed geometry, then `epsilon.x`. Drop the NC `.UPF` files here.

## Required files (default names expected by `run_lib.sh`)

| Element | Expected filename here | Must include in valence |
|---------|------------------------|-------------------------|
| Sn      | `Sn.upf`               | 4d (for `HUBBARD U Sn-4d`) |
| O       | `O.upf`                | 2s 2p                   |
| Ti      | `Ti.upf`               | 3d (for `HUBBARD U Ti-3d`) |

If your downloaded files have different names, either rename them to the above
or override `NC_MAP` when calling `run.sh` (see below).

## Where to get them (PBEsol, scalar-relativistic, NC)

**Pseudo Dojo** — http://www.pseudo-dojo.org
1. Select: *PBEsol*, *SR* (scalar-relativistic), *standard* accuracy, format
   **UPF (Quantum ESPRESSO)**.
2. Download Sn, O, Ti. The Pseudo Dojo Sn (4d10 5s2 5p2) and Ti (3s3p3d4s)
   standard sets include the semicore d states needed for `+U`.
3. Place them here and rename to `Sn.upf`, `O.upf`, `Ti.upf`.

> The recommended cutoffs for these NC pseudos are higher than for PAW. The
> optical inputs default to `ecutwfc=80 Ry`, `ecutrho=320 Ry`. Adjust via
> `NC_ECUTWFC` / `NC_ECUTRHO` env vars if Pseudo Dojo hints differ.

## Overriding names / cutoffs

```bash
NC_MAP="Sn=Sn_ONCV_PBEsol.upf,O=O_ONCV_PBEsol.upf,Ti=Ti_ONCV_PBEsol.upf" \
NC_ECUTWFC=90 NC_ECUTRHO=360 \
bash run.sh optical
```
