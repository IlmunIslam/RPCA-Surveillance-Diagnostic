# Baseline source paper

The algorithm this project takes as its baseline is **SS-RTD**, published as:

> B. Shen, R. R. Kamath, H. Choo, and Z. (James) Kong,
> "Robust Tensor Decomposition based Background/Foreground Separation in
> Noisy Videos and Its Applications in Additive Manufacturing,"
> *IEEE Transactions on Automation Science and Engineering*, 2022.
> DOI: [10.1109/TASE.2022.3163674](https://doi.org/10.1109/TASE.2022.3163674)

```bibtex
@article{shen2022ssrtd,
  author  = {Shen, Bo and Kamath, Rakesh R. and Choo, Hahn and Kong, Zhenyu (James)},
  title   = {Robust Tensor Decomposition based Background/Foreground Separation
             in Noisy Videos and Its Applications in Additive Manufacturing},
  journal = {IEEE Transactions on Automation Science and Engineering},
  year    = {2022},
  doi     = {10.1109/TASE.2022.3163674}
}
```

## Why the PDF is not in this repository

The PDF carries the notice `(c)2022 IEEE. Personal use is permitted, but
republication/redistribution requires IEEE permission.` This repository is
public, so the file is listed in `.gitignore` rather than committed. It is
kept in the working tree at the repository root under its full title, and can
be re-obtained from the DOI above.

## Method summary (for verification against our code)

Verified verbatim against the PDF on 2026-09-07. Section and equation numbers
refer to the published article.

- **Objective, eq. (5):** `min ||E||_1 + lambda * ||S||_TV1`
  subject to `X = L + S + E` and `L = G x1 U1 x2 U2 x3 U3`.
- **eq. (3):** `L` is a Tucker decomposition with rank `(r1, r2, r3)`,
  solved by **HOOI** (sub-problem eq. 8).
- **eq. (4):** `||S||_TV1` is the **anisotropic total variation** norm,
  the l1 norm of the stacked horizontal, vertical and temporal difference
  operators with periodic boundary conditions.
- **eq. (9):** `S` update, solved in closed form via 3D FFT.
- **eq. (11):** `f` update, soft-threshold at `lambda / beta_f`.
- **eq. (12):** `E` update, soft-threshold at `2 / beta_X`.
- **eqs. (13), (14):** multiplier updates with `gamma = 1.1`, and an
  **adaptive** conditional penalty scheme (`c1 = 1.15`, `c2 = 0.95`) --
  not a fixed geometric ramp.
- **Algorithm 1 initialization:** `r1 = ceil(0.8*H)`, `r2 = ceil(0.8*W)`,
  `r3 = 1`; `L` from `(r1,r2,r3)`-Tucker of `X`; `S = X - L`;
  `beta_f = 1e+1/mean(X)`, `beta_X = 4e-1/mean(X)`; all else `0`.
  Stopping: relative change in `E` below `1e-6`, or 100 iterations.
- **Tuning:** exactly **one** parameter, `lambda`, recommended range
  `[0.2, 1]` (Section III-C).

## Relationship to `src/ssrtd.py`

`src/ssrtd.py` does **not** implement the above and is not a variant of it: it
uses tensor SVT rather than Tucker/HOOI, has no total variation term, and has
two soft-threshold parameters instead of one `lambda`. See section 4, item 1 of
`RESEARCH_LOG.md`.
