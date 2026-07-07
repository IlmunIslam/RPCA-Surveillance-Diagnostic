# RPCA Surveillance Diagnostic

A diagnostic and stability study of tensor RPCA-family decomposition on surveillance video.

## Overview

This is **not** a new compression method and **not** a comparative benchmark. It is a
diagnostic study of how RPCA-family low-rank + sparse tensor decompositions actually behave
on real surveillance footage, using the VIRAT Ground dataset.

The central finding is a **structural collapse**: SS-RTD's three-component decomposition
(smooth + sparse + residual) systematically degenerates to two components on surveillance
video. The foreground moves entirely into one component while the other collapses to
near-zero — in **all 180 videos**, with no middle ground. Which component wins is determined
by the **lambda parameter ratio**, not by scene content.

## Findings

- **Component collapse (main result).** SS-RTD's three-way split collapses to two on every
  one of the 180 videos: foreground concentrates in a single component, the other goes to
  near-zero. The winner is set by the lambda ratio (`lam_s` vs `lam_n`), independent of the
  scene.
- **Background compressibility (supporting).** Tensor RPCA's low-rank background compresses
  roughly **6.8% better than H.264** on 176/180 videos.
- **Hybrid recombination fails (negative result).** Recombining components does **not** beat
  H.264 on any video (0/180). This is reported as a negative result, not a contribution.

## Methods

Two decomposition methods are actually run and analyzed:

| Method | Description |
|---|---|
| Tensor RPCA | Low-rank tensor decomposition (background / foreground separation) |
| SS-RTD | Smooth + Sparse + Residual Tensor Decomposition |

Matrix RPCA and Chen (2012) are discussed as prior work but are **not** run in this study.

## Dataset

180 surveillance videos from **VIRAT Ground 2.0** (the `videos-01` subset), obtained from the
official Kitware source. All source clips are 1280×720. Each is capped at 300 frames and
processed at **320×180 grayscale**.

## Metrics

- PSNR and SSIM (reconstruction quality)
- Sparsity % of the sparse / residual components
- File size (KB) and compression ratio vs. H.264 (ffmpeg, CRF=23 reference / CRF=28 components)

## Repository Structure

```
RPCA_Hybrid_Project/
├── src/                  # Core Python modules
│   ├── preprocessing.py  # Frame extraction and downsampling
│   ├── tensor_rpca.py    # Tensor RPCA implementation
│   ├── ssrtd.py          # SS-RTD implementation
│   ├── hybrid_encoder.py # Component recombination (negative-result experiment)
│   ├── compression.py    # H.264 / ffmpeg compression measurement
│   ├── metrics.py        # PSNR, SSIM, sparsity, compression metrics
│   ├── param_sweep.py    # Lambda-ratio parameter sweep
│   ├── batch_runner.py   # Resumable batch driver over the 180-video set
│   └── video_registry.py # Dataset inventory builder
├── video_registry.csv    # 180-video inventory / short-ID mapping
├── data/                 # Processed frames (gitignored)
├── results/              # Decomposition outputs (gitignored)
└── logs/                 # Run logs (gitignored)
```

## Target Publication

IEEE Access

## Author

**IlmunIslam** — [github.com/IlmunIslam](https://github.com/IlmunIslam)
