#!/usr/bin/env python
"""Figure 2 - Downstream effect, conditional on capture. (a) protein changes vs the clean run;
(b) protein acquires the payload's benign domain (gain of function). Clean baseline is 0 in
every arm. Reads runs/attack/summary_100.json."""
import sys, json, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from plotting.style import set_nature_style, nature_figsize, savefig, panel_label
from plotting import colors as C
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
S = json.load(open(ROOT/"runs/attack/summary_100.json"))
D = S["downstream"]

ARMS = [("neardup_templated", "Targeted\n(templated)"),
        ("neardup_freetext",  "Targeted\n(free-text)"),
        ("universal_freetext", "Universal\n(free-text)")]
ARMS = [a for a in ARMS if a[0] in D]
cols = [C.E2E[k] for k, _ in ARMS]
x = np.arange(len(ARMS))

def yerr(triple):
    r, lo, hi = triple
    return np.array([[r-lo], [hi-r]])

set_nature_style()
fig, (axa, axb) = plt.subplots(1, 2, figsize=nature_figsize("double", height=3.6),
                               gridspec_kw={"wspace": 0.30})

for ax, metric, ylab, letter in [(axa, "change", "Change from clean | captured", "A."),
                                 (axb, "gof", "Gain of function | captured", "B.")]:
    vals = [D[k][metric] for k, _ in ARMS]
    ax.bar(x, [v[0] for v in vals], 0.6, color=cols,
           yerr=np.hstack([yerr(v) for v in vals]), error_kw=dict(lw=0.9, capsize=2))
    ax.set_xticks(x); ax.set_xticklabels([lab for _, lab in ARMS])
    ax.set_ylabel(ylab); ax.set_ylim(0, 1.0)
    panel_label(ax, letter)

savefig(fig, ROOT/"figures/figure2_downstream_effect")
print("wrote figures/figure2_downstream_effect.{pdf,png}")
