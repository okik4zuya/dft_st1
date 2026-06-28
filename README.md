# QE Input Files — SnO₂₋ₓ/TiO₂ DFT Study
## Oxygen Vacancy Concentration vs Band Gap

---

## System Overview

| Folder | System | Vo count | Vo% (DFT) | Vo% (exp) | Eg_exp (K-M) |
|---|---|---|---|---|---|
| `pristine/` | Stoichiometric SnO₂ | 0 | 0% | 0% | ~3.60 eV |
| `ratio_1to1/` | SnO₂₋ₓ (1:1 Sn²⁺:Sn⁴⁺) | 2 | 12.50% | 12.71% | **2.41 eV** |
| `ratio_2to1/` | SnO₂₋ₓ (2:1 Sn²⁺:Sn⁴⁺) | 3 | 18.75% | 17.64% | **2.21 eV** |

All supercells: **2×2×1 rutile SnO₂** (a=9.474 Å, b=9.474 Å, c=3.186 Å)

---

## Directory Structure

```
QE_SnO2_TiO2/
├── pseudo/                          ← PUT PSEUDOPOTENTIALS HERE
│   ├── Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF
│   └── O.pbesol-n-kjpaw_psl.1.0.0.UPF
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
├── ratio_1to1/                      ← 2 Vo, 12.50%, Eg=2.41 eV
│   ├── relax/   SnO2_1to1.relax.in
│   ├── scf/     SnO2_1to1.scf.in
│   ├── nscf/    SnO2_1to1.nscf.in
│   ├── bands/   SnO2_1to1.bands.in + bands_pp.in
│   ├── dos/     SnO2_1to1.dos.in + pdos.in
│   ├── optical/ SnO2_1to1.epsilon.in
│   └── pp/      SnO2_1to1.pp.in
│
├── ratio_2to1/                      ← 3 Vo, 18.75%, Eg=2.21 eV
│   ├── relax/   SnO2_2to1.relax.in
│   ├── scf/     SnO2_2to1.scf.in
│   ├── nscf/    SnO2_2to1.nscf.in
│   ├── bands/   SnO2_2to1.bands.in + bands_pp.in
│   ├── dos/     SnO2_2to1.dos.in + pdos.in
│   ├── optical/ SnO2_2to1.epsilon.in
│   └── pp/      SnO2_2to1.pp.in
│
└── run_all.sh                       ← Master run script
```

---

## Step-by-Step Workflow

### 0. Download pseudopotentials
```bash
# Download from: https://www.materialscloud.org/discover/sssp (Precision library)
# OR: https://pseudopotentials.quantum-espresso.org/legacy_tables/ps-library
mkdir -p pseudo
# Place in pseudo/:
#   Sn.pbesol-dn-kjpaw_psl.1.0.0.UPF
#   O.pbesol-n-kjpaw_psl.1.0.0.UPF
```

### 1. Run vc-relax (FIRST for every system)
```bash
cd pristine/relax && mkdir -p tmp
mpirun -np 4 pw.x -in SnO2_pristine.relax.in > SnO2_pristine.relax.out
```

### 2. Extract relaxed coordinates
```bash
# Extract final structure from relax output:
grep -A 999 "Begin final coordinates" SnO2_pristine.relax.out | \
    grep -B 999 "End final coordinates" > relaxed_coords.txt

# Update CELL_PARAMETERS and ATOMIC_POSITIONS in all subsequent .in files
# This step is MANDATORY before running SCF
```

### 3. Run SCF
```bash
cd ../scf && mkdir -p tmp
# Copy or symlink wavefunction files from relax:
cp -r ../relax/tmp ./
mpirun -np 4 pw.x -in SnO2_pristine.scf.in > SnO2_pristine.scf.out
```

### 4. Run NSCF (denser k-mesh)
```bash
cd ../nscf && mkdir -p tmp && cp -r ../scf/tmp ./
mpirun -np 4 pw.x -in SnO2_pristine.nscf.in > SnO2_pristine.nscf.out
```

### 5. Band structure
```bash
cd ../bands && mkdir -p tmp && cp -r ../scf/tmp ./
mpirun -np 4 pw.x    -in SnO2_pristine.bands.in    > SnO2_pristine.bands.out
mpirun -np 4 bands.x -in SnO2_pristine.bands_pp.in > SnO2_pristine.bands_pp.out
```

### 6. DOS and PDOS (uses NSCF tmp)
```bash
cd ../dos && mkdir -p tmp && cp -r ../nscf/tmp ./
mpirun -np 4 dos.x     -in SnO2_pristine.dos.in  > SnO2_pristine.dos.out
mpirun -np 4 projwfc.x -in SnO2_pristine.pdos.in > SnO2_pristine.pdos.out
```

### 7. Optical properties
```bash
# IMPORTANT: Read Eg_PBE+U from band structure output first, then set scissor shift
# grep "highest occupied" SnO2_pristine.scf.out
# grep "lowest unoccupied" SnO2_pristine.scf.out

cd ../optical && mkdir -p tmp && cp -r ../nscf/tmp ./
# Edit epsilon.in: set shift = Eg_exp - Eg_PBE+U
#   pristine: shift = 3.60 - Eg_PBE+U
#   1:1 sample: shift = 2.41 - Eg_PBE+U
#   2:1 sample: shift = 2.21 - Eg_PBE+U
mpirun -np 4 epsilon.x -in SnO2_pristine.epsilon.in > SnO2_pristine.epsilon.out
```

### 8. Charge density
```bash
cd ../pp && mkdir -p tmp && cp -r ../scf/tmp ./
mpirun -np 4 pp.x -in SnO2_pristine.pp.in > SnO2_pristine.pp.out
# Output: SnO2_pristine_charge.cube -> open in VESTA
```

