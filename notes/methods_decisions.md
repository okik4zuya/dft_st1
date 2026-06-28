# Methods Decisions & Justifications — SnO₂₋ₓ/TiO₂ DFT Study

Reference for the methodological choices a reviewer will question. Keep the
manuscript Methods section consistent with this file.

---

## 1. Exchange–correlation functional: PBEsol (not PBE)

- **Choice:** PBEsol + DFT+U (Dudarev, `lda_plus_u_kind = 0`), PAW PSlibrary.
- **Why:** the physical argument rests on **lattice distortion** from oxygen
  vacancies. PBEsol restores the gradient expansion for solids and reproduces
  rutile SnO₂/TiO₂ lattice constants to ~0.5%, vs PBE's ~1–2% over-expansion.
  For a structural/distortion argument the better-geometry functional is the
  correct choice.
- **Known limitation:** PBEsol *underestimates* the band gap (more than PBE).
  This is **not** corrected by the functional; it is handled by an experimental
  scissor in the band-alignment and optical post-processing (see §3, §4).

## 2. DFT+U: which orbitals, and why Sn 4d is near-cosmetic

- **U values:** `U(Sn 4d) = 4.0 eV`, `U(Ti 3d) = 4.2 eV`, `U(O 2p) = 0 eV`,
  identical in every cell.
- **Sn 4d is semicore-cosmetic, NOT a gap/defect correction.** Sn⁴⁺ is
  [Kr]4d¹⁰5s⁰: the 4d shell is full and ~20 eV below the VBM. The SnO₂ gap is
  O 2p (VBM) → **Sn 5s** (CBM), and the vacancy donor electrons are Sn 5s-like.
  U on 4d shifts an inert filled band and does essentially nothing to the gap or
  the donor states. It is kept only for clean semicore PDOS and for parameter
  symmetry with TiO₂. **Do not describe it as a gap correction.**
- **No U on O 2p.** A U_p would lower/shift the VBM — and the VBM position is the
  core DFT-derived quantity in the band alignment. Tuning it to widen the gap
  would make the headline result depend on an arbitrary knob. `U(O 2p)=0` is
  also kept **identical in SnO₂ and TiO₂** so the O 1s core-level alignment uses
  a consistent oxygen reference in both materials.
- **Ti 3d U is genuinely essential** (Ti³⁺ d¹ localisation); cite the source for
  4.2 eV or compute it with `hp.x`.

## 3. Band alignment & the gap-in-CBM rule

- Method: O 1s core-level alignment (Van de Walle–Martin / Wei–Zunger). Implemented
  in `band_alignment.py`.
- **Rule:** `CBM_aligned = VBM_aligned + Eg_exp`. The CBM is built from the
  **experimental** gap, never the PBEsol gap. Using the underestimated PBEsol gap
  would push every CBM ~1 eV too low and can **flip the mechanism** (Type-II vs
  Z/S-scheme). Only the **VBM offset** is DFT-derived (from the core levels).
- The doped cells are near-metallic (CB filling), so their DFT "gap" is not a
  clean optical gap — see §4. `extract_dft_values.py` falls back to the E_F
  crossing for VBM/CBM there and prints a warning; only VBM_DFT is used downstream.

## 4. Optical vs fundamental gap, and Burstein–Moss

- The experimental Eg (3.60 → 2.41 → 2.21 eV) is from **UV-Vis / Tauc — an optical
  gap.** DFT yields a **fundamental** gap. State which quantity each number is.
- Self-doping fills the conduction-band bottom → **Burstein–Moss** *widens* the
  optical gap even as the fundamental gap narrows, and heavy Vo adds sub-gap
  defect-band absorption. When attributing the measured narrowing to distortion,
  acknowledge BM and the defect-tail contribution rather than equating
  DFT-fundamental with Tauc-optical.

## 5. Isolating the distortion contribution (supporting argument)

To support "self-doping distorts the lattice → gap narrows," the electronic and
structural effects are separated by three calculations per doped system:

| Cell | Geometry | Gives |
|---|---|---|
| pristine (relaxed) | relaxed | reference |
| doped, **unrelaxed** (`scf_unrelaxed/`) | ideal pristine coords, O removed | electronic-only |
| doped, **relaxed** (`scf/`) | vc-relaxed | total |

- `gap(pristine) − gap(unrelaxed)` = pure electronic effect of the vacancy.
- `gap(unrelaxed) − gap(relaxed)` = **distortion contribution**.

Distortion metrics (Sn–O bond distribution, SnO₆ distortion index, Δa/Δc/ΔV,
local Sn displacement around Vo) are computed by `distortion_analysis.py` and
correlated against the gap.

## 6. Spin treatment (under review)

Doped inputs use `nspin = 2, starting_magnetization(Sn) = 0.5`. This is **not yet
confirmed physical**: Sn²⁺ is a 5s² lone pair and the donor electrons likely
delocalise (zero net moment expected). Run `check_magnetization.py` on the
converged outputs; if |M_tot| ≈ 0, either document why nspin=2 is retained or
rerun non-spin-polarised.

## 7. Deferred: HSE06 anchor

A hybrid single-point anchor (`notes/hse_template.in`, coarse Fock q-grid) is
**not run** under the current budget. It is the recommended next step if a
reviewer challenges the PBEsol gap underestimation or the band-edge positions.
The argument currently relies on the experimental-gap scissor instead.
