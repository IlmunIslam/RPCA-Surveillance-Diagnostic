# RPCA Hybrid Compression Research

## Project Goal
Empirical comparative study of RPCA-family decomposition methods for surveillance 
video compression. Centerpiece contribution: a hybrid method combining Tensor RPCA's 
L component with SS-RTD's N component.

## Target Publication
IEEE Access or ICIP workshop paper.

## Dataset
180 VIRAT Ground 2.0 surveillance videos (videos-01 subset, scenes S_010000–S_010208)
Location: S:\works\Video compression Research\RPCA_Hybrid_Project\data\videos\
Short ID mapping: see video_registry.csv — 180 videos confirmed, all ≥300 frames, 1280×720 @ 23.97fps
Annotations: data\annotations\ — 343 .viratdata.objects.txt files covering all scenes

## Methods Being Compared
1. Tensor RPCA (Phase 2) — produces best L (temporally consistent background)
2. SS-RTD (Phase 3) — produces best N (sparse movement carrier)
3. Hybrid: Tensor RPCA L + SS-RTD N (main contribution)

## Key Technical Decisions
- Frame cap: 300 frames (12 sec) per video. Videos shorter than 300 frames 
  use their full length. Document per-video frame counts in results.
- Reconstruction: L + S for two-component methods, L + N for SS-RTD 
  (NOT L + S — this was a prior bug, N carries movement when S collapses to 0)
- Resolution: 320x180 grayscale (downsampled from original)
- Lambda Phase 1 & 2: 1/sqrt(max(height, width)) = 0.004167
- SS-RTD: lam_s=0.01, lam_n=0.001, smoothness penalty REMOVED. Parameter search on video_39 confirmed binary winner-takes-all behavior — lam_s > lam_n forces foreground into N component.
- Compression measurement: H.264 via ffmpeg, CRF=23 for reference, CRF=28 for components
- Metrics: PSNR, SSIM, sparsity %, file size (KB), compression ratio vs original

## Compute Architecture
- Local (Claude Code): file management, code writing, results analysis, figures
- Remote (Colab via MCP): heavy computation — Tensor RPCA, SS-RTD, hybrid

## Prior Work Done
- Phases 1-3 implemented and tested on Sample 1 (one VIRAT video, 150 frames)
- Bug identified: old runs used 150 frames → 6 sec output instead of 12 sec
- All old results are in S:\works\Video compression Research\RPCA_Project\ (backup, do not delete)
- New clean run starts from scratch in this project folder

## Current Status
Phase 1 complete. 180 official VIRAT Ground 2.0 videos ready. Annotations downloaded. Ready for pipeline execution.
