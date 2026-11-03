import io
import json
import html
import zipfile

import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
import plotly.express as px

from shapely.geometry import Polygon
from folium.plugins import MarkerCluster, HeatMap, Fullscreen, MiniMap
from streamlit_folium import st_folium


# ==================================================
# PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="City Web GIS Platform",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ==================================================
# CUSTOM DASHBOARD DESIGN
# ==================================================

st.markdown("""
<style>

[data-testid="stAppViewContainer"] {
    background: #f3f6fa;
    color: #17283e;
}

.block-container {
    padding: 0.7rem 1.1rem 1rem;
    max-width: 100%;
}

[data-testid="stSidebar"] {
    display: none;
}

h1, h2, h3 {
    color: #162b42;
}

.city-header {
    background: #14273d;
    color: white;
    border-radius: 12px;
    padding: 16px 22px;
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.city-header strong {
    font-size: 24px;
}

.city-header small {
    color: #b8c8d9;
}

.panel-heading {
    font-weight: 750;
    color: #18314b;
    font-size: 18px;
    margin-bottom: 10px;
}

.stat {
    background: white;
    border: 1px solid #e3eaf0;
    border-radius: 10px;
    padding: 12px;
    margin: 5px 0;
}

.stat-label {
    font-size: 12px;
    color: #60758a;
}

.stat-value {
    font-size: 23px;
    font-weight: 750;
    color: #1b3a54;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background: white;
    border-color: #e1e8ef;
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# HEADER
# ==================================================

st.markdown("""
<div class="city-header">
    <div>
        <strong>📍 City Web GIS Platform</strong>
        <br>
        <small>Smart decisions with spatial data</small>
    </div>
    <div>
        MAP EXPLORER &nbsp; • &nbsp; SPATIAL DASHBOARD
    </div>
</div>
""", unsafe_allow_html=True)


# ==================================================
# DEMONSTRATION GIS DATA
# ==================================================

@st.cache_data(show_spinner=False)
def demo_data():

    # Illustrative polygons near Dehradun.
    # These are NOT official geographic boundaries.

    lat0, lon0 = 30.3165, 78.0322

    categories = [
        "Residential",
        "Commercial",
        "Industrial",
        "Parks & Green",
        "Water Bodies"
    ]

    colors = {
        "Residential": "#f6cd58",
        "Commercial": "#f18491",
        "Industrial": "#b899e9",
        "Parks & Green": "#7ed59a",
        "Water Bodies": "#6db8ee"
    }

    rows = []

    for r in range(6):
        for c in range(8):

            lat = lat0 + (r - 3) * 0.012
            lon = lon0 + (c - 4) * 0.014

            cat = categories[
                (r * 7 + c * 3 + (r * c) % 4)
                % len(categories)
            ]

            poly = Polygon([
                (lon, lat),
                (lon + 0.012, lat),
                (lon + 0.012, lat + 0.010),
                (lon, lat + 0.010)
            ])

            rows.append({
                "zone": f"Zone {r+1}-{c+1}",
                "land_use": cat,
                "population": int(
                    350 + ((r * 53 + c * 97) % 1300)
                ),
                "geometry": poly
            })

    zones = gpd.GeoDataFrame(
        rows,
        geometry="geometry",
        crs="EPSG:4326"
    )

    pois = []

    for i in range(20):

        lat = lat0 + ((i * 7) % 35 - 17) * 0.002
        lon = lon0 + ((i * 11) % 45 - 22) * 0.002

        typ = [
            "Hospital",
            "School",
            "Transit"
        ][i % 3]

        pois.append({
            "name": f"Demo {typ} {i+1}",
            "type": typ,
            "latitude": lat,
            "longitude": lon
        })

    return zones, pd.DataFrame(pois), colors


# ==================================================
# DATA UPLOAD FUNCTION
# ==================================================

@st.cache_data(show_spinner=False)
def load_uploaded(name, content):

    lower = name.lower()

    if lower.endswith(".csv"):

        return pd.read_csv(
            io.BytesIO(content)
        ), None

    if lower.endswith(".xlsx"):

        return pd.read_excel(
            io.BytesIO(content)
        ), None

    if lower.endswith((".geojson", ".json")):

        obj = json.loads(
            content.decode("utf-8-sig")
        )

        if obj.get("type") == "Feature":

            obj = {
                "type": "FeatureCollection",
                "features": [obj]
            }

        if obj.get("type") != "FeatureCollection":

            raise ValueError(
                "Expected a GeoJSON FeatureCollection or Feature."
            )

        geo = gpd.GeoDataFrame.from_features(
            obj["features"],
            crs="EPSG:4326"
        )

        return geo.drop(
            columns="geometry"
        ), geo

    if lower.endswith(".zip"):

        with zipfile.ZipFile(
            io.BytesIO(content)
        ) as archive:

            names = archive.namelist()

            shp = [
                n for n in names
                if n.lower().endswith(".shp")
            ]

            if (
                len(shp) != 1
                or not any(
                    n.lower().endswith(".dbf")
                    for n in names
                )
                or not any(
                    n.lower().endswith(".shx")
                    for n in names
                )
            ):

                raise ValueError(
                    "ZIP must contain exactly one Shapefile "
                    "with .shp, .shx and .dbf files."
                )

            if any(
                n.startswith("/")
                or ".." in n.split("/")
                for n in names
            ):

                raise ValueError(
                    "Invalid ZIP file paths."
                )

        from geopandas import read_file
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as temp:

            archive_path = Path(temp) / "uploaded.zip"
            archive_path.write_bytes(content)

            geo = read_file(
                f"zip://{archive_path}!{shp[0]}"
            )

        return geo.drop(
            columns="geometry"
        ), geo

    raise ValueError("Unsupported file format")


# ==================================================
# THREE-COLUMN DASHBOARD LAYOUT
# ==================================================

left, center, right = st.columns(
    [1.05, 3.5, 1.15],
    gap="small"
)


# ==================================================
# LEFT PANEL: LAYER MANAGEMENT
# ==================================================

with left:

    with st.container(border=True):

        st.markdown(
            '<div class="panel-heading">Layers & Data</div>',
            unsafe_allow_html=True
        )

        uploaded = st.file_uploader(
            "Add GIS data",
            type=[
                "csv",
                "xlsx",
                "geojson",
                "json",
                "zip"
            ],
            help="ZIP must contain a complete Shapefile."
        )

        use_demo = st.checkbox(
            "Show illustrative city demo",
            value=uploaded is None
        )

        st.markdown("**Base map**")

        basemap = st.selectbox(
            "Basemap",
            [
                "OpenStreetMap",
                "CartoDB positron",
                "CartoDB dark_matter"
            ],
            label_visibility="collapsed"
        )

        st.markdown("**Layer visibility**")

        show_zones = st.checkbox(
            "Land-use / geographic polygons",
            True
        )

        show_points = st.checkbox(
            "Points of interest / locations",
            True
        )

        show_heat = st.checkbox(
            "Point density heatmap",
            False
        )

        cluster = st.checkbox(
            "Cluster markers",
            True
        )

        opacity = st.slider(
            "Polygon opacity",
            0.1,
            1.0,
            0.55,
            0.05
        )

        st.markdown("**Map tools**")

        show_minimap = st.checkbox(
            "Mini map",
            True
        )

        st.caption(
            "Uploaded data is processed for this session; "
            "it is not automatically saved to GitHub."
        )


# ==================================================
# PREPARE DATA
# ==================================================

zones = None
points = None
geo = None

source = "No dataset loaded"

colors = {
    "Residential": "#f6cd58",
    "Commercial": "#f18491",
    "Industrial": "#b899e9",
    "Parks & Green": "#7ed59a",
    "Water Bodies": "#6db8ee"
}

if uploaded is not None:

    try:

        tabular, geo = load_uploaded(
            uploaded.name,
            uploaded.getvalue()
        )

        source = uploaded.name

        if geo is not None:

            if geo.crs is None:

                st.warning(
                    "Uploaded geometry has no coordinate "
                    "reference system; assuming WGS84 "
                    "(EPSG:4326). Verify this assumption."
                )

                geo = geo.set_crs("EPSG:4326")

            geo = geo.to_crs("EPSG:4326")

            geo = geo[
                geo.geometry.notna()
                & ~geo.geometry.is_empty
            ].copy()

            zones = geo[
                geo.geometry.geom_type.isin([
                    "Polygon",
                    "MultiPolygon",
                    "LineString",
                    "MultiLineString"
                ])
            ].copy()

            point_geo = geo[
                geo.geometry.geom_type == "Point"
            ].copy()

            if not point_geo.empty:

                points = pd.DataFrame(
                    point_geo.drop(
                        columns="geometry"
                    )
                )

                points["latitude"] = (
                    point_geo.geometry.y.values
                )

                points["longitude"] = (
                    point_geo.geometry.x.values
                )

        else:

            points = tabular.copy()

        if use_demo:

            st.info(
                "Demonstration layers are hidden "
                "when a real file is uploaded."
            )

    except Exception as exc:

        st.error(
            f"Unable to read dataset: {exc}"
        )

        st.stop()

elif use_demo:

    zones, points, colors = demo_data()

    tabular = zones.drop(
        columns="geometry"
    )

    source = (
        "Illustrative demo — NOT official GIS data"
    )

else:

    tabular = pd.DataFrame()


# ==================================================
# ATTRIBUTE FILTERS
# ==================================================

with left:

    with st.container(border=True):

        st.markdown(
            '<div class="panel-heading">Attribute filters</div>',
            unsafe_allow_html=True
        )

        if len(tabular) > 0:

            candidates = [
                str(c)
                for c in tabular.columns
                if (
                    tabular[c].dtype == "object"
                    or str(tabular[c].dtype) == "category"
                )
            ]

            selected_field = st.selectbox(
                "Filter field",
                ["None"] + candidates
            )

            if selected_field != "None":

                opts = sorted(
                    tabular[selected_field]
                    .dropna()
                    .astype(str)
                    .unique()
                    .tolist()
                )

                selected_values = st.multiselect(
                    "Show values",
                    opts,
                    default=opts
                )

                mask = (
                    tabular[selected_field]
                    .astype(str)
                    .isin(selected_values)
                )

                tabular = tabular.loc[
                    mask
                ].copy()

                if (
                    zones is not None
                    and len(zones) > 0
                ):

                    zones = zones.loc[
                        zones.index.intersection(
                            tabular.index
                        )
                    ].copy()

                if (
                    points is not None
                    and geo is None
                ):

                    points = points.loc[
                        points.index.intersection(
                            tabular.index
                        )
                    ].copy()

        else:

            st.caption(
                "Upload data or enable the demo "
                "to filter attributes."
            )

        if (
            points is not None
            and len(points.columns) > 0
        ):

            cols = list(points.columns)

            def guess(aliases, default):

                return next(
                    (
                        c for c in cols
                        if str(c).strip().lower()
                        in aliases
                    ),
                    default
                )

            lat_guess = guess(
                {"latitude", "lat", "y"},
                cols[0]
            )

            lon_guess = guess(
                {"longitude", "lon", "lng", "long", "x"},
                cols[min(1, len(cols)-1)]
            )

            lat_col = st.selectbox(
                "Latitude column",
                cols,
                index=cols.index(lat_guess)
            )

            lon_col = st.selectbox(
                "Longitude column",
                cols,
                index=cols.index(lon_guess)
            )

            if lat_col == lon_col:

                st.warning(
                    "Choose two different coordinate columns."
                )

                points = points.iloc[
                    0:0
                ].copy()

            else:

                points = points.copy()

                points["__lat"] = pd.to_numeric(
                    points[lat_col],
                    errors="coerce"
                )

                points["__lon"] = pd.to_numeric(
                    points[lon_col],
                    errors="coerce"
                )

                points = points.loc[
                    points["__lat"].between(-90, 90)
                    & points["__lon"].between(-180, 180)
                ].copy()


# ==================================================
# INTERACTIVE MAP
# ==================================================

m = folium.Map(
    location=[30.3165, 78.0322],
    zoom_start=11,
    tiles=basemap,
    control_scale=True
)

Fullscreen().add_to(m)

if show_minimap:

    MiniMap(
        toggle_display=True
    ).add_to(m)

all_bounds = []


# ==================================================
# GEOGRAPHICAL ZONES
# ==================================================

if (
    zones is not None
    and not zones.empty
    and show_zones
):

    categories = (
        list(zones["land_use"].dropna().unique())
        if "land_use" in zones.columns
        else []
    )

    def style(feature):

        cat = (
            feature.get("properties", {})
            .get("land_use", "")
        )

        return {
            "fillColor": colors.get(
                cat,
                "#58a6d6"
            ),
            "color": "#42738b",
            "weight": 1.4,
            "fillOpacity": opacity
        }

    tip_cols = [
        str(c)
        for c in zones.columns
        if c != "geometry"
    ][:5]

    folium.GeoJson(
        zones.to_json(),
        name="Geographic zones",
        style_function=style,
        tooltip=(
            folium.GeoJsonTooltip(
                fields=tip_cols
            )
            if tip_cols
            else None
        )
    ).add_to(m)

    bounds = zones.total_bounds

    all_bounds.extend([
        [bounds[1], bounds[0]],
        [bounds[3], bounds[2]]
    ])


# ==================================================
# LOCATION MARKERS AND HEATMAP
# ==================================================

if (
    points is not None
    and not points.empty
):

    if show_points:

        fg = folium.FeatureGroup(
            name="Location markers"
        )

        target = (
            MarkerCluster().add_to(fg)
            if cluster
            else fg
        )

        for _, r in points.head(4000).iterrows():

            details = "<br>".join(
                f"<b>{html.escape(str(k))}</b>: "
                f"{html.escape(str(v)[:80])}"
                for k, v in r.items()
                if not str(k).startswith("__")
            )

            folium.Marker(
                [
                    r["__lat"],
                    r["__lon"]
                ],
                popup=folium.Popup(
                    details,
                    max_width=320
                )
            ).add_to(target)

        fg.add_to(m)

    if show_heat:

        HeatMap(
            points[
                ["__lat", "__lon"]
            ].values.tolist(),
            name="Point density",
            radius=16
        ).add_to(m)

    all_bounds.extend([
        [
            points["__lat"].min(),
            points["__lon"].min()
        ],
        [
            points["__lat"].max(),
            points["__lon"].max()
        ]
    ])


# ==================================================
# AUTOMATIC MAP ZOOM
# ==================================================

if all_bounds:

    latitudes = [
        p[0] for p in all_bounds
    ]

    longitudes = [
        p[1] for p in all_bounds
    ]

    if (
        min(latitudes) == max(latitudes)
        and min(longitudes) == max(longitudes)
    ):

        m.location = [
            latitudes[0],
            longitudes[0]
        ]

        m.zoom_start = 12

    else:

        m.fit_bounds([
            [
                min(latitudes),
                min(longitudes)
            ],
            [
                max(latitudes),
                max(longitudes)
            ]
        ])

folium.LayerControl(
    collapsed=False
).add_to(m)


# ==================================================
# CENTRE PANEL: MAP AND DATA TABLE
# ==================================================

with center:

    with st.container(border=True):

        st.markdown(
            '<div class="panel-heading">'
            'Interactive City Map'
            '</div>',
            unsafe_allow_html=True
        )

        st_folium(
            m,
            height=660,
            width=None,
            returned_objects=[],
            key="city_map"
        )

        st.caption(
            f"Data source: {source}. "
            "Demo zones and points are illustrative only."
        )

    with st.expander(
        "Attribute table and download",
        expanded=False
    ):

        st.dataframe(
            tabular,
            use_container_width=True
        )

        st.download_button(
            "Download filtered table (CSV)",
            tabular.to_csv(
                index=False
            ).encode("utf-8"),
            "gis_filtered_data.csv",
            "text/csv"
        )

        if (
            zones is not None
            and not zones.empty
        ):

            st.download_button(
                "Download geographic features (GeoJSON)",
                zones.to_json(),
                "gis_filtered_features.geojson",
                "application/geo+json"
            )


# ==================================================
# RIGHT PANEL: MAP INFORMATION
# ==================================================

with right:

    with st.container(border=True):

        st.markdown(
            '<div class="panel-heading">'
            'Map Info'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(source)

        st.markdown(
            f"""
            <div class="stat">
                <div class="stat-label">
                    Dataset records
                </div>
                <div class="stat-value">
                    {len(tabular):,}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="stat">
                <div class="stat-label">
                    Mapped point locations
                </div>
                <div class="stat-value">
                    {0 if points is None else len(points):,}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="stat">
                <div class="stat-label">
                    Geographic features
                </div>
                <div class="stat-value">
                    {0 if zones is None else len(zones):,}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            "**Category distribution**"
        )

        categorical = next(
            (
                c for c in [
                    "land_use",
                    "type",
                    "category"
                ]
                if c in tabular.columns
            ),
            None
        )

        if categorical is None:

            categorical = next(
                (
                    c for c in tabular.columns
                    if tabular[c].dtype == "object"
                ),
                None
            )

        if (
            categorical
            and not tabular.empty
        ):

            counts = (
                tabular[categorical]
                .fillna("Unknown")
                .astype(str)
                .value_counts()
                .head(10)
                .reset_index()
            )

            counts.columns = [
                "Category",
                "Count"
            ]

            fig = px.pie(
                counts,
                names="Category",
                values="Count",
                hole=0.55,
                color="Category",
                color_discrete_map=colors
            )

            fig.update_layout(
                margin=dict(
                    l=0,
                    r=0,
                    t=10,
                    b=0
                ),
                height=245,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    y=-0.15
                ),
                paper_bgcolor="rgba(0,0,0,0)"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        else:

            st.caption(
                "Upload categorical data "
                "to see a breakdown."
            )

        numeric = [
            c for c in
            tabular.select_dtypes(
                include="number"
            ).columns
            if not str(c).startswith("__")
        ]

        if numeric:

            metric = st.selectbox(
                "Numerical attribute",
                numeric
            )

            st.metric(
                f"Average {metric}",
                (
                    f"{tabular[metric].mean():,.2f}"
                    if tabular[metric].notna().any()
                    else "N/A"
                )
            )

            fig = px.histogram(
                tabular,
                x=metric,
                nbins=15
            )

            fig.update_layout(
                height=210,
                margin=dict(
                    l=0,
                    r=0,
                    t=10,
                    b=0
                ),
                paper_bgcolor="rgba(0,0,0,0)"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        st.caption(
            "For accurate area/population summaries, "
            "provide authoritative boundary "
            "and census datasets."
        )
