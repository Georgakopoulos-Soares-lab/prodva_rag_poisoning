#!/usr/bin/env python
"""Figure 1 - Retrieval capture. (a) capture by attack and query phrasing; (b) how the
universal attack scales with hub budget, templated vs free-text. Reads runs/attack/summary_100.json."""
import sys, json, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from plotting.style import set_nature_style, nature_figsize, savefig, panel_label
from plotting import colors as C
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parents[1]
S = json.load(open(ROOT/"runs/attack/summary_100.json"))

def yerr(triple):
    r, lo, hi = triple
    return np.array([[r-lo], [hi-r]])

set_nature_style()
fig, (axa, axb) = plt.subplots(1, 2, figsize=nature_figsize("double", height=3.6),
                               gridspec_kw={"wspace": 0.30})

# ---- panel a: capture by attack x query phrasing ----
groups = ["Targeted\n(1 record)", "Universal\n(1500 hubs)"]
templ = [S["retrieval"]["templated"]["targeted_neardup"], S["retrieval"]["templated"]["universal_m1500"]]
free  = [S["retrieval"]["free_text"]["targeted_neardup"],  S["retrieval"]["free_text"]["universal_m1500"]]
x = np.arange(len(groups)); w = 0.36
axa.bar(x-w/2, [t[0] for t in templ], w, yerr=np.hstack([yerr(t) for t in templ]),
        color=C.QUERY_STYLE["templated"], label="Templated", error_kw=dict(lw=0.9, capsize=2))
axa.bar(x+w/2, [f[0] for f in free], w, yerr=np.hstack([yerr(f) for f in free]),
        color=C.QUERY_STYLE["free_text"], label="Free-text", error_kw=dict(lw=0.9, capsize=2))
axa.set_xticks(x); axa.set_xticklabels(groups)
axa.set_ylabel("Poison@16 (capture rate)"); axa.set_ylim(0, 1.05)
axa.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
           columnspacing=1.4, handlelength=1.2, borderaxespad=0.3)
rc = S["retrieval"]["templated"]["random_control"][0]
dt = S["retrieval"]["templated"]["targeted_distinct"][0]
panel_label(axa, "A.")

# ---- panel b: universal budget sweep ----
ms = S["ms"]
for style in ("templated", "free_text"):
    arr = np.array(S["sweep"][style])           # [m x (rate,lo,hi)]
    c = C.QUERY_STYLE[style]
    axb.plot(ms, arr[:, 0], "-o", color=c, label={"templated": "Templated", "free_text": "Free-text"}[style])
    axb.fill_between(ms, arr[:, 1], arr[:, 2], color=c, alpha=0.15, linewidth=0)
axb.set_xscale("log")
axb.set_xlabel("Hub budget, m (records)"); axb.set_ylabel("Universal-Poison@16")
axb.set_ylim(0, 1.05)
axb.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2,
           columnspacing=1.4, handlelength=1.2, borderaxespad=0.3)
panel_label(axb, "B.")

savefig(fig, ROOT/"figures/figure1_retrieval_capture")
print("wrote figures/figure1_retrieval_capture.{pdf,png}")
