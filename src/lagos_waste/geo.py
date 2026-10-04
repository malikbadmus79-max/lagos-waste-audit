"""LGA boundaries for Lagos State and choropleth maps.

Boundaries are the GRID3 Nigeria LGA boundaries (2022), as redistributed by geoBoundaries
(gbOpen NGA ADM2, simplified) [S16]. The national file is kept unchanged in
`data/raw/boundaries/`; the 20 Lagos LGAs are selected here by name and location.
"""

from __future__ import annotations

from pathlib import Path

import folium
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from lagos_waste.charts import SURFACE, TEXT_PRIMARY, TEXT_SECONDARY  # noqa: E402
from lagos_waste.paths import DATA_RAW  # noqa: E402

BOUNDARY_PATH = DATA_RAW / "boundaries" / "geoBoundaries-NGA-ADM2_simplified.geojson"

# GRID3 spelling -> project spelling (the 20 constitutional LGAs of Lagos State).
GRID3_TO_LGA = {
    "Agege": "Agege",
    "Ajeromi/Ifelodun": "Ajeromi-Ifelodun",
    "Alimosho": "Alimosho",
    "Amuwo Odofin": "Amuwo-Odofin",
    "Apapa": "Apapa",
    "Badagry": "Badagry",
    "Epe": "Epe",
    "Eti Osa": "Eti-Osa",
    "Ibeju Lekki": "Ibeju-Lekki",
    "Ifako/Ijaye": "Ifako-Ijaiye",
    "Ikeja": "Ikeja",
    "Ikorodu": "Ikorodu",
    "Kosofe": "Kosofe",
    "Lagos Island": "Lagos Island",
    "Lagos Mainland": "Lagos Mainland",
    "Mushin": "Mushin",
    "Ojo": "Ojo",
    "Oshodi/Isolo": "Oshodi-Isolo",
    "Shomolu": "Shomolu",
    "Surulere": "Surulere",
}
LGAS = sorted(GRID3_TO_LGA.values())

# Lagos State lies within this box; it separates Lagos LGAs from same-named LGAs elsewhere
# (for example Surulere in Oyo State).
LAGOS_BOUNDS = (2.6, 6.3, 4.4, 6.75)  # min lon, min lat, max lon, max lat

# Sequential single-hue ramp (light to dark blue) for counts.
RAMP = LinearSegmentedColormap.from_list("counts", ["#e8f0fb", "#8db6ea", "#2a78d6", "#123f78"])
NO_DATA = "#efeeea"
EDGE = "#ffffff"


