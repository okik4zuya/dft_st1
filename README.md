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
│   ├── run.sh   ← per-system runner (no relax.out needed for post steps)
│   ├── relax/   SnO2_pristine.relax.in
│   ├── scf/     SnO2_pristine.scf.in
│   ├── nscf/    SnO2_pristine.nscf.in
│   ├── bands/   SnO2_pristine.bands.in + bands_pp.in
│   ├── dos/     SnO2_pristine.dos.in + pdos.in
│   ├── optical/ SnO2_pristine.epsilon.in
│   └── pp/      SnO2_pristine.pp.in
│
├── ratio_1to1/                      ← 2 Vo, 12.50%, Eg=2.41 eV (nspin=2)
│   ├── run.sh
│   ├── relax/   SnO2_1to1.relax.in
│   ├── scf/     SnO2_1to1.scf.in + scf_unrelaxed/  (distortion isolation)
│   ├── nscf/    SnO2_1to1.nscf.in
│   ├── bands/   SnO2_1to1.bands.in + bands_pp.in
│   ├── dos/     SnO2_1to1.dos.in + pdos.in
│   ├── optical/ SnO2_1to1.epsilon.in
│   └── pp/      SnO2_1to1.pp.in
│
├── ratio_2to1/                      ← 3 Vo, 18.75%, Eg=2.21 eV (nspin=2)
│   ├── run.sh
│   └── [same layout as ratio_1to1]
│
├── TiO2/                            ← pristine rutile TiO₂, U(Ti-3d)=4.2 eV
│   ├── run.sh
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
├── run_all.sh                       ← multi-system orchestrator (all systems at once)
├── run_lib.sh                       ← shared functions sourced by run_all.sh and run.sh
├── update_geometry.py               ← injects relaxed coords into scf/nscf/bands inputs
├── extract_dft_values.py            ← extracts VBM/CBM/O1s/Fermi from QE outputs
├── band_alignment.py                ← O 1s core-level alignment → energy diagram
├── check_magnetization.py           ← verify spin ansatz in doped cells
├── distortion_analysis.py           ← isolate distortion vs electronic gap contribution
└── progress.md                      ← timestamped run log (auto-written by scripts)
```

---

## Running Calculations

### Per-system scripts (recommended)

Each system folder has its own `run.sh`. Geometry injection is **not** a prerequisite
— run post steps directly against whatever coordinates are already in the input files.

```bash
# From inside any system folder:
bash run.sh            # full post pipeline: scf → nscf → bands → dos → optical → pp
bash run.sh scf        # SCF only
bash run.sh nscf       # NSCF only
bash run.sh bands      # band structure only
bash run.sh dos        # DOS + PDOS only
bash run.sh optical    # epsilon.x only
bash run.sh pp         # charge density only

# Relaxation and geometry injection (explicit):
bash run.sh relax      # vc-relax + auto-inject relaxed coords into scf/nscf/bands
bash run.sh inject     # inject only (from an existing relax.out)
```

Scripts are **idempotent**: each step checks for `JOB DONE` in the output file and
skips if already complete. Safe to stop and restart at any point.

### Multi-system orchestration (`run_all.sh`)

```bash
bash run_all.sh relax           # vc-relax + inject, all 4 systems, then STOP for review
bash run_all.sh post            # scf → pp, all 4 systems (no injection)
bash run_all.sh                 # full pipeline (relax + inject + post), all systems

