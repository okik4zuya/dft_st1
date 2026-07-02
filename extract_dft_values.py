#!/usr/bin/env python3
"""
extract_dft_values.py
=====================
Reads QE output files and extracts all values needed for band_alignment.py.
Run this after all SCF, NSCF, bands, and PDOS calculations are complete.

Usage:
    python extract_dft_values.py

Outputs:
    - Prints a filled-in data dictionary ready to paste into band_alignment.py
    - Saves summary to dft_extracted_values.txt
"""

import os
import re
import glob
import json
import numpy as np

# =============================================================================
# CONFIGURATION — adjust paths if needed
# =============================================================================
BASE_DIR = '.'

SYSTEMS = {
    'TiO2': {
        'scf_out'  : 'TiO2/scf/TiO2_pristine.scf.out',
        'bands_out': 'TiO2/bands/TiO2_pristine.bands.out',
        'pdos_glob': 'TiO2/dos/TiO2_pristine_pdos.pdos_atm*O*wfc*s*',
        'Eg_exp'   : 3.00,
    },
    'SnO2_pristine': {
        'scf_out'  : 'pristine/scf/SnO2_pristine.scf.out',
        'bands_out': 'pristine/bands/SnO2_pristine.bands.out',
        'pdos_glob': 'pristine/dos/SnO2_pristine_pdos.pdos_atm*O*wfc*s*',
        'Eg_exp'   : 3.60,
    },
    'SnO2_1to1': {
        'scf_out'  : 'ratio_1to1/scf/SnO2_1to1.scf.out',
        'bands_out': 'ratio_1to1/bands/SnO2_1to1.bands.out',
        'pdos_glob': 'ratio_1to1/dos/SnO2_1to1_pdos.pdos_atm*O*wfc*s*',
        'Eg_exp'   : 2.41,
    },
    'SnO2_2to1': {
        'scf_out'  : 'ratio_2to1/scf/SnO2_2to1.scf.out',
        'bands_out': 'ratio_2to1/bands/SnO2_2to1.bands.out',
        'pdos_glob': 'ratio_2to1/dos/SnO2_2to1_pdos.pdos_atm*O*wfc*s*',
        'Eg_exp'   : 2.21,
    },
}

# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================

def extract_fermi(scf_out):
    """Extract Fermi energy from SCF output."""
    with open(scf_out) as f:
        content = f.read()
    match = re.search(r'the Fermi energy is\s+([-\d.]+)\s+ev', content, re.I)
    if match:
        return float(match.group(1))
    # fallback: highest occupied level
    match = re.search(r'highest occupied level\s*\(ev\):\s+([-\d.]+)', content, re.I)
    if match:
        return float(match.group(1))
    return None

def extract_vbm_cbm(scf_out, system_name=None):
    """
    Extract VBM (highest occupied) and CBM (lowest unoccupied) from SCF output.
    For spin-polarised systems, takes the spin-averaged value.

    QE only prints the 'highest occupied / lowest unoccupied level' line for
    insulators with fixed occupations. With smearing (the doped, near-metallic
    SnO2-x cells) that line is absent, so we fall back to locating the VBM/CBM
    from the printed Kohn-Sham eigenvalues straddling the Fermi level. In that
    regime the 'gap' is not a true optical gap (Burstein-Moss filling of the CB)
    and only VBM_DFT is meaningful for the core-level alignment.
    """
    with open(scf_out) as f:
        content = f.read()

    # --- Preferred: explicit highest-occupied / lowest-unoccupied line --------
    # For non-spin-polarised
    match = re.search(
        r'highest occupied.*?lowest unoccupied.*?level.*?:\s+([-\d.]+)\s+([-\d.]+)',
        content, re.I | re.S)
    if match:
        return float(match.group(1)), float(match.group(2))

    # For spin-polarised (two separate lines)
    matches = re.findall(
        r'highest occupied.*?lowest unoccupied.*?level.*?:\s+([-\d.]+)\s+([-\d.]+)',
        content, re.I)
    if len(matches) >= 2:
        vbm = max(float(m[0]) for m in matches)
        cbm = min(float(m[1]) for m in matches)
        return vbm, cbm

    # 'highest occupied level' alone (insulator, only VBM printed)
    match = re.search(r'highest occupied level\s*\(ev\):\s+([-\d.]+)', content, re.I)
    if match:
        return float(match.group(1)), None

    # --- Fallback: derive VBM/CBM from eigenvalues straddling E_F -------------
    E_F = extract_fermi(scf_out)
    if E_F is None:
        return None, None

    eigs = _parse_eigenvalues(content)
    if not eigs:
        return None, None

    below = [e for e in eigs if e <= E_F]
    above = [e for e in eigs if e > E_F]
    vbm = max(below) if below else None
    cbm = min(above) if above else None

    if system_name:
        print(f"  WARNING: {system_name} is degenerate/near-metallic — VBM/CBM "
              f"taken from E_F crossing; the resulting 'gap' is NOT a true optical "
              f"gap (Burstein-Moss). Only VBM_DFT is used for core-level alignment.")
    return vbm, cbm


