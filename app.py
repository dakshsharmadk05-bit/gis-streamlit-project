
import json
import pandas as pd
import streamlit as st
import folium
from folium.plugins import MarkerCluster, Fullscreen, MiniMap
from streamlit_folium import st_folium

st.set_page_config(
    page_title="GeoScope",
    page_icon="🌍",
    layout="wide"
)

st.title("GeoScope")
st.caption("Interactive geospatial mapping and data analysis")

# Sidebar
st.sidebar.header("Data Management")

uploaded_file = st.sidebar.file_uploader(
    "Upload your dataset",
    type=["csv", "xlsx", "geojson", "json"]
)

map_style = st.sidebar.selectbox(
    "Map style",
    ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"]
)

show_clusters = st.sidebar.checkbox(
    "Cluster location markers", value=True
)

if uploaded_file is None:
    st.info("Upload a CSV, Excel, or GeoJSON file to begin.")
    st.stop()

# Read uploaded data
try:
    filename = uploaded_file.name.lower()
    geojson_data = None

    if filename.endswith(".csv"):
        df = pd.read_csv(uploaded_file)

    elif filename.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)

    else:
        geojson_data = json.load(uploaded_file)

        features = geojson_data.get("features", [])
        df = pd.DataFrame([
            feature.get("properties") or {}
            for feature in features
        ])

except Exception as e:
    st.error(f"Unable to read file: {e}")
    st.stop()

st.success("Dataset loaded successfully!")

# Summary
a, b, c = st.columns(3)
a.metric("Total Records", len(df))
b.metric("Total Attributes", len(df.columns))
c.metric("Dataset Type", filename.split(".")[-1].upper())

st.divider()

# Attribute filtering
filtered_df = df.copy()

if not df.empty:
    filter_column = st.sidebar.selectbox(
        "Filter by attribute",
        ["None"] + list(df.columns)
    )

    if filter_column != "None":
        values = df[filter_column].dropna().unique().tolist()
        values = sorted(values, key=str)

        selected = st.sidebar.multiselect(
            "Select values",
            values,
            default=values[:20]
        )

        filtered_df = df[
            df[filter_column].isin(selected)
        ].copy()

# Initialize map
m = folium.Map(
    location=[20.5937, 78.9629],
    zoom_start=5,
    tiles=map_style,
    control_scale=True
)

Fullscreen().add_to(m)
MiniMap(toggle_display=True).add_to(m)

if geojson_data is not None:
    # Keep only features whose attributes match filtered rows
    allowed = set(filtered_df.index)

    selected_features = [
        feature
        for i, feature in enumerate(geojson_data["features"])
        if i in allowed
    ]

    filtered_geojson = {
        "type": "FeatureCollection",
        "features": selected_features
    }

    layer = folium.FeatureGroup(name="Geographic Features")

    folium.GeoJson(
        filtered_geojson,
        tooltip=folium.GeoJsonTooltip(
            fields=list(df.columns)[:5]
        ) if len(df.columns) > 0 else None,
        style_function=lambda feature: {
            "fillColor": "#238b45",
            "color": "#176b36",
            "weight": 2,
            "fillOpacity": 0.45
        }
    ).add_to(layer)

    layer.add_to(m)

else:
    # Detect latitude/longitude columns
    columns = list(df.columns)
    latitude_guess = next(
        (col for col in columns
         if col.lower() in ["latitude", "lat"]), columns[0]
    )
    longitude_guess = next(
        (col for col in columns
         if col.lower() in ["longitude", "lon", "lng", "long"]),
        columns[min(1, len(columns)-1)]
    )

    lat_col = st.sidebar.selectbox(
        "Latitude column",
        columns,
        index=columns.index(latitude_guess)
    )

    lon_col = st.sidebar.selectbox(
        "Longitude column",
        columns,
        index=columns.index(longitude_guess)
    )

    points = filtered_df.copy()
    points[lat_col] = pd.to_numeric(
        points[lat_col], errors="coerce"
    )
    points[lon_col] = pd.to_numeric(
        points[lon_col], errors="coerce"
    )

    points = points.dropna(subset=[lat_col, lon_col])
    points = points[
        points[lat_col].between(-90, 90)
        & points[lon_col].between(-180, 180)
    ]

    marker_layer = folium.FeatureGroup(name="Data Points")

    target = (
        MarkerCluster().add_to(marker_layer)
        if show_clusters else marker_layer
    )

    for _, row in points.iterrows():
        details = "<br>".join(
            f"<b>{col}:</b> {str(row[col])[:100]}"
            for col in columns[:8]
        )

        folium.Marker(
            location=[row[lat_col], row[lon_col]],
            tooltip="View location details",
            popup=folium.Popup(details, max_width=300)
        ).add_to(target)

    marker_layer.add_to(m)

    if not points.empty:
        bounds = [
            [points[lat_col].min(), points[lon_col].min()],
            [points[lat_col].max(), points[lon_col].max()]
        ]
        m.fit_bounds(bounds)

folium.LayerControl(collapsed=False).add_to(m)

# Main display
map_tab, data_tab, chart_tab = st.tabs(
    ["🗺️ Interactive Map", "📋 Dataset", "📊 Analysis"]
)

with map_tab:
    st_folium(m, width=None, height=550, returned_objects=[])

with data_tab:
    st.subheader("Attribute Table")
    st.dataframe(filtered_df, use_container_width=True)

    csv = filtered_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download Filtered Data",
        csv,
        "filtered_gis_data.csv",
        "text/csv"
    )

with chart_tab:
    st.subheader("Data Analysis")

    numeric_columns = filtered_df.select_dtypes(
        include="number"
    ).columns.tolist()

    if numeric_columns and not filtered_df.empty:
        selected_column = st.selectbox(
            "Select numerical attribute",
            numeric_columns
        )
        st.bar_chart(
            filtered_df[selected_column].value_counts().head(20)
        )
        st.write(filtered_df[selected_column].describe())
    else:
        st.info("No numerical data available for analysis.")

