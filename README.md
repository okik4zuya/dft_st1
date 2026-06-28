# QE Input Files — SnO₂₋ₓ/TiO₂ DFT Study

## Oxygen Vacancy Concentration vs Band Gap + Heterojunction Mechanism

---

## System Overview

| Folder | System | nat | Vo | Vo% (DFT) | Vo% (exp) | Eg_exp (K-M) |
| --- | --- | --- | --- | --- | --- | --- |
| `pristine/` | Stoichiometric SnO₂ | 24 (8Sn+16O) | 0 | 0% | 0% | ~3.60 eV |
| `ratio_1to1/` | SnO₂₋ₓ (1:1 Sn²⁺:Sn⁴⁺) | 22 (8Sn+14O) | 2 | 12.50% | 12.71% | **2.41 eV** |
| `ratio_2to1/` | SnO₂₋ₓ (2:1 Sn²⁺:Sn⁴⁺) | 21 (8Sn+13O) | 3 | 18.75% | 17.64% | **2.21 eV** |
| `TiO2/` | Pristine rutile TiO₂ | 24 (8Ti+16O) | 0 | — | — | ~3.00 eV |

All SnO₂ supercells: **2×2×1 rutile SnO₂** (a=b=9.474 Å, c=3.186 Å)
TiO₂ supercell: **2×2×1 rutile TiO₂** (a=b=9.188 Å, c=2.959 Å)

---

## Directory Structure

```
QE/
├── pseudo/                          ← PUT PSEUDOPOTENTIALS HERE
│   ├── Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF
│   ├── O.pbesol-n-kjpaw_psl.1.0.0.UPF
│   └── Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF
│
├── pristine/
│   ├── relax/   SnO2_pristine.relax.in
│   ├── scf/     SnO2_pristine.scf.in
│   ├── nscf/    SnO2_pristine.nscf.in
│   ├── bands/   SnO2_pristine.bands.in + bands_pp.in
│   ├── dos/     SnO2_pristine.dos.in + pdos.in
│   ├── optical/ SnO2_pristine.epsilon.in
│   └── pp/      SnO2_pristine.pp.in
│
├── ratio_1to1/                      ← 2 Vo, 12.50%, Eg=2.41 eV (nspin=2)
│   ├── relax/   SnO2_1to1.relax.in
│   ├── scf/     SnO2_1to1.scf.in + scf_unrelaxed/  (distortion isolation)
│   ├── nscf/    SnO2_1to1.nscf.in
│   ├── bands/   SnO2_1to1.bands.in + bands_pp.in
│   ├── dos/     SnO2_1to1.dos.in + pdos.in
│   ├── optical/ SnO2_1to1.epsilon.in
│   └── pp/      SnO2_1to1.pp.in
│
├── ratio_2to1/                      ← 3 Vo, 18.75%, Eg=2.21 eV (nspin=2)
│   └── [same layout as ratio_1to1]
│
├── TiO2/                            ← pristine rutile TiO₂, U(Ti-3d)=4.2 eV
│   └── [same layout as pristine/]
│
├── postprocess/
│   ├── run_figures.py               ← generate all 5 figures
│   ├── fig1_bands_pdos.py
│   ├── fig2_pdos_comparison.py
│   ├── fig3_delta_rho.py
│   ├── fig4_optical_absorption.py
│   └── fig5_energy_diagram.py
│
├── run_all.sh                       ← master run script (two-phase, auto-scaling)
├── update_geometry.py               ← auto-injects relaxed coords into scf/nscf/bands
├── extract_dft_values.py            ← extracts VBM/CBM/O1s/Fermi from QE outputs
├── band_alignment.py                ← O 1s core-level alignment → energy diagram
├── check_magnetization.py           ← verify spin ansatz in doped cells
├── distortion_analysis.py           ← isolate distortion vs electronic gap contribution
└── progress.md                      ← timestamped run log (auto-written by run_all.sh)
```

---

## Running Calculations

### Quick start (recommended)

