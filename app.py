
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="GIS Dashboard",
    layout="wide"
)

st.title("GIS Data Visualization Dashboard")
st.write("Interactive GIS project using Streamlit")

uploaded_file = st.file_uploader(
    "Upload your GIS dataset (CSV)",
    type=["csv"]
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.subheader("Dataset Preview")
    st.dataframe(df)

    if {"latitude", "longitude"}.issubset(df.columns):
        m = folium.Map(
            location=[df["latitude"].mean(),
                      df["longitude"].mean()],
            zoom_start=6
        )

        for _, row in df.dropna(
            subset=["latitude", "longitude"]
        ).iterrows():
            folium.Marker(
                [row["latitude"], row["longitude"]]
            ).add_to(m)

        st_folium(m, width=None, height=500)
    else:
        st.warning(
            "Dataset must contain latitude and longitude columns."
        )