def _parse_eigenvalues(content):
    """
    Collect all printed Kohn-Sham eigenvalues (eV) from a pw.x output.

    QE prints eigenvalues per k-point/spin as blocks following a 'bands (ev):'
    header: a blank line, then one or more rows of free-format floats, then a
    blank line. We skip the leading blank(s), gather the number rows, and stop
    at the trailing blank line that ends each block.
    """
    eigs = []
    for block in re.split(r'bands \(ev\):', content)[1:]:
        started = False
        for line in block.splitlines():
            nums = re.findall(r'[-+]?\d+\.\d+', line)
            if nums:
                started = True
                eigs.extend(float(x) for x in nums)
            elif started:
                # first non-number line after we began collecting ends the block
                break
            # else: leading blank line(s) before the data — keep skipping
    return eigs

def extract_o2s_reference(pdos_glob, fermi=None, deep_below_fermi=12.0):
    """
    Extract the deep O 2s peak position used as the internal alignment reference.

    NOTE ON NAMING: this is labelled "O 1s" elsewhere for historical reasons, but
    in a pseudopotential calculation the true O 1s is frozen in the core and never
    appears in the PDOS. The deepest O s-channel state present is O 2s (~18 eV
    below the VBM), a rigid, atomic-like level — a valid common reference for
    MacFarlane-style core-level band alignment.

    projwfc writes PDOS on the ABSOLUTE eV scale (same zero as the eigenvalues),
    so the O 2s peak sits near `E_Fermi - 19 eV`, NOT near -19 eV. We therefore
    locate it relative to the Fermi level (`energy - fermi < -deep_below_fermi`)
    and return its ABSOLUTE position, consistent with VBM_DFT / CBM_DFT.
    """
    files = glob.glob(pdos_glob)
    if not files:
        print(f"  WARNING: No PDOS files found matching {pdos_glob}")
        return None

    # Aggregate all O s-channel PDOS files onto a common energy grid
    all_energy = None
    total_dos  = None
    for f in files:
        try:
            raw = np.loadtxt(f, comments='#')
            if raw.ndim == 1:
                raw = raw.reshape(1, -1)

            energy = raw[:, 0]
            if raw.shape[1] == 3:
                # spin-polarised: col 1 = spin-up, col 2 = spin-down
                dos = raw[:, 1] + raw[:, 2]
            else:
                dos = raw[:, 1]

            if all_energy is None:
                all_energy = energy
                total_dos  = dos.copy()
            elif len(dos) == len(total_dos):
                total_dos += dos

        except Exception as e:
            print(f"  WARNING: Could not read {f}: {e}")
            continue

    if all_energy is None or total_dos is None:
        return None

    # Locate the deep O 2s peak. Reference to the Fermi level when available,
    # since projwfc energies are absolute; otherwise fall back to the raw axis.
    if fermi is not None:
        deep = all_energy < (fermi - deep_below_fermi)
        where = f"{deep_below_fermi:.0f} eV below E_Fermi ({fermi:.3f} eV)"
    else:
        deep = all_energy < -deep_below_fermi
        where = f"below -{deep_below_fermi:.0f} eV (no Fermi level given)"

    if not np.any(deep):
        print(f"  WARNING: no O s-states found {where}; "
              f"check Emin in pdos.in (needs ~-25 eV) and that projwfc ran")
        return None

    idx_peak = np.argmax(total_dos[deep])
    return float(all_energy[deep][idx_peak])

