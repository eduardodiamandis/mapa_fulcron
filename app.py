import streamlit as st
import pandas as pd
import folium
from pathlib import Path
from streamlit_folium import st_folium

# Page configuration
st.set_page_config(layout="wide", page_title="Soybean Crop Tour - Map")
st.title("Sample Collection Map: Soybean Crop Tour")

FOTOS_DIR = Path("fotos")

# 1. Load data
@st.cache_data
def load_data():
    df = pd.read_excel("crop_tour_soja.xlsx")
    df = df.dropna(subset=['latitude', 'longitude'])
    # Add sequential ID column
    df.insert(0, 'ID', range(1, len(df) + 1))
    return df


def get_foto1_id(fotos_str):
    """Extracts first photo ID"""
    if pd.isna(fotos_str):
        return None
    return fotos_str.split(",")[0].strip()


@st.cache_data
def find_image_file(image_id):
    """Search for image file in local folder"""
    if not image_id:
        return None

    for ext in [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]:
        path = FOTOS_DIR / f"{image_id}{ext}"
        if path.exists():
            return path
    return None


# Load data
df = load_data()

# 2. Sidebar filters
st.sidebar.header("Filters")

# Crop condition filter
condition = st.sidebar.multiselect(
    "Crop Condition:",
    options=sorted(df["condicao_da_lavoura"].unique()),
    default=df["condicao_da_lavoura"].unique()
)

# Phenological stage filter
stages = st.sidebar.multiselect(
    "Phenological Stage:",
    options=sorted(df["estadio_fenologico"].unique()),
    default=df["estadio_fenologico"].unique()
)

# Apply filters
df_filtered = df[
    (df["condicao_da_lavoura"].isin(condition)) &
    (df["estadio_fenologico"].isin(stages))
].copy()

# Statistics
st.sidebar.markdown("---")
st.sidebar.markdown("Statistics")
st.sidebar.metric("Total samples", len(df_filtered))


# 3. Map creation
@st.cache_data
def create_lightweight_map(df_data):
    """Creates a lightweight map without embedded images"""

    if len(df_data) == 0:
        return None

    center_lat = df_data['latitude'].mean()
    center_lon = df_data['longitude'].mean()

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles="OpenStreetMap",
        prefer_canvas=True
    )

    for _, row in df_data.iterrows():
        popup_html = f"""
        <div style='width: 240px; font-family: Arial, sans-serif; font-size: 13px;'>
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white; padding: 12px; margin: -10px -10px 10px -10px;
                        border-radius: 4px 4px 0 0;'>
                <b style='font-size: 15px;'>Location: {row['localidade_']}</b>
                <div style='margin-top: 4px; font-size: 11px; opacity: 0.9;'>
                    ID: {row['ID']}
                </div>
            </div>
            <table style='width: 100%; font-size: 13px; line-height: 2;'>
                <tr>
                    <td style='color: #666;'><b>Stage:</b></td>
                    <td><b>{row['estadio_fenologico']}</b></td>
                </tr>
                <tr>
                    <td style='color: #666;'><b>Yield:</b></td>
                    <td><b style='color: #2ecc71; font-size: 14px;'>{row['graosha_k']:.2f}K</b> grains/ha</td>
                </tr>
                <tr>
                    <td style='color: #666;'><b>Condition:</b></td>
                    <td><b>{row['condicao_da_lavoura']}</b></td>
                </tr>
            </table>
            <div style='margin-top: 10px; padding: 8px; background: #fff3cd;
                        border-radius: 4px; text-align: center; border: 1px solid #ffc107;'>
                <small style='color: #856404;'>
                    Enter ID {row['ID']} below to view the photo
                </small>
            </div>
        </div>
        """

        # Marker color by condition
        color_map = {
            "Bom": "green",
            "Regular": "orange",
            "Ruim": "red"
        }

        condition_str = str(row['condicao_da_lavoura'])
        color = "blue"
        for key, value in color_map.items():
            if key in condition_str:
                color = value
                break

        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"ID {row['ID']}: {row['localidade_']} | {row['graosha_k']:.1f}K",
            icon=folium.Icon(color=color, icon="leaf", prefix='fa')
        ).add_to(m)

    return m


# Prepare data for map cache
df_for_map = df_filtered[['ID', 'latitude', 'longitude', 'localidade_',
                          'estadio_fenologico', 'graosha_k',
                          'condicao_da_lavoura']].copy()

# Generate map
with st.spinner("Generating map..."):
    m = create_lightweight_map(df_for_map)

# 4. Display map
if m:
    st_folium(m, width="100%", height=400)
else:
    st.warning("No points match the selected filters.")

# 5. ID search section
st.markdown("---")
st.subheader("Search Point by ID")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("Enter the ID of the point you want to view:")

with col2:
    if len(df_filtered) > 0:
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f'crop_tour_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}.csv',
            mime='text/csv',
        )

if len(df_filtered) > 0:
    col_input, col_info = st.columns([1, 3])

    with col_input:
        id_range = f"({df_filtered['ID'].min()} - {df_filtered['ID'].max()})"
        input_id = st.number_input(
            f"ID {id_range}:",
            min_value=int(df_filtered['ID'].min()),
            max_value=int(df_filtered['ID'].max()),
            value=int(df_filtered['ID'].min()),
            step=1,
            key="id_input"
        )

    with col_info:
        if input_id in df_filtered['ID'].values:
            selected_row = df_filtered[df_filtered['ID'] == input_id].iloc[0]
            st.success(f"ID {input_id} found: {selected_row['localidade_']}")
        else:
            st.error(f"ID {input_id} not found in filtered data")
            selected_row = None

    if input_id in df_filtered['ID'].values:
        st.markdown("---")

        col_info, col_foto = st.columns([1, 1])

        with col_info:
            st.markdown(f"Information - ID {selected_row['ID']}")

            st.markdown(f"""
            Location: {selected_row['localidade_']}

            Phenological Stage: {selected_row['estadio_fenologico']}

            Yield: {selected_row['graosha_k']:.2f}K grains/ha

            Crop Condition: {selected_row['condicao_da_lavoura']}

            Coordinates:
            - Latitude: {selected_row['latitude']:.6f}
            - Longitude: {selected_row['longitude']:.6f}
            """)

            if 'data_coleta' in selected_row:
                st.markdown(f"Collection Date: {selected_row['data_coleta']}")

        with col_foto:
            st.markdown("Sample Photo")

            foto1_id = get_foto1_id(selected_row["fotos"])
            if foto1_id:
                foto_path = find_image_file(foto1_id)
                if foto_path and foto_path.exists():
                    st.image(
                        str(foto_path),
                        caption=f"Photo ID: {foto1_id}",
                        use_container_width=True
                    )
                else:
                    st.info(f"Photo not found: {foto1_id}")
            else:
                st.info("No photo available for this sample")

    st.markdown("---")

    with st.expander("View full filtered data table"):
        st.dataframe(
            df_filtered[['ID', 'localidade_', 'estadio_fenologico',
                         'graosha_k', 'condicao_da_lavoura',
                         'latitude', 'longitude']],
            use_container_width=True,
            height=400
        )
else:
    st.info("No data available with the current filters.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 12px;'>
    <p>Tip: Click on a map marker to see the point ID.</p>
    <p>Enter the ID above to view details and the sample photo.</p>
</div>
""", unsafe_allow_html=True)
