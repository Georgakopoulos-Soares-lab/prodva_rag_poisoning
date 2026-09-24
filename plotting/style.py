"""Central Nature-style plotting configuration for the whole project.

Import and use these rather than setting rcParams / figure sizes per script:

    from plotting.style import set_nature_style, nature_figsize, savefig, panel_label

Changing this file restyles every figure. Priority: scientific correctness > clarity >
consistency > aesthetics.
"""
import pathlib
import matplotlib as mpl
import matplotlib.pyplot as plt


def set_nature_style():
    """Restrained, publication-quality defaults (Nature-family look)."""
    mpl.rcParams.update({
        # output quality
        "figure.dpi": 150,
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,       # editable/embedded text in PDF (TrueType)
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        # typography (sans-serif; Arial/Helvetica if present, else DejaVu Sans)
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        # clean axes: no top/right spines, thin lines, no grid
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.titlelocation": "left",
        # lines / markers / ticks
        "lines.linewidth": 1.2,
        "lines.markersize": 4,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.direction": "out",
        "ytick.direction": "out",
        # legend
        "legend.frameon": False,
        "legend.handlelength": 1.4,
        "legend.columnspacing": 1.0,
        "legend.labelspacing": 0.3,
    })


# approx manuscript column widths (inches)
_WIDTHS = {"single": 3.5, "medium": 5.0, "double": 7.2}


def nature_figsize(kind="single", height=None):
    """Figure size for a target column width; height chosen for the content if not given."""
    w = _WIDTHS.get(kind, 3.5)
    return (w, height if height is not None else w * 0.72)


def panel_label(ax, letter, x=-0.18, y=1.05):
    """Bold panel label ('a','b',...) placed consistently at the top-left of an axis."""
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=11, fontweight="bold",
            va="bottom", ha="right")


def savefig(fig, path):
    """Export a figure to both PDF (vector) and 600-DPI PNG, then close it."""
    stem = pathlib.Path(path).with_suffix("")
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{stem}.pdf")
    fig.savefig(f"{stem}.png", dpi=600)
    plt.close(fig)
    return f"{stem}.pdf", f"{stem}.png"