```bash
# Phase 1: relaxation only — stops after injecting relaxed geometry for review
bash run_all.sh relax

# Review the injected coordinates, then run the rest
bash run_all.sh post

# OR run everything end-to-end in one shot
bash run_all.sh
```

The script is **idempotent**: re-running it resumes from the first incomplete step (checks for `JOB DONE` in output files). Safe to stop and restart at any point.

### Per-system override

```bash
bash run_all.sh relax pristine         # relax only, pristine system
bash run_all.sh post  ratio_1to1       # post only, 1:1 system
bash run_all.sh all   ratio_2to1       # full chain, 2:1 system
```

### Resource overrides

```bash
NPROC=4            bash run_all.sh post   # force 4 ranks (laptop)
OMP_NUM_THREADS=2  bash run_all.sh post   # 32 MPI × 2 OMP hybrid
MEM_PER_RANK_MB=500 bash run_all.sh       # tighter RAM guard (larger cells)
NK_PW=4 NK_BANDS=2 bash run_all.sh       # manual k-pool pin
```

The script auto-detects physical cores (not SMT threads), guards against OOM by
capping ranks at `AvailMem / MEM_PER_RANK_MB` (default 300 MB), and picks the
largest valid `npool` divisor automatically.

---

## Step-by-Step Workflow (Manual Reference)

### 0. Download pseudopotentials

```bash
# SSSP Precision v1.3: https://www.materialscloud.org/discover/sssp
# Required files:
#   Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF
#   O.pbesol-n-kjpaw_psl.1.0.0.UPF
#   Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF
mkdir -p pseudo
```

### 1. Run vc-relax

```bash
cd pristine/relax && mkdir -p tmp
mpirun -np 64 pw.x -nk 8 -pd .true. -in SnO2_pristine.relax.in > SnO2_pristine.relax.out
```

### 2. Inject relaxed geometry (replaces manual coord extraction)

```bash
# Parses Begin/End final coordinates from relax.out;
# overwrites CELL_PARAMETERS + ATOMIC_POSITIONS in scf/nscf/bands inputs;
# aborts if any cation–O bond < 1.8 Å
python3 update_geometry.py pristine/relax/SnO2_pristine.relax.out pristine/scf/SnO2_pristine.scf.in
```

### 3. Run SCF

```bash
cd ../scf && mkdir -p tmp
mpirun -np 64 pw.x -nk 8 -in SnO2_pristine.scf.in > SnO2_pristine.scf.out
```

### 4. Run NSCF (denser k-mesh, CG diagonalization)

```bash
cd ../nscf && rm -rf tmp && ln -sfn ../scf/tmp tmp
mpirun -np 64 pw.x -nk 8 -in SnO2_pristine.nscf.in > SnO2_pristine.nscf.out
```

### 5. Band structure

```bash
cd ../bands && rm -rf tmp && ln -sfn ../scf/tmp tmp
mpirun -np 64 pw.x    -nk 4 -in SnO2_pristine.bands.in    > SnO2_pristine.bands.out
mpirun -np 64 bands.x -pd .true. -in SnO2_pristine.bands_pp.in > SnO2_pristine.bands_pp.out
```

### 6. DOS and PDOS

```bash
cd ../dos && rm -rf tmp && ln -sfn ../nscf/tmp tmp
mpirun -np 64 dos.x     -pd .true. -in SnO2_pristine.dos.in  > SnO2_pristine.dos.out
mpirun -np 64 projwfc.x -pd .true. -in SnO2_pristine.pdos.in > SnO2_pristine.pdos.out
```

### 7. Optical properties

```bash
# Set scissor shift after reading Eg from band_alignment.py output
cd ../optical && rm -rf tmp && ln -sfn ../nscf/tmp tmp
mpirun -np 64 epsilon.x -pd .true. -in SnO2_pristine.epsilon.in > SnO2_pristine.epsilon.out
```

### 8. Charge density

```bash
cd ../pp && rm -rf tmp && ln -sfn ../scf/tmp tmp
mpirun -np 64 pp.x -pd .true. -in SnO2_pristine.pp.in > SnO2_pristine.pp.out
# Output: SnO2_pristine_charge.cube -> open in VESTA
```