# =============================================================================
# MAIN EXTRACTION
# =============================================================================

def extract_all():
    extracted = {}
    lines = []

    print("\n" + "=" * 60)
    print("  DFT VALUE EXTRACTION")
    print("  Run from QE_SnO2_TiO2/ directory")
    print("=" * 60 + "\n")

    for sys, cfg in SYSTEMS.items():
        print(f"System: {sys}")
        result = {'Eg_exp': cfg['Eg_exp']}

        # SCF output
        scf_path = os.path.join(BASE_DIR, cfg['scf_out'])
        E_F = None
        if os.path.exists(scf_path):
            VBM, CBM = extract_vbm_cbm(scf_path, system_name=sys)
            E_F      = extract_fermi(scf_path)
            result['VBM_DFT'] = VBM
            result['CBM_DFT'] = CBM
            result['E_Fermi'] = E_F
            print(f"  Fermi energy (eV)  : {E_F}")
            print(f"  VBM (eV)           : {VBM}")
            print(f"  CBM (eV)           : {CBM}")
            if VBM and CBM:
                print(f"  Eg_PBE+U (eV)      : {CBM - VBM:.4f}")
                print(f"  Scissor shift (eV) : {cfg['Eg_exp'] - (CBM-VBM):+.4f}")
        else:
            print(f"  SCF output not found: {scf_path}")
            result['VBM_DFT'] = None
            result['CBM_DFT'] = None

        # PDOS — deep O 2s alignment reference (labelled "O1s_DFT" for the
        # downstream band_alignment.py data dict; see extract_o2s_reference).
        pdos_path = os.path.join(BASE_DIR, cfg['pdos_glob'])
        O2s = extract_o2s_reference(pdos_path, fermi=E_F)
        result['O1s_DFT'] = O2s
        print(f"  O 2s reference (eV): {O2s}")

        extracted[sys] = result
        print()

    # Print filled-in dictionary for band_alignment.py
    print("=" * 60)
    print("COPY THIS INTO band_alignment.py  (data section):")
    print("=" * 60)
    for sys, res in extracted.items():
        print(f"  '{sys}': {{")
        print(f"    'VBM_DFT' : {res.get('VBM_DFT')},")
        print(f"    'CBM_DFT' : {res.get('CBM_DFT')},")
        print(f"    'O1s_DFT' : {res.get('O1s_DFT')},")
        print(f"    'Eg_exp'  : {res.get('Eg_exp')},")
        print(f"  }},")

    # Save to file
    summary_path = os.path.join(BASE_DIR, 'dft_extracted_values.txt')
    with open(summary_path, 'w') as f:
        for sys, res in extracted.items():
            f.write(f"[{sys}]\n")
            for k, v in res.items():
                f.write(f"  {k} = {v}\n")
            f.write("\n")
    print(f"\nSummary saved to: {summary_path}")

    # Machine-readable JSON consumed by band_alignment.py (no manual copy-paste).
    json_path = os.path.join(BASE_DIR, 'dft_values.json')
    with open(json_path, 'w') as f:
        json.dump(extracted, f, indent=2)
    print(f"Machine-readable values: {json_path}")

    return extracted

if __name__ == '__main__':
    extract_all()
