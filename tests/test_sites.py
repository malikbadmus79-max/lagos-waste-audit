"""Tests for lagos_waste.sites."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from lagos_waste import sites

OSM = {"elements": [
    {"type": "way", "id": 591626786, "center": {"lat": 6.5945, "lon": 3.3769}, "tags": {"name": "Olushosun Landfill"}},
    {"type": "way", "id": 705802151, "center": {"lat": 6.5642, "lon": 3.2527}, "tags": {}},
    {"type": "way", "id": 785706979, "center": {"lat": 6.5994, "lon": 3.5803}, "tags": {}},
    {"type": "node", "id": 1, "lat": 6.5, "lon": 3.3, "tags": {"name": "Other"}},
]}


def test_active_sites_selects_three_named_sites() -> None:
    """Only the configured OSM features are kept, with site names attached."""
    out = sites.active_sites(sites.osm_points(OSM))
    assert sorted(out["site"]) == ["Ewu-Elepe", "Olusosun", "Solous"]
    assert out.set_index("site").loc["Olusosun", "lga"] == "Ikeja"


def test_missing_osm_feature_is_an_error() -> None:
    """A configured site absent from the OSM file stops the build."""
    data = {"elements": OSM["elements"][:2]}
    with pytest.raises(ValueError):
        sites.active_sites(sites.osm_points(data))


def test_distance_to_nearest_picks_closest_site() -> None:
    """A square around a site is 0 km from it; a distant square picks its own nearest site."""
    lgas = gpd.GeoDataFrame({"lga": ["Ikeja", "Far"]},
                            geometry=[box(3.37, 6.59, 3.38, 6.60), box(3.57, 6.59, 3.59, 6.61)], crs=4326)
    out = sites.distance_to_nearest(lgas, sites.active_sites(sites.osm_points(OSM))).set_index("lga")
    assert out.loc["Ikeja", "nearest_site"] == "Olusosun" and out.loc["Ikeja", "km_to_nearest_site"] < 1
    assert out.loc["Far", "nearest_site"] == "Ewu-Elepe"
