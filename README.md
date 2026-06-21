# RPCA Hybrid Compression

An empirical comparative study of RPCA-family decomposition methods for surveillance video compression.

## Overview

This project evaluates and compares low-rank + sparse decomposition approaches for compressing surveillance video, with a focus on the VIRAT Ground dataset. The centerpiece contribution is a **hybrid method** that combines the temporally consistent background (L component) from Tensor RPCA with the sparse movement carrier (N component) from SS-RTD.

## Methods Compared

| Method | Description |
|---|---|
| Tensor RPCA | Low-rank tensor decomposition — best background separation |
| SS-RTD | Smooth+Sparse+Residual Tensor Decomposition — best sparse carrier |
| **Hybrid** | Tensor RPCA L + SS-RTD N *(main contribution)* |

## Dataset

[VIRAT Ground Dataset](https://viratdata.org/) — 58 surveillance videos processed at 320×180 grayscale, capped at 300 frames (12 seconds) per clip.

## Metrics

- PSNR and SSIM (reconstruction quality)
- Sparsity % of S/N components
- File size (KB) and compression ratio vs. original (H.264, CRF=23/28 via ffmpeg)

## Repository Structure

```
RPCA_Hybrid_Project/
├── src/                  # Core Python modules
│   ├── preprocessing.py  # Frame extraction and downsampling
│   ├── tensor_rpca.py    # Tensor RPCA implementation
│   ├── ssrtd.py          # SS-RTD implementation
│   ├── hybrid_encoder.py # Hybrid L+N encoder
│   ├── metrics.py        # PSNR, SSIM, compression metrics
│   └── video_registry.py # Dataset inventory builder
├── notebooks/            # Jupyter notebooks for analysis
├── figures/              # Plots and visualizations
├── paper/                # Manuscript drafts
├── data/                 # Processed frames (gitignored)
├── results/              # Decomposition outputs (gitignored)
└── logs/                 # Run logs (gitignored)
```

## Target Publication

IEEE Access / ICIP Workshop

## Author

**IlmunIslam** — [github.com/IlmunIslam](https://github.com/IlmunIslam)
