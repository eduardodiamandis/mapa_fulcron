import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Crop Tour Soja - Brazil 2026")

st.markdown("""
<style>
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .detail-card { animation: fadeInUp 0.35s ease; }
    .stDeckGlJsonChart > div { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("Sampling Map: Brazil Soy Crop Tour 2026")

FOTOS_DIR = Path("fotos")


# --- 1. DADOS ---
@st.cache_data
def load_data():
    df = pd.read_csv("crop_tour_soja.csv")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={'_latitude': 'latitude', '_longitude': 'longitude', 'localidade': 'localidade_'})

    # Mantém apenas quem tem coordenadas
    df = df.dropna(subset=['latitude', 'longitude'])

    # --- TRATAMENTO PARA ESPAÇOS E "SEM INFORMAÇÃO" ---
    df['condicao_da_lavoura'] = (
        df['condicao_da_lavoura']
        .fillna("Sem Info")
        .astype(str)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
    )

    df['estadio_fenologico'] = (
        df['estadio_fenologico']
        .fillna("Sem Info")
        .astype(str)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
    )

    color_map = {
        "1. Muito Ruim": [139, 0, 0, 230],
        "2. Ruim": [231, 76, 60, 230],
        "3. Media": [241, 196, 15, 230],
        "4. Boa": [46, 204, 113, 230],
        "5. Excelente": [142, 68, 173, 230],
        "Sem Info": [128, 128, 128, 160],
    }

    df['base_color'] = df['condicao_da_lavoura'].apply(
        lambda x: color_map.get(x, color_map["Sem Info"])
    )

    df.insert(0, 'ID', range(1, len(df) + 1))
    return df


@st.cache_resource(ttl=300)
def get_image_index():
    index = {}
    if not FOTOS_DIR.exists():
        return index
    for path in FOTOS_DIR.glob("*"):
        if path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            index[path.stem] = str(path)
    return index


df = load_data()
image_index = get_image_index()

# --- 2. SIDEBAR (LEGENDA COM TRADUÇÕES) ---
st.sidebar.markdown("### Legend - Condition")
st.sidebar.markdown("""
- 🔴 **1. Muito Ruim** (Very Poor)
- 🟠 **2. Ruim** (Poor)
- 🟡 **3. Media** (Fear)
- 🟢 **4. Boa** (Good)
- 🟣 **5. Excelente** (Excellent)
- ⚪ **Sem Info** (No Information)
""")

st.sidebar.header("Crop Filters")

opcoes_condicao = sorted(df["condicao_da_lavoura"].unique())
condition = st.sidebar.multiselect(
    "Condição da Lavoura (Condition):",
    options=opcoes_condicao,
    default=opcoes_condicao
)

opcoes_estadios = sorted(df["estadio_fenologico"].unique())
stages = st.sidebar.multiselect(
    "Estádio Fenológico (Growth Stage):",
    options=opcoes_estadios,
    default=opcoes_estadios
)

df_filtered = df[
    (df["condicao_da_lavoura"].isin(condition)) &
    (df["estadio_fenologico"].isin(stages))
    ].copy().reset_index(drop=True)

st.sidebar.divider()
st.sidebar.metric("Filtered Samples", len(df_filtered))

# --- 3. SESSION STATE ---
if "selected_idx" not in st.session_state:
    st.session_state["selected_idx"] = None

st.session_state["_df_len"] = len(df_filtered)


def on_map_select():
    raw = st.session_state.get("pydeck_map")
    if not raw:
        st.session_state["selected_idx"] = None
        return
    indices = raw.get("selection", {}).get("indices", {})
    all_idx = []
    if isinstance(indices, dict):
        for v in indices.values(): all_idx.extend(v)
    elif isinstance(indices, list):
        all_idx = indices

    df_len = st.session_state.get("_df_len", 0)
    if all_idx and 0 <= all_idx[0] < df_len:
        st.session_state["selected_idx"] = all_idx[0]
    else:
        st.session_state["selected_idx"] = None


# --- 4. MAPA ---
selected_idx = st.session_state["selected_idx"]
if selected_idx is not None and selected_idx >= len(df_filtered):
    selected_idx = None
    st.session_state["selected_idx"] = None


def build_display_data(data, sel_idx):
    display = data.copy()
    if sel_idx is not None and 0 <= sel_idx < len(display):
        display['fill_color'] = display['base_color'].apply(lambda c: [c[0], c[1], c[2], 70])
        display['point_radius'] = 15000
        display.at[sel_idx, 'fill_color'] = [255, 255, 255, 255]
        display.at[sel_idx, 'point_radius'] = 32000
    else:
        display['fill_color'] = display['base_color']
        display['point_radius'] = 15000
    return display


def render_map(data, sel_idx):
    display = build_display_data(data, sel_idx)
    view_state = pdk.ViewState(
        latitude=data['latitude'].mean() if not data.empty else -15.78,
        longitude=data['longitude'].mean() if not data.empty else -47.93,
        zoom=4, pitch=0,
    )
    layer = pdk.Layer(
        "ScatterplotLayer",
        display,
        get_position='[longitude, latitude]',
        get_fill_color='fill_color',
        get_radius='point_radius',
        pickable=True,
        auto_highlight=True,
        radius_min_pixels=6,
    )
    return pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={
        "html": "<b>Location:</b> {localidade_}<br/><b>Condition:</b> {condicao_da_lavoura}<br/><b>Yield:</b> {graosha_k} K grains/ha",
        "style": {"backgroundColor": "#1a1a2e", "color": "white"}
    })


st.subheader("Spatial Visualization")
st.caption("Hover for details • Click on a point to view field data below")

st.pydeck_chart(
    render_map(df_filtered, selected_idx),
    on_select=on_map_select,
    selection_mode="single-object",
    width='stretch',
    key="pydeck_map",
)

# --- 5. DETALHES ---
st.divider()
selected_row = df_filtered.iloc[selected_idx] if (
            selected_idx is not None and selected_idx < len(df_filtered)) else None

if selected_row is not None:
    badge_colors = {
        "1. Muito Ruim": "#8B0000", "2. Ruim": "#E74C3C", "3. Media": "#F1C40F",
        "4. Boa": "#2ECC71", "5. Excelente": "#8E44AD", "Sem Info": "#808080"
    }
    cond = selected_row['condicao_da_lavoura']
    color = badge_colors.get(cond, "#888")

    st.markdown('<div class="detail-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown(f"""
            <div style="background:{color}22;border-left:4px solid {color};padding:12px;border-radius:6px;">
                <span style="font-weight:700">📍 Sample ID {int(selected_row['ID'])}</span><br/>
                <span style="font-size:14px;">{selected_row['localidade_']}</span>
            </div>
        """, unsafe_allow_html=True)
        st.write(f"**Condition (Condição):** {cond}")
        st.write(f"**Stage (Estádio):** {selected_row['estadio_fenologico']}")
        st.write(f"**Yield (Produtividade):** {selected_row.get('graosha_k', 0):.2f}K grains/ha")

    with c2:
        foto_ids = [id.strip() for id in str(selected_row.get("fotos", "")).split(",") if id.strip() not in ["nan", ""]]
        foto_paths = [image_index.get(id) for id in foto_ids]
        valid_fotos = [p for p in foto_paths if p]
        if valid_fotos:
            st.image(valid_fotos[0], use_container_width=True,
                     caption=f"Field Image - Sample {int(selected_row['ID'])}")
        else:
            st.info("📷 No photo available.")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("🗺️ Select a point on the map to see specific details.")

# --- 6. DOWNLOAD & TABLE ---
st.divider()
st.download_button("⬇️ Download CSV", df_filtered.to_csv(index=False).encode('utf-8'), "crop_tour.csv", "text/csv")
with st.expander("View Full Data Table"):
    st.dataframe(df_filtered, use_container_width=True)