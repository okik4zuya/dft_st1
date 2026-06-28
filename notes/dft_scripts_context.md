# Session Context — SnO₂₋ₓ/TiO₂ DFT Study (Quantum ESPRESSO)
 
## Research Overview
 
Manuscript study of **SnO₂₋ₓ/TiO₂ heterojunction photocatalysts**. Two samples were synthesized with different Sn²⁺:Sn⁴⁺ precursor ratios controlling oxygen vacancy (Vo) concentration. Experimental characterisation includes XRD, Raman, XPS, UV-Vis DRS + Kubelka-Munk, photocatalytic activity testing, and an energy diagram. DFT is used to determine the charge transfer mechanism (Type-II, Z-scheme, or S-scheme), which could not be resolved experimentally — making band alignment a **key result**, not supporting evidence.
 
---
 
## DFT Setup
 
| Parameter | Value |
|---|---|
| Software | Quantum ESPRESSO 7.3.1, RunPod Ubuntu 22.04 |
| Functional | PBEsol + DFT+U, Dudarev simplified (lda_plus_u_kind = 0) |
| U values | Sn 4d = 4.0 eV, Ti 3d = 4.2 eV, O 2p = 0.0 eV |
| Pseudopotentials | PAW PSlibrary: `Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF`, `O.pbesol-n-kjpaw_psl.1.0.0.UPF`, `Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF` |
| Supercell | 2×2×1 rutile SnO₂ (a=b=9.474 Å, c=3.186 Å) |
| ecutwfc / ecutrho | 60 Ry / 480 Ry |
| K-points SCF | 4×4×8 |
| K-points NSCF | 8×8×12 |
| nbnd | 160–200 (system-dependent) |
 
---
 
## Three-Block Calculation Strategy
 
```
Block A — SnO₂₋ₓ supercells     (inputs ready, currently running)
Block B — Pristine rutile TiO₂  (inputs ready, not yet run)
Block C — Band alignment         (O 1s core-level method, post-SCF)
```
 
---
 
## Four Systems and Their Parameters
 
| System | Folder | nat | nspin | Vo count | Vo% DFT | Vo% exp | Eg_exp |
|---|---|---|---|---|---|---|---|
| Pristine SnO₂ | `pristine/` | 24 (8Sn+16O) | 1 | 0 | 0% | 0% | ~3.60 eV |
| SnO₂₋ₓ 1:1 | `ratio_1to1/` | 22 (8Sn+14O) | 2 | 2 | 12.50% | 12.71% | **2.41 eV** |
| SnO₂₋ₓ 2:1 | `ratio_2to1/` | 21 (8Sn+13O) | 2 | 3 | 18.75% | 17.64% | **2.21 eV** |
| Pristine TiO₂ | `TiO2/` | 24 (8Ti+16O) | 1 | 0 | — | — | ~3.00 eV |
 
---
 
## Directory Structure
 
```
QE_SnO2_TiO2/
├── pseudo/                        ← Sn, O, Ti UPF files go here
├── pristine/
│   ├── relax/   SnO2_pristine.relax.in
│   ├── scf/     SnO2_pristine.scf.in
│   ├── nscf/    SnO2_pristine.nscf.in
│   ├── bands/   SnO2_pristine.bands.in + bands_pp.in
│   ├── dos/     SnO2_pristine.dos.in + pdos.in
│   ├── optical/ SnO2_pristine.epsilon.in
│   └── pp/      SnO2_pristine.pp.in
├── ratio_1to1/  (same structure, prefix=SnO2_1to1,  nat=22, nspin=2)
├── ratio_2to1/  (same structure, prefix=SnO2_2to1,  nat=21, nspin=2)
├── TiO2/        (same structure, prefix=TiO2_pristine, nat=24, nspin=1)
├── run_all.sh              ← master run script
├── extract_dft_values.py   ← reads QE outputs, extracts VBM/CBM/O1s/Fermi
├── band_alignment.py       ← O 1s core-level alignment → energy diagram → mechanism
└── postprocess/
    ├── plot_config.py          ← shared colours, RC params (imported by all)
    ├── fig1_bands_pdos.py      ← band structure + PDOS (1:1 and 2:1 side-by-side)
    ├── fig2_pdos_comparison.py ← stacked PDOS all 4 systems (needs CORE_SHIFT filled)
    ├── fig3_delta_rho.py       ← Δρ cube subtraction + 2D slice + VESTA guide
    ├── fig4_optical_absorption.py ← α(ω) all 4 systems + Tauc inset
    ├── fig5_energy_diagram.py  ← band alignment diagram (needs ALIGNED_VBM filled)
    └── run_figures.py          ← master runner, runs fig1–5 in sequence
```
 
---
 
## Per-System Calculation Chain
 
```
vc-relax → SCF → NSCF → bands.x → dos.x → projwfc.x → epsilon.x → pp.x
(pw.x)    (pw.x) (pw.x) (pw.x+   (dos.x) (projwfc.x) (epsilon.x) (pp.x)
                         bands.x)
```
 
Each step reads from the `tmp/` directory of the previous step. The `tmp/` symlink chain: `relax/tmp` → `scf/tmp` → `nscf/tmp` (NSCF and bands both read from SCF tmp; DOS/optical/pp read from NSCF tmp).
 
---
 
## Key Input Flags by System Type
 