bash run_all.sh relax pristine  # relax only, one system
bash run_all.sh post  ratio_1to1
```

### Resource overrides (both scripts)

```bash
NPROC=4             bash run.sh           # force 4 ranks (laptop)
OMP_NUM_THREADS=2   bash run.sh post      # hybrid: 32 MPI × 2 OMP
MEM_PER_RANK_MB=500 bash run_all.sh       # tighter RAM guard (larger cells)
NK_PW=4 NK_BANDS=2  bash run_all.sh       # manual k-pool pin
```

Both scripts auto-detect physical cores (not SMT threads), guard against OOM by
capping ranks at `AvailMem / MEM_PER_RANK_MB` (default 300 MB), and pick the
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

Post-processing turns the **raw QE outputs** (one set per system, produced by
`run.sh`) into the **5 manuscript figures**. It is not one script — it is three
layers, and the confusing part is the middle layer, where two helper scripts
distill the raw outputs into a few numbers that you then **paste by hand** into
the figure scripts.

### The three layers

```text
  LAYER A — raw QE outputs            LAYER B — extract & align         LAYER C — figures
  (run.sh, per system)                (numbers you paste forward)       (postprocess/)

  scf/*.scf.out      ─ Fermi, VBM ┐
  bands/*_bands.dat  ─ band path  ├─►  extract_dft_values.py            fig1_bands_pdos.py
  bands/*.bands.out  ─ CBM        │      └─ writes dft_extracted_       fig2_pdos_comparison.py
  dos/*.pdos_atm*    ─ PDOS, O 1s ┘         values.txt (VBM/CBM/        fig3_delta_rho.py
  pp/*_charge.cube   ─ charge density        O1s/Fermi per system)      fig4_optical_absorption.py
  optical/epsilon_*.dat ─ ε(ω)            ▼                             fig5_energy_diagram.py
                                       band_alignment.py                       ▲
                                          └─ prints scissor shifts,      run_figures.py
                                             CORE_SHIFT, ALIGNED_VBM ────┘  (runs all 5)
```

- **Layer A** is everything `run.sh` produces. Each figure needs only *some* of
  these steps (see the table below) — you do **not** need the full pipeline to
  make every figure.
- **Layer B** are two scripts that read Layer A and emit *numbers*, not figures:
  - `extract_dft_values.py` — greps VBM / CBM / O 1s / Fermi from the outputs
    into `dft_extracted_values.txt` (and prints a dict to paste into the next
    script). Currently all `None` because the calculations haven't been run yet.
  - `band_alignment.py` — takes those numbers, does the O 1s core-level
    alignment, and prints the **scissor shifts**, the fig2 `CORE_SHIFT` dict,
    and the fig5 `ALIGNED_VBM` dict. It also emits the energy diagram itself.
- **Layer C** are the 5 figure scripts. fig1 and fig3 read Layer A directly;
  **fig2, fig4, fig5 need values from Layer B pasted in first** (that is the
  manual step that makes this feel non-obvious).

### Which figure needs which calculation step

| Fig | Content | Calc steps required | Manual numbers to paste in first |
| --- | --- | --- | --- |
| **1** | Band structure + PDOS (1:1, 2:1) | `bands` + `dos` (+`scf` Fermi) | none — reads outputs directly |
| **2** | Stacked PDOS, all 4 systems | `dos` (+`scf`) | `CORE_SHIFT` dict (from `band_alignment.py`) |
| **3** | Δρ charge-density cube + slice | `pp` | none — subtracts the `.cube` files |
| **4** | α(ω) + Tauc inset | `optical` (NC branch) | scissor `shift` set in each `epsilon.in` |
| **5** | Band-alignment energy diagram | `scf` + `bands` + `dos` | `ALIGNED_VBM` dict (from `band_alignment.py`) |

> **Stop after `dos` →** you can make **fig1, fig2, fig5** (fig2/fig5 after the
> Layer-B paste step). **fig3** additionally needs `pp`; **fig4** needs the
> `optical` step.

### Order of operations

```bash
# 1. Extract numbers from the raw outputs (run from repo root)
python3 extract_dft_values.py          # → dft_extracted_values.txt + printed dict

# 2. Paste that dict into band_alignment.py's data section, set DEMO_MODE = False,
#    then run it. It prints scissor shifts + CORE_SHIFT + ALIGNED_VBM and draws fig5's diagram.
python3 band_alignment.py

# 3a. (fig4 only) put each system's scissor `shift` into its optical/*.epsilon.in,
#     then redo the optical step so ε(ω) reflects the corrected gap:
cd pristine && bash run.sh optical && cd ..
# 3b. (fig2) paste CORE_SHIFT dict into fig2_pdos_comparison.py
# 3c. (fig5) paste ALIGNED_VBM dict into fig5_energy_diagram.py

# 4. Generate all 5 figures (skips/uses demo data for any missing inputs)
cd postprocess/ && python3 run_figures.py
```

> **Demo-data caveat:** every `figN_*.py` (and `band_alignment.py` via
> `DEMO_MODE`) falls back to **synthetic placeholder data** when its QE inputs
> are missing, so a script "succeeding" does **not** mean the figure is real.
> A real figure requires both (a) the calculation steps in the table above and
> (b) the manual paste steps for fig2/4/5. Check the script's stdout — it warns
> when it used demo data.

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

**Fix:** `-pd .true.` is pre-set in `run_lib.sh` for all post-processing tools
(used by both `run.sh` and `run_all.sh`). If you run manually, always add
`-pd .true.` to these programs.

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
`run_lib.sh` handles this correctly in both `run.sh` and `run_all.sh`; only relevant for manual runs.

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
