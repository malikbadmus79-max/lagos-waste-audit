"""Active disposal sites and distance from each LGA (hypothesis H4).

Input: OpenStreetMap landfill features for the Lagos area, retrieved through the Overpass API on
4 October 2026 and stored unchanged in `data/raw/sites/osm_landfills.json` [S21].

Three disposal sites were reported as receiving waste in 2026: Olusosun (Ikeja) and Solous
(Igando, Alimosho), both at the end of their operating lives [S24], and Ewu-Elepe (Ikorodu) [S22].
Epe landfill was reported closed for conversion to a waste-to-energy facility [S23] and is not
included. Olusosun is named in OpenStreetMap; Solous and Ewu-Elepe are matched to the unnamed
landfill polygons nearest to Igando and Elepe [A11].

Distance is the straight-line distance from each LGA's representative point to the nearest active
site, in kilometres [A09].

Usage (from the repository root):

    python -m lagos_waste.sites
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from lagos_waste.geo import load_lagos_lgas
from lagos_waste.paths import DATA_PROCESSED, DATA_RAW

OSM_PATH = DATA_RAW / "sites" / "osm_landfills.json"
SITES_PATH = DATA_PROCESSED / "disposal_sites.csv"
DISTANCE_PATH = DATA_PROCESSED / "site_distance_by_lga.csv"
METRIC_CRS = 32631  # UTM zone 31N, metres

# Active disposal sites, keyed by OpenStreetMap way ID.
ACTIVE_SITES = {
    591626786: {"site": "Olusosun", "lga": "Ikeja", "status_2026": "operating, end of life", "source_id": "S21;S24",
                "match": "named in OpenStreetMap"},
    705802151: {"site": "Solous", "lga": "Alimosho", "status_2026": "operating, end of life", "source_id": "S21;S24",
                "match": "unnamed polygon nearest Igando [A11]"},
    785706979: {"site": "Ewu-Elepe", "lga": "Ikorodu", "status_2026": "operating", "source_id": "S21;S22",
                "match": "unnamed polygon nearest Elepe [A11]"},
}


def osm_points(data: dict) -> pd.DataFrame:
    """OSM elements as rows with id, name and centre coordinates."""
    rows = []
    for e in data["elements"]:
        centre = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        rows.append({"osm_id": e["id"], "osm_type": e["type"], "osm_name": e.get("tags", {}).get("name", ""),
                     "lat": centre["lat"], "lon": centre["lon"]})
    return pd.DataFrame(rows)


def active_sites(points: pd.DataFrame) -> pd.DataFrame:
    """The active disposal sites with coordinates; a missing OSM feature raises an error."""
    missing = set(ACTIVE_SITES) - set(points["osm_id"])
    if missing:
        raise ValueError(f"OSM features not found: {sorted(missing)}")
    sel = points[points["osm_id"].isin(ACTIVE_SITES)].copy()
    meta = pd.DataFrame.from_dict(ACTIVE_SITES, orient="index").rename_axis("osm_id").reset_index()
    out = meta.merge(sel, on="osm_id")
    out[["lat", "lon"]] = out[["lat", "lon"]].round(5)
    return out[["site", "lga", "status_2026", "lat", "lon", "osm_type", "osm_id", "osm_name", "match", "source_id"]]


def distance_to_nearest(lgas: gpd.GeoDataFrame, sites: pd.DataFrame) -> pd.DataFrame:
    """Straight-line km from each LGA's representative point to the nearest site, and which site."""
    pts = gpd.GeoDataFrame(sites, geometry=[Point(xy) for xy in zip(sites["lon"], sites["lat"])], crs=4326)
    pts = pts.to_crs(METRIC_CRS)
    centres = lgas.to_crs(METRIC_CRS).copy()
    centres["geometry"] = centres.geometry.representative_point()
    rows = []
    for _, row in centres.iterrows():
        d = pts.geometry.distance(row.geometry) / 1000
        i = d.idxmin()
        rows.append({"lga": row["lga"], "km_to_nearest_site": round(float(d[i]), 1),
                     "nearest_site": pts.loc[i, "site"]})
    return pd.DataFrame(rows)


def main(path: Path = OSM_PATH) -> None:
    """Write disposal_sites.csv and site_distance_by_lga.csv."""
    points = osm_points(json.loads(path.read_text(encoding="utf-8")))
    sites = active_sites(points)
    dist = distance_to_nearest(load_lagos_lgas(), sites)
    dist["source_id"] = "S16;S21"
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    sites.to_csv(SITES_PATH, index=False)
    dist.to_csv(DISTANCE_PATH, index=False)
    print(sites[["site", "lga", "lat", "lon"]].to_string(index=False))
    print(f"Wrote {SITES_PATH} and {DISTANCE_PATH}")


if __name__ == "__main__":
    main()
