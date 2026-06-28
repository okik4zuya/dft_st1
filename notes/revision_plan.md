# Revision Plan — DFT+Hubbard Syntax Fix (QE ≥7.2)

## Root Cause

QE 7.2+ replaced the old `&SYSTEM`-namelist DFT+U keywords with a dedicated `HUBBARD` card.
The three old keywords are now **fatal** (not just deprecated):

```fortran
! OLD — causes system_checkin error in QE ≥7.2
lda_plus_u       = .true.
lda_plus_u_kind  = 0
Hubbard_U(1)     = 4.0
Hubbard_U(2)     = 0.0
```

The output confirms this:
```
WARNING!!! The input parameter lda_plus_u is obsolete.
WARNING!!! The input parameter lda_plus_u_kind is obsolete.
WARNING!!! The input parameter Hubbard_U is obsolete.
Error in routine  system_checkin (1):
stopping ...
```

---

## Scope

**16 input files** need to be updated (4 systems × 4 stages: relax, scf, nscf, bands).
The remaining `.in` files (dos, pdos, epsilon, pp, bands_pp) do **not** contain `lda_plus_u`
and require no changes.

### SnO₂ systems (U: Sn-4d = 4.0 eV, O-2p = 0.0 eV)

| File | Stage |
|---|---|
| `pristine/relax/SnO2_pristine.relax.in` | vc-relax |
| `pristine/scf/SnO2_pristine.scf.in` | SCF |
| `pristine/nscf/SnO2_pristine.nscf.in` | NSCF |
| `pristine/bands/SnO2_pristine.bands.in` | bands |
| `ratio_1to1/relax/SnO2_1to1.relax.in` | vc-relax |
| `ratio_1to1/scf/SnO2_1to1.scf.in` | SCF |
| `ratio_1to1/nscf/SnO2_1to1.nscf.in` | NSCF |
| `ratio_1to1/bands/SnO2_1to1.bands.in` | bands |
| `ratio_2to1/relax/SnO2_2to1.relax.in` | vc-relax |
| `ratio_2to1/scf/SnO2_2to1.scf.in` | SCF |
| `ratio_2to1/nscf/SnO2_2to1.nscf.in` | NSCF |
| `ratio_2to1/bands/SnO2_2to1.bands.in` | bands |

### TiO₂ system (U: Ti-3d = 4.2 eV, O-2p = 0.0 eV)

| File | Stage |
|---|---|
| `TiO2/relax/TiO2_pristine.relax.in` | vc-relax |
| `TiO2/scf/TiO2_pristine.scf.in` | SCF |
| `TiO2/nscf/TiO2_pristine.nscf.in` | NSCF |
| `TiO2/bands/TiO2_pristine.bands.in` | bands |

---

## Fix Per File

### Step 1 — Remove 3 lines from `&SYSTEM`

Delete these lines (exact text varies slightly per file but pattern is the same):

```fortran
  lda_plus_u       = .true.
  lda_plus_u_kind  = 0         ! Dudarev simplified (Ueff = U - J)
  Hubbard_U(1)     = 4.0       ! Sn 4d (eV)   ← value differs for TiO2
  Hubbard_U(2)     = 0.0       ! O 2p
```

### Step 2 — Append `HUBBARD` card at end of file (after `K_POINTS`)

**For all 12 SnO₂ files:**
```fortran
HUBBARD (ortho-atomic)
  U Sn-4d 4.0
  U O-2p  0.0
```

**For all 4 TiO₂ files:**
```fortran
HUBBARD (ortho-atomic)
  U Ti-3d 4.2
  U O-2p  0.0
```

The `(ortho-atomic)` projection matches the Dudarev simplified scheme (`lda_plus_u_kind = 0`)
from the old syntax and is the QE-recommended default.

---

## Execution Order

Apply the fix to all 16 files, then re-run:

```
1. Fix all 16 .in files (removes old U block, appends HUBBARD card)
2. On server: cd /quickpod/QE && bash run_all.sh
```

No other scripts or post-processing files are affected — `band_alignment.py`,
`extract_dft_values.py`, and all `postprocess/fig*.py` scripts are unchanged.

---

## Verification

After applying the fix, spot-check with:

```bash
# Should print only the new card, no old keywords
grep -rn "lda_plus_u\|Hubbard_U" QE_SnO2_TiO2/

# Should show HUBBARD card in all 16 files
grep -rl "HUBBARD" QE_SnO2_TiO2/ --include="*.in"
```

After re-running the first calculation (pristine relax), confirm success:
```bash
grep "bfgs converged\|Final enthalpy\|JOB DONE" \
    pristine/relax/SnO2_pristine.relax.out | tail -5
```

---

## Ready to Apply?

Say **"apply the fix"** and all 16 files will be patched automatically.
