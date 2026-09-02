"""Interactive slice viewer built from matplotlib widgets."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import RadioButtons, Slider

from .loader import Series
from .windowing import CT_PRESETS, apply_window, default_window, is_inverted


def _aspect(series: Series) -> float:
    """Display aspect ratio for an axial slice.

    Pixel Spacing is (row_mm, col_mm)
    """
    row_mm, col_mm = series.pixel_spacing
    return row_mm / col_mm


def show(series: Series) -> None:
    """Open the interactive viewer. Arrow keys or the slider change slices."""
    index = series.n_slices // 2
    ds = series.datasets[index]
    centre, width = default_window(ds, series.volume)
    invert = is_inverted(ds)

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.subplots_adjust(left=0.28, bottom=0.18, top=0.94)

    im = ax.imshow(
        apply_window(series.volume[index], centre, width, invert),
        cmap="gray", vmin=0, vmax=1, aspect=_aspect(series),
    )
    ax.set_xticks([])
    ax.set_yticks([])

    def title() -> str:
        depth = index * series.slice_spacing
        return (
            f"{series.modality}  {series.description}\n"
            f"slice {index + 1}/{series.n_slices}   {depth:.1f} mm into stack   "
            f"C {centre:.0f} / W {width:.0f} {series.units}"
        )

    ax.set_title(title(), fontsize=10)

    ax_slice = fig.add_axes([0.28, 0.10, 0.60, 0.03])
    ax_centre = fig.add_axes([0.28, 0.06, 0.60, 0.03])
    ax_width = fig.add_axes([0.28, 0.02, 0.60, 0.03])

    lo, hi = float(series.volume.min()), float(series.volume.max())
    s_slice = Slider(ax_slice, "slice", 0, series.n_slices - 1, valinit=index, valstep=1)
    s_centre = Slider(ax_centre, "centre", lo, hi, valinit=centre)
    s_width = Slider(ax_width, "width", 1, max(hi - lo, 2), valinit=width)

    ax_preset = fig.add_axes([0.02, 0.35, 0.20, 0.45])
    ax_preset.set_title("CT presets", fontsize=9)
    radio = RadioButtons(ax_preset, list(CT_PRESETS), active=None)

    def redraw() -> None:
        im.set_data(apply_window(series.volume[index], centre, width, invert))
        ax.set_title(title(), fontsize=10)
        fig.canvas.draw_idle()

    def on_slice(value) -> None:
        nonlocal index
        index = int(value)
        redraw()

    def on_window(_) -> None:
        nonlocal centre, width
        centre, width = s_centre.val, s_width.val
        redraw()

    def on_preset(label) -> None:
        c, w = CT_PRESETS[label]
        s_centre.set_val(c)   # triggers on_window
        s_width.set_val(w)

    def on_key(event) -> None:
        nonlocal index
        if event.key in ("up", "right"):
            index = min(index + 1, series.n_slices - 1)
        elif event.key in ("down", "left"):
            index = max(index - 1, 0)
        else:
            return
        s_slice.set_val(index)

    s_slice.on_changed(on_slice)
    s_centre.on_changed(on_window)
    s_width.on_changed(on_window)
    radio.on_clicked(on_preset)
    fig.canvas.mpl_connect("key_press_event", on_key)

    # Keep references alive; matplotlib widgets are garbage collected otherwise.
    fig._widgets = (s_slice, s_centre, s_width, radio)
    plt.show()


def save_window_comparison(
    series: Series,
    path: str,
    presets: tuple[str, ...] = ("lung", "soft tissue", "bone"),
    index: int | None = None,
) -> str:
    """Render one slice under several windows, side by side.

    """
    index = series.n_slices // 2 if index is None else index
    invert = is_inverted(series.datasets[0])
    image = series.volume[index]

    fig, axes = plt.subplots(1, len(presets), figsize=(4.2 * len(presets), 4.6))
    for ax, name in zip(np.atleast_1d(axes).ravel(), presets):
        centre, width = CT_PRESETS[name]
        ax.imshow(apply_window(image, centre, width, invert),
                  cmap="gray", vmin=0, vmax=1, aspect=_aspect(series))
        ax.set_title(f"{name}   C {centre:g} / W {width:g}", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])

    fig.suptitle(f"Slice {index + 1} of {series.n_slices}, same pixel data throughout")
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path


def save_montage(
    series: Series,
    path: str,
    n: int = 9,
    window: tuple[float, float] | None = None,
) -> str:
    """Write a grid of evenly spaced slices to a PNG.

    Works without a display, so it runs in CI and produces the screenshot for
    a README.
    """
    centre, width = window or default_window(series.datasets[0], series.volume)
    invert = is_inverted(series.datasets[0])

    n = min(n, series.n_slices)
    indices = np.linspace(0, series.n_slices - 1, n).astype(int)
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))

    fig, axes = plt.subplots(rows, cols, figsize=(3 * cols, 3 * rows))
    for ax, i in zip(np.atleast_1d(axes).ravel(), indices):
        ax.imshow(
            apply_window(series.volume[i], centre, width, invert),
            cmap="gray", vmin=0, vmax=1, aspect=_aspect(series),
        )
        ax.set_title(f"slice {i + 1}", fontsize=8)
    for ax in np.atleast_1d(axes).ravel()[n:]:
        ax.set_visible(False)
    for ax in np.atleast_1d(axes).ravel():
        ax.set_xticks([])
        ax.set_yticks([])

    fig.suptitle(
        f"{series.modality} {series.description}  |  "
        f"window C {centre:.0f} / W {width:.0f} {series.units}"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path