**Pristine systems (nspin=1):**
```fortran
nspin = 1
! No starting_magnetization needed
mixing_beta = 0.4
mixing_mode = 'plain'
```
 
**Doped systems (nspin=2):**
```fortran
nspin = 2
starting_magnetization(1) = 0.5   ! Sn
starting_magnetization(2) = 0.0   ! O
mixing_beta = 0.3                  ! 1:1 sample
mixing_beta = 0.2                  ! 2:1 sample (more Vo = more oscillation risk)
mixing_mode = 'local-TF'
electron_maxstep = 300–400
```
 
**DFT+U block (all systems, QE ≤7.1 syntax):**
```fortran
lda_plus_u      = .true.
lda_plus_u_kind = 0
Hubbard_U(1)    = 4.0   ! Sn 4d  (or 4.2 for Ti 3d in TiO2)
Hubbard_U(2)    = 0.0   ! O 2p
```
 
**⚠ QE 7.2+ alternative syntax** (if lda_plus_u_kind causes error):
```fortran
! Remove lda_plus_u block from &SYSTEM entirely, add card:
HUBBARD (ortho-atomic)
  U Sn-4d 4.0
  U O-2p  0.0
```
 
---
 
## Post-Processing Workflow
 
```
1. All QE calculations complete
2. python extract_dft_values.py       → reads all .out files automatically
                                         prints VBM, CBM, Fermi, O 1s for each system
3. Copy printed values into band_alignment.py
   Set DEMO_MODE = False
4. python band_alignment.py           → prints scissor shifts + ALIGNED_VBM
                                         saves energy_diagram.png
5. Fill in three files:
   - each epsilon.in  → shift = Eg_exp - Eg_PBE+U
   - fig2_pdos_comparison.py → CORE_SHIFT dict
   - fig5_energy_diagram.py  → ALIGNED_VBM dict
6. Re-run epsilon.x for all 4 systems with scissor corrections
7. cd postprocess/ && python run_figures.py   → generates fig1–5
```
 
---
 
## Figures Planned
 
| Figure | Script | Content |
|---|---|---|
| Fig 1 | `fig1_bands_pdos.py` | Band structure + PDOS, 1:1 and 2:1 side-by-side |
| Fig 2 | `fig2_pdos_comparison.py` | Stacked PDOS all 4 systems, core-level aligned |
| Fig 3 | `fig3_delta_rho.py` | Δρ = ρ(doped) − ρ(pristine), 2D slice + VESTA cubes |
| Fig 4 | `fig4_optical_absorption.py` | α(ω) all 4 systems + Tauc inset |
| Fig 5 | `fig5_energy_diagram.py` | DFT band alignment → mechanism + NHE axis |
 
All scripts fall back to physically plausible **demo data** if QE output files are absent — figures render immediately for inspection.
 
---
 
## Active Issue: vc-relax Failure (Pristine SnO₂)
 
**Error:** `ERROR: vc-relax failed for pristine` — no output file inspected yet.
 
**Five most likely causes (ranked):**
 
1. **Pseudopotential not found** — `pseudo_dir = '../../../pseudo'` assumes execution from inside `pristine/relax/`. Verify with `ls pristine/relax/../../../pseudo/`
2. **`tmp/` directory missing** — must `mkdir -p pristine/relax/tmp` before running
3. **QE not in PATH** — `pw.x: command not found`; need `source ~/.bashrc` or `module load quantum-espresso`
4. **DFT+U syntax mismatch** — `lda_plus_u_kind` is deprecated in QE 7.2+; replace with `HUBBARD` card
5. **MPI rank count > irreducible k-points** — with 4×4×8 k-mesh and full symmetry, ~20–40 irreducible k-points; 64 MPI ranks may exceed this for the pristine system
 
**Diagnosis command (run on the server):**
```bash
grep -i "error\|Error\|stopping\|STOP" \
    QE_SnO2_TiO2/pristine/relax/SnO2_pristine.relax.out | tail -20
```
 
---
 
## Compute Environment
 
- **Platform:** RunPod Ubuntu 22.04 (same environment used for prior CFD/OpenFOAM work)
- **Target cores:** 64 MPI ranks
- **Estimated total wall time:** 18–28 h sequential; ~10 h if TiO₂/pristine run in parallel with doped systems
- **Storage needed:** ~72 GB raw; ~150 GB recommended with safety margin
- **Peak RAM:** ~128 GB (NSCF step with dense k-mesh)
- **Scripting conventions:** colour-coded output, `set -eo pipefail`, idempotent `.bashrc` checks, persistent volume at `/workspace`
 
---
 
## Key Design Decisions Made This Session
 
1. **Separate component modelling** (not full interface slab) — practical for a photocatalysis manuscript; full SnO₂/TiO₂ interface slab would require 100–200+ atoms and months of compute
2. **O 1s core-level alignment** chosen over ionisation potential method — works with bulk supercells, no vacuum slab needed
3. **2×2×1 supercell** chosen over 2×2×2 — gives 12.5% and 18.75% Vo concentrations that closely match experimental 12.71% and 17.64%; manuscript states the approximation explicitly
4. **Vo placement** — maximally separated configurations used; multiple configurations should be tested, lowest total energy used for production runs
5. **DFT band alignment is a primary result** — it determines the heterojunction mechanism (Type-II vs Z-scheme vs S-scheme), which cannot be inferred from experiment alone
   