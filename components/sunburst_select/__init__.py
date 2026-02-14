"""
Streamlit component: Sunburst chart that sends the clicked slice id back to Python.
Each click includes a monotonic sequence number so the app can distinguish new clicks
from stale component values that Streamlit re-sends on every rerun.
"""
import json
import os

import streamlit.components.v1 as components

_RELEASE = True  # Use built frontend; set False and url="http://localhost:3001" for dev

if _RELEASE:
    _parent_dir = os.path.dirname(os.path.abspath(__file__))
    _build_dir = os.path.join(_parent_dir, "frontend", "build")
    _component_func = components.declare_component("sunburst_select", path=_build_dir)
else:
    _component_func = components.declare_component(
        "sunburst_select",
        url="http://localhost:3001",
    )


def sunburst_select(fig=None, plot_json=None, key=None, height=380):
    """Render a Plotly Sunburst and return (id, seq) of the clicked slice.

    Parameters
    ----------
    fig : plotly.graph_objects.Figure or None
        A Plotly figure containing a single Sunburst trace. Ignored if plot_json is set.
    plot_json : str or None
        Pre-serialized figure JSON.
    key : str or None
        Optional key for the component.
    height : int
        Height of the chart in pixels.

    Returns
    -------
    tuple[str | None, int | None]
        (id, seq) — the clicked slice id and a monotonic click counter.
        seq changes only on genuine user clicks; it stays the same across reruns.
        Returns (None, None) if no click has been received yet.
    """
    if plot_json is None and fig is not None:
        plot_json = fig.to_json()
    raw = _component_func(
        plot_obj=plot_json,
        height=height,
        key=key,
        default=None,
    )
    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data.get("id"), data.get("seq")
        except (json.JSONDecodeError, TypeError):
            return None, None
    if isinstance(raw, dict):
        return raw.get("id"), raw.get("seq")
    return None, None