def lagos_lgas(boundaries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Select the 20 Lagos LGAs from a national boundary layer and add the project `lga` name."""
    min_lon, min_lat, max_lon, max_lat = LAGOS_BOUNDS
    pts = boundaries.geometry.representative_point()
    inside = pts.x.between(min_lon, max_lon) & pts.y.between(min_lat, max_lat)
    sel = boundaries[inside & boundaries["shapeName"].isin(GRID3_TO_LGA)].copy()
    sel["lga"] = sel["shapeName"].map(GRID3_TO_LGA)
    if sorted(sel["lga"]) != LGAS:
        missing = sorted(set(LGAS) - set(sel["lga"]))
        raise ValueError(f"Expected the 20 Lagos LGAs once each; missing or duplicated: {missing}")
    return sel[["lga", "shapeID", "geometry"]].sort_values("lga").reset_index(drop=True)


def load_lagos_lgas(path: Path = BOUNDARY_PATH) -> gpd.GeoDataFrame:
    """Read the national boundary file and return the 20 Lagos LGAs in WGS84."""
    return lagos_lgas(gpd.read_file(path).to_crs(4326))


def join_counts(lgas: gpd.GeoDataFrame, counts: pd.DataFrame, column: str) -> gpd.GeoDataFrame:
    """Attach a per-LGA value to the boundaries; LGAs without a value receive 0."""
    out = lgas.merge(counts[["lga", column]], on="lga", how="left")
    out[column] = out[column].fillna(0)
    return out


# Inset window for the dense central LGAs (min lon, min lat, max lon, max lat).
CORE_BOUNDS = (3.24, 6.41, 3.46, 6.68)
CORE_AREA_KM2 = 100.0  # LGAs smaller than this are labelled in the inset only
# Label shifts in degrees (lon, lat) on the full-state map, clear of disposal-site markers.
MAIN_LABEL_OFFSETS = {"Alimosho": (-0.035, 0.045), "Ikorodu": (0.06, 0.05)}
# Label shifts in degrees (lon, lat) in the inset where neighbouring labels would overlap.
LABEL_OFFSETS = {"Kosofe": (0.014, -0.012), "Oshodi-Isolo": (-0.012, 0.0), "Mushin": (-0.004, -0.006), "Shomolu": (0.012, 0.006), "Lagos Island": (0.022, 0.006),
                 "Apapa": (0.004, 0.0), "Ajeromi-Ifelodun": (-0.004, -0.012), "Lagos Mainland": (0.012, 0.0)}


def _draw(gdf: gpd.GeoDataFrame, column: str, vmax: float, ax: plt.Axes, label: pd.Series,
          offsets: dict[str, tuple[float, float]] | None = None) -> None:
    """Fill LGAs (zero in grey), outline them and write labels where `label` is True."""
    colours = [NO_DATA if pd.isna(v) or v <= 0 else matplotlib.colors.to_hex(RAMP(v / vmax)) for v in gdf[column]]
    gdf.plot(color=colours, edgecolor=EDGE, linewidth=0.8, ax=ax)
    for (_, row), show in zip(gdf.iterrows(), label):
        if not show:
            continue
        p = row.geometry.representative_point()
        dx, dy = (offsets or {}).get(row["lga"], (0.0, 0.0))
        value = "n/a" if pd.isna(row[column]) else f"{row[column]:g}"
        ax.annotate(f"{row['lga']}\n{value}", (p.x + dx, p.y + dy), ha="center", va="center", fontsize=6.5,
                    color=TEXT_PRIMARY, bbox={"boxstyle": "round,pad=0.15", "fc": SURFACE, "ec": "none", "alpha": 0.75})
    ax.set_axis_off()


def choropleth_png(
    gdf: gpd.GeoDataFrame, column: str, title: str, legend: str, source: str, path: Path | None = None,
    points: pd.DataFrame | None = None,
) -> Figure:
    """Static choropleth: full state with large LGAs labelled, and an inset of the central LGAs.

    LGAs with a value of 0 are drawn in grey, separate from the colour ramp.
    """
    vmax = max(float(gdf[column].max(skipna=True)), 1.0)
    area = gdf.to_crs(32631).area / 1e6
    small = area < CORE_AREA_KM2
    fig = plt.figure(figsize=(11, 6.4))
    fig.patch.set_facecolor(SURFACE)
    ax_main = fig.add_axes((0.01, 0.42, 0.98, 0.46))
    ax_core = fig.add_axes((0.28, 0.06, 0.44, 0.38))
    _draw(gdf, column, vmax, ax_main, ~small, MAIN_LABEL_OFFSETS if points is not None else None)
    _draw(gdf, column, vmax, ax_core, small, LABEL_OFFSETS)
    x0, y0, x1, y1 = CORE_BOUNDS
    ax_core.set_xlim(x0, x1)
    ax_core.set_ylim(y0, y1)
    ax_main.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], color=TEXT_SECONDARY, linewidth=0.8)
    ax_core.set_title("Central LGAs (box above)", fontsize=8, color=TEXT_SECONDARY)
    if points is not None:
        for ax in (ax_main, ax_core):
            ax.scatter(points["lon"], points["lat"], marker="^", s=46, color=TEXT_PRIMARY, edgecolor=SURFACE,
                       linewidth=0.8, zorder=5)
        fig.text(0.80, 0.035, "\u25b2 Active disposal site:\n" + ", ".join(points["site"]), fontsize=7,
                 color=TEXT_SECONDARY, va="bottom")
    cax = fig.add_axes((0.78, 0.12, 0.012, 0.25))
    sm = plt.cm.ScalarMappable(cmap=RAMP, norm=plt.Normalize(0, vmax))
    bar = fig.colorbar(sm, cax=cax)
    bar.set_label(legend, fontsize=8, color=TEXT_SECONDARY)
    bar.ax.tick_params(labelsize=7, colors=TEXT_SECONDARY)
    fig.text(0.80, 0.08, "Grey: zero or not available", fontsize=7, color=TEXT_SECONDARY)
    fig.suptitle(title, x=0.02, y=0.97, ha="left", fontsize=12, fontweight="bold", color=TEXT_PRIMARY)
    fig.text(0.02, 0.015, source, fontsize=7.5, color=TEXT_SECONDARY)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=200, facecolor=SURFACE)
    return fig


def choropleth_html(
    gdf: gpd.GeoDataFrame, column: str, legend: str, source: str, path: Path | None = None
) -> folium.Map:
    """Interactive choropleth with hover labels, saved as a standalone HTML file."""
    m = folium.Map(location=[6.55, 3.55], zoom_start=10, tiles="OpenStreetMap")
    vmax = max(float(gdf[column].max()), 1.0)

    def colour(value: float) -> str:
        if value <= 0:
            return NO_DATA
        return matplotlib.colors.to_hex(RAMP(value / vmax))

    data = gdf.copy()
    data["fill"] = data[column].map(colour)
    folium.GeoJson(
        data.to_json(),
        style_function=lambda f: {"fillColor": f["properties"]["fill"], "color": EDGE, "weight": 1,
                                  "fillOpacity": 0.85},
        tooltip=folium.GeoJsonTooltip(fields=["lga", column], aliases=["LGA", legend]),
    ).add_to(m)
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;bottom:12px;left:12px;z-index:9999;background:#fcfcfb;padding:6px 10px;'
        f'font:12px sans-serif;color:#52514e;border:1px solid #e4e3df">{legend}. {source}</div>'
    ))
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(path))
    return m
