"""Tests for lagos_waste.geo."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from lagos_waste import geo


def national() -> gpd.GeoDataFrame:
    """Twenty small Lagos squares plus a same-named LGA outside Lagos."""
    names = list(geo.GRID3_TO_LGA)
    shapes = [box(3.0 + 0.05 * i, 6.45, 3.04 + 0.05 * i, 6.49) for i in range(len(names))]
    names.append("Surulere")
    shapes.append(box(4.0, 8.0, 4.1, 8.1))  # Surulere, Oyo State
    return gpd.GeoDataFrame({"shapeName": names, "shapeID": range(len(names))}, geometry=shapes, crs=4326)


def test_lagos_lgas_selects_twenty_by_name_and_location() -> None:
    """The Oyo State Surulere is excluded and project names are applied."""
    out = geo.lagos_lgas(national())
    assert sorted(out["lga"]) == geo.LGAS and len(out) == 20
    assert "Ajeromi-Ifelodun" in set(out["lga"])


def test_lagos_lgas_rejects_missing_lga() -> None:
    """A boundary layer without all 20 LGAs is rejected."""
    with pytest.raises(ValueError):
        geo.lagos_lgas(national().iloc[1:])


def test_join_counts_fills_zero(tmp_path) -> None:
    """LGAs missing from the counts receive 0, and both map outputs are written."""
    lgas = geo.lagos_lgas(national())
    out = geo.join_counts(lgas, pd.DataFrame({"lga": ["Alimosho"], "n": [3]}), "n")
    assert out.set_index("lga").loc["Alimosho", "n"] == 3 and out["n"].sum() == 3
    geo.choropleth_png(out, "n", "t", "Articles", "Source: test", tmp_path / "m.png")
    geo.choropleth_html(out, "n", "Articles", "Source: test", tmp_path / "m.html")
    assert (tmp_path / "m.png").exists() and (tmp_path / "m.html").exists()


def test_boundary_file_holds_lagos() -> None:
    """The committed boundary file yields the 20 Lagos LGAs."""
    assert len(geo.load_lagos_lgas()) == 20
