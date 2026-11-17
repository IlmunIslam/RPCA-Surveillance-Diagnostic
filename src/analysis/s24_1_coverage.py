"""RESEARCH_LOG.md §24.1 -- annotation coverage, frame-index convention, resolution and box bounds.

Provenance: recovered verbatim from the Claude Code session transcript, where it ran
as an inline script at 2026-11-07 17:17-17:18 UTC. Only this header and the working-directory lines
were added; the four checks ran as separate commands and are concatenated in order, and an
all-180 bounds check is appended (marked ADDED). See RESEARCH_LOG.md section 28.

Run from the repo root:  python -m src.analysis.s24_1_coverage
"""
import os, sys
from pathlib import Path
PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))
# ---- original code below ----
import csv, re
from pathlib import Path
A=Path('data/annotations')
ann={p.name.replace('.viratdata.objects.txt','') for p in A.glob('*.objects.txt')}
reg=list(csv.DictReader(open('video_registry.csv',newline='',encoding='utf-8')))
print('annotation basenames:', len(ann), '| registry videos:', len(reg))
print('sample annotation names:', sorted(ann)[:3], '...', sorted(ann)[-3:])
stems={r['short_id']: r['original_filename'].replace('.mp4','') for r in reg}
exact=[k for k,v in stems.items() if v in ann]
print(f'EXACT filename matches: {len(exact)}/{len(reg)}')
# try prefix matching on the VIRAT_S_0XXXXX scene id
def scene(n): 
    m=re.match(r'(VIRAT_S_\d+)', n); return m.group(1) if m else None
ann_sc=collections={}
import collections as C
ann_sc=C.Counter(scene(a) for a in ann)
hit=0; miss=[]
for sid,st in stems.items():
    s=scene(st)
    if s in ann_sc: hit+=1
    else: miss.append((sid,st))
print(f'scene-id prefix matches: {hit}/{len(reg)}')
print('sample registry stems:', [stems[k] for k in list(stems)[:3]])
print('first 5 misses:', miss[:5])

print('\n' + '=' * 70)
import csv, collections
from pathlib import Path
A=Path('data/annotations')
reg=list(csv.DictReader(open('video_registry.csv',newline='',encoding='utf-8')))
stats=[]; types=collections.Counter(); empty=[]
for r in reg:
    f=A/(r['original_filename'].replace('.mp4','')+'.viratdata.objects.txt')
    frames=[]; n=0
    with open(f) as fh:
        for ln in fh:
            p=ln.split()
            if len(p)<8: continue
            n+=1; fr=int(p[2]); frames.append(fr); types[int(p[7])]+=1
    in300=sum(1 for x in frames if 0<=x<300)
    stats.append((r['short_id'], n, min(frames) if frames else None,
                  max(frames) if frames else None, in300, int(r['total_frames'])))
    if in300==0: empty.append(r['short_id'])
print(f'videos: {len(stats)}')
print(f'object-type histogram across all files: {dict(types)}')
rows_in300=[s[4] for s in stats]
print(f'\nannotation rows within frames 0-299:')
print(f'  videos with ZERO rows in 0-299: {len(empty)}  -> {empty[:12]}{"..." if len(empty)>12 else ""}')
import statistics as st
nz=[x for x in rows_in300 if x>0]
print(f'  videos with >=1 row: {len(nz)}')
if nz: print(f'  rows in-window: min {min(nz)} median {st.median(nz):.0f} max {max(nz)}')
mins=[s[2] for s in stats if s[2] is not None]
print(f'\nfirst annotated frame per video: min {min(mins)} median {st.median(mins):.0f} max {max(mins)}')
print(f'videos whose FIRST annotated frame is >= 300: {sum(1 for m in mins if m>=300)}')

print('\n' + '=' * 70)
import csv, collections
reg=list(csv.DictReader(open('video_registry.csv',newline='',encoding='utf-8')))
print('resolutions:', collections.Counter((r['width'],r['height']) for r in reg))
print('fps:', collections.Counter(r['fps'] for r in reg).most_common(3))
print('total_frames < 300:', [r['short_id'] for r in reg if int(r['total_frames'])<300])
import subprocess  # the original also grepped src/preprocessing.py for the resize geometry
print(open('src/preprocessing.py').read().splitlines()[20])

print('\n' + '=' * 70)
import csv
from pathlib import Path
A=Path('data/annotations')
reg=list(csv.DictReader(open('video_registry.csv',newline='',encoding='utf-8')))
bad=[]; oob=0; tot=0; neg=0
for r in reg[:40]:
    f=A/(r['original_filename'].replace('.mp4','')+'.viratdata.objects.txt')
    mx=0
    for ln in open(f):
        p=ln.split()
        if len(p)<8: continue
        fr=int(p[2]); mx=max(mx,fr)
        if fr<300:
            tot+=1
            x,y,w,h=map(int,p[3:7])
            if x<0 or y<0: neg+=1
            if x+w>1280 or y+h>720: oob+=1
    tf=int(r['total_frames'])
    if not (0.9*tf <= mx+1 <= 1.1*tf): bad.append((r['short_id'], mx, tf))
print(f'checked 40 videos: max_annotated_frame+1 vs total_frames mismatch: {len(bad)} {bad[:4]}')
print(f'rows in 0-299: {tot}; boxes extending past 1280x720: {oob} ({oob/tot*100:.2f}%); negative x or y: {neg} ({neg/tot*100:.2f}%)')

# ---- ADDED 2026-11-18 (RESEARCH_LOG.md section 28): the original check above covered
# only reg[:40]; section 24.1 reported "0 out of bounds" without that qualifier. This
# repeats the bounds check on all 180 videos.
oob = neg = tot = 0
for r in reg:
    f = A / (r['original_filename'].replace('.mp4', '') + '.viratdata.objects.txt')
    for ln in open(f):
        p = ln.split()
        if len(p) < 8 or int(p[2]) >= 300:
            continue
        tot += 1
        x, y, w, h = map(int, p[3:7])
        neg += x < 0 or y < 0
        oob += x + w > 1280 or y + h > 720
print(f'ALL 180: rows in 0-299: {tot}; past 1280x720: {oob}; negative x or y: {neg}')