---

## Critical Parameters to Check

### Before running any calculation:
- [ ] Pseudopotentials are in `pseudo/` directory
- [ ] ecutwfc convergence tested (40, 60, 80 Ry)
- [ ] k-point convergence tested for SCF
- [ ] vc-relax completed; relaxed coordinates extracted

### After vc-relax, before SCF:
- [ ] Forces < 0.01 eV/Å in relax output
- [ ] Stress < 0.5 kbar in relax output
- [ ] Updated ATOMIC_POSITIONS in scf/nscf/bands/dos/optical/pp inputs

### After SCF:
- [ ] SCF converged (check "convergence has been achieved" in output)
- [ ] Read Eg_PBE+U: grep "highest occupied" *.scf.out
- [ ] Calculate scissor shift for each system
- [ ] Update shift= in epsilon.in files

### After bands:
- [ ] Verify band gap visually matches expected trend:
      pristine > 1:1 (2.41 eV) > 2:1 (2.21 eV)
- [ ] Check Vo donor states appear in gap for doped systems

---

## Scissor Shift Reference

Fill in after running SCF/bands:

| System | Eg_exp (eV) | Eg_PBE+U (eV) | scissor shift (eV) |
|---|---|---|---|
| Pristine | ~3.60 | ___ | ___ |
| 1:1 (12.5% Vo) | 2.41 | ___ | ___ |
| 2:1 (18.75% Vo) | 2.21 | ___ | ___ |

---

## DFT+U Parameters

```
Hubbard_U(Sn 4d) = 4.0 eV   [Dudarev simplified]
Hubbard_U(O 2p)  = 0.0 eV

Literature range for Sn: 3.5 - 4.5 eV
Validate by reproducing Eg(pristine) ≈ 3.6 eV before studying Vo systems
```

---

## Pseudopotential Sources

Primary (recommended):
  SSSP Precision v1.3: https://www.materialscloud.org/discover/sssp

Alternative:
  PSlibrary 1.0.0: https://pseudopotentials.quantum-espresso.org

Do NOT mix pseudopotentials from different libraries in the same calculation.

---

## Expected Calculation Times (per system, 4 cores)

| Step | Pristine | 1:1 (2Vo) | 2:1 (3Vo) |
|---|---|---|---|
| vc-relax | ~30 min | ~2 hr | ~3 hr |
| SCF | ~10 min | ~30 min | ~45 min |
| NSCF | ~20 min | ~1 hr | ~1.5 hr |
| Bands | ~15 min | ~45 min | ~1 hr |
| DOS+PDOS | ~10 min | ~30 min | ~45 min |
| epsilon.x | ~15 min | ~45 min | ~1 hr |
| pp.x | ~5 min | ~10 min | ~10 min |

Times are approximate for a standard workstation. RunPod GPU instances with
more cores will be significantly faster.

---

## Post-Processing

After all calculations complete, run the Python post-processing scripts:
  1. plot_bands_dos.py       → Figure 1 (band structure + PDOS)
  2. plot_delta_rho.py       → Figure 2 (differential charge density, via VESTA)
  3. plot_optical.py         → Figure 3 (absorption spectra comparison)

---

## Reference

If using these inputs in a publication, cite:
  - Quantum ESPRESSO: Giannozzi et al., J. Phys.: Condens. Matter 21, 395502 (2009)
  - DFT+U (Dudarev): Dudarev et al., Phys. Rev. B 57, 1505 (1998)
  - SSSP pseudopotentials: Prandini et al., npj Comput. Mater. 4, 72 (2018)

---

## BLOCK B — TiO₂ Component (Added)

| Folder | System | nat | nspin | U (Ti 3d) |
|---|---|---|---|---|
| `TiO2/` | Pristine rutile TiO₂ | 24 (8Ti+16O) | 1 | 4.2 eV |

Supercell: 2×2×1 rutile TiO₂ (a=b=9.188 Å, c=2.959 Å)
Pseudopotential: Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF

```
TiO2/
├── relax/   TiO2_pristine.relax.in
├── scf/     TiO2_pristine.scf.in
├── nscf/    TiO2_pristine.nscf.in
├── bands/   TiO2_pristine.bands.in + bands_pp.in
├── dos/     TiO2_pristine.dos.in + pdos.in
├── optical/ TiO2_pristine.epsilon.in
└── pp/      TiO2_pristine.pp.in
```

---

## BLOCK C — Band Alignment Scripts (Added)

| Script | Purpose |
|---|---|
| `extract_dft_values.py` | Auto-reads QE outputs, extracts VBM/CBM/O1s/Fermi |
| `band_alignment.py` | Core-level alignment → energy diagram → mechanism ID |

### Workflow:
```bash
# Step 1: After all SCF + PDOS calculations complete
cd QE_SnO2_TiO2/
python extract_dft_values.py        # reads all outputs automatically

# Step 2: Copy printed values into band_alignment.py data section
# Step 3: Set DEMO_MODE = False in band_alignment.py
python band_alignment.py            # produces energy_diagram.png
```

### Additional pseudopotential needed for TiO₂:
```
Ti.pbesol-spn-kjpaw_psl.1.0.0.UPF
```
Download from: https://www.materialscloud.org/discover/sssp

---

## Complete System Summary

| System | Folder | nat | Vo% | Eg_exp |
|---|---|---|---|---|
| Pristine SnO₂ | `pristine/` | 24 | 0% | ~3.60 eV |
| SnO₂₋ₓ 1:1 | `ratio_1to1/` | 22 | 12.50% | 2.41 eV |
| SnO₂₋ₓ 2:1 | `ratio_2to1/` | 21 | 18.75% | 2.21 eV |
| Pristine TiO₂ | `TiO2/` | 24 | — | ~3.00 eV |