---

## Post-Processing Workflow

```bash
# Step 1: extract VBM, CBM, Fermi, O 1s core levels from all QE outputs
python3 extract_dft_values.py

# Step 2: copy printed values into band_alignment.py data section
# Step 3: set DEMO_MODE = False in band_alignment.py
python3 band_alignment.py      # → scissor shifts, ALIGNED_VBM, energy_diagram.png

# Step 4: fill epsilon.in (scissor shift), fig2 CORE_SHIFT dict, fig5 ALIGNED_VBM dict
# Step 5: re-run epsilon.x with scissor corrections

# Step 6: generate all 5 manuscript figures
cd postprocess/ && python3 run_figures.py
```

### Figures

| Fig | Script | Content |
|---|---|---|
| 1 | fig1_bands_pdos.py | Band structure + PDOS (1:1 and 2:1 SnO₂) |
| 2 | fig2_pdos_comparison.py | Stacked PDOS all 4 systems |
| 3 | fig3_delta_rho.py | Δρ cube + 2D slice |
| 4 | fig4_optical_absorption.py | α(ω) + Tauc inset |
| 5 | fig5_energy_diagram.py | Band alignment → Type-II/Z/S-scheme |

All scripts fall back to demo data if QE outputs are absent.

---

## Critical Parameters to Check

### Before running any calculation

- [ ] Pseudopotentials are in `pseudo/` directory (Sn, O, Ti)
- [ ] `pw.x` is on PATH (`which pw.x`)
- [ ] ecutwfc convergence tested (40, 60, 80 Ry)
- [ ] k-point convergence tested for SCF

### After vc-relax, before SCF

- [ ] Forces < 0.01 eV/Å in relax output
- [ ] Stress < 0.5 kbar in relax output
- [ ] `update_geometry.py` exited 0 (geometry injected, bond guard passed)
- [ ] Initial pressure was <10 kbar (if >100 kbar, check cation–O distances)

### After SCF

- [ ] SCF converged ("convergence has been achieved")
- [ ] Compute scissor shift for each system via `band_alignment.py`
- [ ] Update `shift=` in each `epsilon.in`

### After bands

- [ ] Band gap trend: pristine > 1:1 (2.41 eV) > 2:1 (2.21 eV)
- [ ] Vo donor states visible in gap for doped systems
- [ ] Check magnetization: `python3 check_magnetization.py` (expect ~0 if Sn 5s² lone pair)

---

## DFT Parameters

```
Functional:  PBEsol + DFT+U (Dudarev, lda_plus_u_kind=0 equivalent)
ecutwfc:     60 Ry   |   ecutrho: 480 Ry
K-points:    SCF 4×4×8   |   NSCF 8×8×12 (tetrahedron)
nbnd:        160 (SnO₂), adjust if Cholesky fails
```

### DFT+U values

| Material | Orbital | U (eV) |
|---|---|---|
| SnO₂ | Sn 4d | 4.0 |
| SnO₂ | O 2p | 0.0 |
| TiO₂ | Ti 3d | 4.2 |
| TiO₂ | O 2p | 0.0 |

> **Note:** U(O 2p)=0 in **both** materials is intentional — changing it shifts the VBM
> and invalidates the O 1s core-level band alignment. Sn 4d U is near-cosmetic for
> the gap (full 4d¹⁰ shell, ~20 eV deep); gap correction comes from scissor/HSE, not U.

### QE ≥7.2 HUBBARD card syntax (required for QE 7.3.1)

```fortran
HUBBARD (ortho-atomic)
  U Sn-4d 4.0
  U O-2p  0.0
```

Do **not** use the old `&SYSTEM` keywords (`lda_plus_u`, `Hubbard_U()`); they cause a
fatal `system_checkin` error in QE ≥7.2.

---

## Scissor Shift Reference

Fill in after running SCF/bands + `band_alignment.py`:

| System | Eg_exp (eV) | Eg_PBEsol+U (eV) | scissor shift (eV) |
|---|---|---|---|
| Pristine SnO₂ | ~3.60 | ___ | ___ |
| 1:1 (12.5% Vo) | 2.41 | ___ | ___ |
| 2:1 (18.75% Vo) | 2.21 | ___ | ___ |
| Pristine TiO₂ | ~3.00 | ___ | ___ |

> **Gap-in-CBM trap:** Fig 5 CBM = VBM(core-aligned) + Eg_corrected. Using the
> uncorrected PBEsol gap (~1 eV too small) can flip the Type-II/Z/S-scheme conclusion.
> Always use the experimental Tauc gap (or HSE) for CBM in the energy diagram.

---

## Expected Calculation Times (64 MPI, EPYC 7773X)

| Step | Pristine | 1:1 (2Vo) | 2:1 (3Vo) |
|---|---|---|---|
| vc-relax | ~20 min | ~1.5 hr | ~2 hr |
| SCF | ~5 min | ~20 min | ~30 min |
| NSCF | ~77 min* | ~2.5 hr | ~3.5 hr |
| Bands (pw.x) | ~30 min | ~1 hr | ~1.5 hr |
| bands.x | ~5 min | ~10 min | ~10 min |
| DOS+PDOS | ~15 min | ~40 min | ~1 hr |
| epsilon.x | ~20 min | ~50 min | ~1.5 hr |
| pp.x | ~5 min | ~10 min | ~10 min |

\* Benchmarked: 4608 s wall, 97.4% parallel efficiency, 3 GB / 473 GB RAM used.
NSCF bottleneck is CG diagonalization (180 avg iters/k-pt); hardware is not the limit.

For 4-core workstation, multiply by ~10–15×.

---

## Known Issues / Resolved Fixes

### FFT pencil decomposition (`-pd .true.` required)

Post-processing tools (`dos.x`, `projwfc.x`, `bands.x`, `epsilon.x`, `pp.x`) crash
with `fft_type_set (6): there are processes with no planes` when MPI ranks > FFT
z-planes. This cell has 45 z-planes; running 64 MPI ranks triggers it.

**Fix:** `-pd .true.` is pre-set in `run_all.sh` for all post-processing tools.
If you run manually, always add `-pd .true.` to these programs.

### NSCF Cholesky crash (`diagonalization='cg'` required)

Davidson diagonalization fails with `cdiaghg (227): problems computing cholesky` in
NSCF/bands when `nbnd=160 > 136` atomic wavefunctions, making S numerically singular.

**Fix:** all `*.nscf.in` and `*.bands.in` use `diagonalization = 'cg'`.
CG also uses `diago_cg_maxiter = 200` and `conv_thr = 1.0e-9` to avoid
`c_bands: N eigenvalues not converged` on tight thresholds.

### tmp/ symlink pattern

NSCF/bands/dos/optical/pp must use a **symlink**, not a real directory:

```bash
rm -rf tmp && ln -sfn ../scf/tmp tmp   # NSCF / bands / pp
rm -rf tmp && ln -sfn ../nscf/tmp tmp  # dos / optical
```

`mkdir -p tmp && ln -sfn ../scf/tmp/. tmp/` creates a real dir and breaks the link.
`run_all.sh` handles this correctly; only relevant for manual runs.

---

## Pseudopotential Sources

Primary (recommended): SSSP Precision v1.3 — <https://www.materialscloud.org/discover/sssp>

Alternative: PSlibrary 1.0.0 — <https://pseudopotentials.quantum-espresso.org>

Do NOT mix pseudopotentials from different libraries in the same calculation.

---

## Reference

If using these inputs in a publication, cite:

- Quantum ESPRESSO: Giannozzi et al., J. Phys.: Condens. Matter 21, 395502 (2009)
- DFT+U (Dudarev): Dudarev et al., Phys. Rev. B 57, 1505 (1998)
- SSSP pseudopotentials: Prandini et al., npj Comput. Mater. 4, 72 (2018)
