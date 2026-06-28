#!/usr/bin/env python3
"""
run_figures.py
==============
Master script — generates all 5 manuscript figures in sequence.

Usage:
    cd QE_SnO2_TiO2/postprocess/
    python run_figures.py              # all figures
    python run_figures.py --fig 1 4   # specific figures only

Prerequisites:
    pip install numpy matplotlib scipy

Workflow:
    1. Run all QE calculations (see README.md)
    2. Run: python ../extract_dft_values.py
    3. Fill in values in ../band_alignment.py → set DEMO_MODE=False
    4. Run: python ../band_alignment.py
    5. Fill in ALIGNED_VBM in fig5_energy_diagram.py
    6. Fill in CORE_SHIFT in fig2_pdos_comparison.py
    7. Fill in scissor shifts in each epsilon.in
    8. Run: python run_figures.py

Outputs (all in postprocess/ directory):
    fig1_bands_pdos.png / .pdf
    fig2_pdos_comparison.png / .pdf
    fig3_delta_rho_slice.png / .pdf  + delta_rho_*.cube (open in VESTA)
    fig4_optical_absorption.png / .pdf
    fig5_energy_diagram.png / .pdf
"""

import sys, os, argparse, time, traceback

SCRIPTS = {
    1: ('fig1_bands_pdos.py',          'Band structure + PDOS'),
    2: ('fig2_pdos_comparison.py',     'PDOS comparison (all 4 systems)'),
    3: ('fig3_delta_rho.py',           'Differential charge density'),
    4: ('fig4_optical_absorption.py',  'Optical absorption α(ω)'),
    5: ('fig5_energy_diagram.py',      'Band alignment energy diagram'),
}

def run_figure(fig_num, script_name, description):
    print(f"\n{'='*60}")
    print(f"  Figure {fig_num}: {description}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        # Run in same directory as the script
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        with open(script_path) as f:
            code = f.read()
        exec(compile(code, script_path, 'exec'),
             {'__file__': script_path, '__name__': '__main__'})
        print(f"  ✓ Figure {fig_num} complete ({time.time()-t0:.1f}s)")
        return True
    except Exception as e:
        print(f"  ✗ Figure {fig_num} FAILED: {e}")
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate DFT manuscript figures')
    parser.add_argument('--fig', nargs='+', type=int,
                        help='Figure numbers to generate (default: all)')
    args = parser.parse_args()

    figs_to_run = args.fig if args.fig else list(SCRIPTS.keys())

    print("\n" + "="*60)
    print("  SnO₂₋ₓ/TiO₂  DFT Figure Generator")
    print("="*60)

    # Dependency check
    try:
        import numpy, matplotlib
        print(f"  numpy {numpy.__version__}  ✓")
        print(f"  matplotlib {matplotlib.__version__}  ✓")
    except ImportError as e:
        print(f"  Missing dependency: {e}")
        print("  Run: pip install numpy matplotlib scipy")
        sys.exit(1)

    # Status check for key files
    base = os.path.join(os.path.dirname(__file__), '..')
    checks = {
        'TiO2 SCF output'         : f'{base}/TiO2/scf/TiO2_pristine.scf.out',
        'SnO2 pristine SCF output': f'{base}/pristine/scf/SnO2_pristine.scf.out',
        '1:1 SCF output'          : f'{base}/ratio_1to1/scf/SnO2_1to1.scf.out',
        '2:1 SCF output'          : f'{base}/ratio_2to1/scf/SnO2_2to1.scf.out',
        '1:1 PDOS'                : f'{base}/ratio_1to1/dos/',
        '2:1 PDOS'                : f'{base}/ratio_2to1/dos/',
        '1:1 epsilon'             : f'{base}/ratio_1to1/optical/',
        '2:1 epsilon'             : f'{base}/ratio_2to1/optical/',
    }
    print("\n  DFT output file status:")
    any_missing = False
    for label, path in checks.items():
        exists = os.path.exists(path)
        status = '✓' if exists else '✗ MISSING'
        print(f"    {status}  {label}")
        if not exists:
            any_missing = True

    if any_missing:
        print("\n  ⚠  Some DFT outputs are missing.")
        print("  Scripts will use DEMO DATA for missing files.")
        print("  Figures will render but values are illustrative only.\n")
    else:
        print("\n  All DFT outputs found. Using real data.\n")

    # Run figures
    results = {}
    for fig_num in figs_to_run:
        if fig_num not in SCRIPTS:
            print(f"  WARNING: Figure {fig_num} not recognised (valid: 1-5)")
            continue
        script, desc = SCRIPTS[fig_num]
        results[fig_num] = run_figure(fig_num, script, desc)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for fig_num, success in results.items():
        icon = '✓' if success else '✗'
        print(f"  {icon}  Figure {fig_num}: {SCRIPTS[fig_num][1]}")

    out_dir = os.path.dirname(__file__)
    png_files = [f for f in os.listdir(out_dir) if f.endswith('.png')]
    pdf_files = [f for f in os.listdir(out_dir) if f.endswith('.pdf')]
    print(f"\n  Output directory: {out_dir}")
    print(f"  PNG files: {len(png_files)}")
    print(f"  PDF files: {len(pdf_files)}")

    if any(f.endswith('.cube') for f in os.listdir(out_dir)):
        print("\n  ⚠  VESTA files generated (delta_rho_*.cube):")
        print("  Open in VESTA for 3D isosurface rendering of Figure 3.")
        print("  See VESTA_rendering_guide.txt for step-by-step instructions.")

    print()

if __name__ == '__main__':
    main()
