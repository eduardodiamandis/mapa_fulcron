import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Crop Tour - Brazil 2026")

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

st.title("Sampling Map: Safrinha Crop Tour 2026")

FOTOS_DIR = Path("fotos")
CSV_FILE = "brazil_2026_winter_corn_croptour.csv"


# --- FUNÇÕES AUXILIARES ---

def adjust_yield(yield_value):
    """
    Aplica a fórmula de ajuste de produtividade aos valores de sacas por hectare.

    Fórmula: y = ((0,04668x + 0,16508) × 1000) / 60

    Onde:
        x: valor original de produtividade (sacas/hectare)
        y: valor ajustado após a transformação

    Argumentos:
        yield_value: float ou pd.Series - valor(es) de produtividade a transformar

    Retorna:
        float ou pd.Series - valor(es) transformados pela fórmula
    """
    return (((0.04668 * yield_value) + 0.16508) * 1000) / 60


# --- 1. DATA LOADING ---
@st.cache_data
def load_data(csv_file):
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={'_latitude': 'latitude', '_longitude': 'longitude', 'localidade': 'localidade_'})
    df = df.dropna(subset=['latitude', 'longitude'])

    if 'estdio_fenolgico' in df.columns and 'estadio_fenologico' not in df.columns:
        df = df.rename(columns={'estdio_fenolgico': 'estadio_fenologico'})

    if 'condio_da_lavoura' in df.columns and 'condicao_da_lavoura' not in df.columns:
        df = df.rename(columns={'condio_da_lavoura': 'condicao_da_lavoura'})

    if not df.empty and 'condicao_da_lavoura' in df.columns:
        df['condicao_da_lavoura'] = (
            df['condicao_da_lavoura']
            .fillna("Sem Info")
            .astype(str)
            .str.replace(r'\s+', ' ', regex=True)
            .str.strip()
            .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
        )

    if not df.empty and 'estadio_fenologico' in df.columns:
        df['estadio_fenologico'] = (
            df['estadio_fenologico']
            .fillna("Sem Info")
            .astype(str)
            .str.replace(r'\s+', ' ', regex=True)
            .str.strip()
            .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
        )

    # ✅ AJUSTE DE PRODUTIVIDADE
    # Fórmula: y = ((0,04668x + 0,16508) * 1000) / 60
    # Aplica a transformação linear com conversão de unidades a todos os valores de produtividade
    if 'produtividade_estimada_clculo_automtico_sacasha' in df.columns:
        # Converte para numérico (valores inválidos viram NaN)
        df['produtividade_estimada_clculo_automtico_sacasha'] = pd.to_numeric(
            df['produtividade_estimada_clculo_automtico_sacasha'],
            errors='coerce'
        )

        # ✅ Armazena o valor ORIGINAL em uma coluna separada para verificação
        df['produtividade_original_sacasha'] = df['produtividade_estimada_clculo_automtico_sacasha'].copy()

        # Aplica a função de ajuste de produtividade aos valores
        df['produtividade_estimada_clculo_automtico_sacasha'] = adjust_yield(
            df['produtividade_estimada_clculo_automtico_sacasha']
        )

    # ✅ Cores como colunas inteiras separadas — Arrow-safe, sem risco de corrupção
    color_map = {
        "2. Ruim / Poor": [231, 76, 60, 230],
        "3. Média / Fair": [241, 196, 15, 230],
        "4. Boa / Good": [46, 204, 113, 230],
        "5. Excelente / Excellent": [142, 68, 173, 230],
        "Sem Info": [128, 128, 128, 160],
    }

    def get_color(val, i):
        return color_map.get(val, color_map["Sem Info"])[i]

    if not df.empty and 'condicao_da_lavoura' in df.columns:
        df['cr'] = df['condicao_da_lavoura'].apply(lambda x: get_color(x, 0))
        df['cg'] = df['condicao_da_lavoura'].apply(lambda x: get_color(x, 1))
        df['cb'] = df['condicao_da_lavoura'].apply(lambda x: get_color(x, 2))
        df['ca'] = df['condicao_da_lavoura'].apply(lambda x: get_color(x, 3))
    else:
        df['cr'], df['cg'], df['cb'], df['ca'] = 128, 128, 128, 160

    df.insert(0, 'ID', range(1, len(df) + 1))
    return df


@st.cache_resource(ttl=300)
def get_image_index():
    index = {}
    if not FOTOS_DIR.exists(): return index
    for path in FOTOS_DIR.glob("*"):
        if path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            index[path.stem] = str(path)
    return index


df = load_data(CSV_FILE)
image_index = get_image_index()

# --- 2. SIDEBAR (LEGEND & FILTERS) ---
st.sidebar.markdown("### Legend - Condition")
st.sidebar.markdown("""
- 🔴 **2. Ruim / Poor**
- 🟡 **3. Média / Fair**
- 🟢 **4. Boa / Good**
- 🟣 **5. Excelente / Excellent**
- ⚪ **Sem Info** (No Information)
""")

if not df.empty:
    st.sidebar.header("Crop Filters")

    condition = st.sidebar.multiselect(
        "Condition:",
        options=sorted(df["condicao_da_lavoura"].unique()) if "condicao_da_lavoura" in df.columns else [],
        default=df["condicao_da_lavoura"].unique().tolist() if "condicao_da_lavoura" in df.columns else []
    )

    stages = st.sidebar.multiselect(
        "Growth Stage:",
        options=sorted(df["estadio_fenologico"].unique()) if "estadio_fenologico" in df.columns else [],
        default=df["estadio_fenologico"].unique().tolist() if "estadio_fenologico" in df.columns else []
    )

    if condition and stages:
        df_filtered = df[
            (df["condicao_da_lavoura"].isin(condition)) &
            (df["estadio_fenologico"].isin(stages))
            ].copy().reset_index(drop=True)
    else:
        df_filtered = df.copy().reset_index(drop=True)
else:
    df_filtered = df.copy()

st.sidebar.divider()
st.sidebar.metric("Total Samples", len(df_filtered))

# --- 3. SESSION STATE ---
if "selected_idx" not in st.session_state:
    st.session_state["selected_idx"] = None
st.session_state["_df_len"] = len(df_filtered)


def on_map_select():
    raw = st.session_state.get("pydeck_map")
    if not raw: return
    indices = raw.get("selection", {}).get("indices", {})
    all_idx = []
    if isinstance(indices, dict):
        for v in indices.values(): all_idx.extend(v)
    elif isinstance(indices, list):
        all_idx = indices

    if all_idx and 0 <= all_idx[0] < st.session_state["_df_len"]:
        st.session_state["selected_idx"] = all_idx[0]
    else:
        st.session_state["selected_idx"] = None


# --- 4. MAP ---
selected_idx = st.session_state["selected_idx"]
if selected_idx is not None and selected_idx >= len(df_filtered):
    selected_idx = None


def render_map(data, sel_idx):
    if data.empty:
        view_state = pdk.ViewState(latitude=-15.78, longitude=-47.93, zoom=4, pitch=0)
        return pdk.Deck(initial_view_state=view_state)

    display = data.copy()
    display['point_radius'] = 15000

    # ✅ Colunas r/g/b/a já são inteiros puros — sem risco de corrupção Arrow
    display['r'] = display['cr']
    display['g'] = display['cg']
    display['b'] = display['cb']
    display['a'] = display['ca']

    if sel_idx is not None and 0 <= sel_idx < len(display):
        display['a'] = 70  # desfoca todos
        display.at[sel_idx, 'r'] = 255
        display.at[sel_idx, 'g'] = 255
        display.at[sel_idx, 'b'] = 255
        display.at[sel_idx, 'a'] = 255
        display.at[sel_idx, 'point_radius'] = 32000

    view_state = pdk.ViewState(
        latitude=data['latitude'].mean(),
        longitude=data['longitude'].mean(),
        zoom=4, pitch=0,
    )

    layer = pdk.Layer(
        "ScatterplotLayer", display,
        get_position='[longitude, latitude]',
        get_fill_color='[r, g, b, a]',  # ✅ Leitura direta de colunas inteiras
        get_radius='point_radius',
        pickable=True, auto_highlight=True, radius_min_pixels=6,
    )

    tooltip_html = "<b>Location:</b> {municipio}<br/><b>Condition:</b> {condicao_da_lavoura}"
    if "produtividade_estimada_clculo_automtico_sacasha" in data.columns:
        tooltip_html += "<br/><b>Yield:</b> {produtividade_estimada_clculo_automtico_sacasha} sc/ha"

    return pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={
        "html": tooltip_html,
        "style": {"backgroundColor": "#1a1a2e", "color": "white", "borderRadius": "8px"}
    })


st.subheader("Spatial Visualization")
st.pydeck_chart(render_map(df_filtered, selected_idx), on_select=on_map_select, selection_mode="single-object",
                key="pydeck_map")

# --- 5. DETAILS ---
st.divider()
if selected_idx is not None and selected_idx < len(df_filtered):
    selected_row = df_filtered.iloc[selected_idx]

    badge_colors = {
        "2. Ruim / Poor": "#E74C3C",
        "3. Média / Fair": "#F1C40F",
        "4. Boa / Good": "#2ECC71",
        "5. Excelente / Excellent": "#8E44AD",
        "Sem Info": "#808080",
    }
    condition_val = selected_row.get('condicao_da_lavoura', 'Sem Info')
    color = badge_colors.get(condition_val, "#888")

    st.markdown('<div class="detail-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])

    with c1:
        location = selected_row.get('municipio', selected_row.get('localidade_', 'Unknown'))
        st.markdown(f"""
            <div style="background:{color}22;border-left:4px solid {color};padding:12px;border-radius:6px;margin-bottom:15px;">
                <span style="font-weight:700;font-size:18px;">📍 Sample ID {int(selected_row['ID'])}</span><br/>
                <span style="font-size:14px;opacity:0.8;">{location}</span>
            </div>
        """, unsafe_allow_html=True)

        if 'condicao_da_lavoura' in selected_row.index:
            st.markdown(f"**Condition:** `{selected_row['condicao_da_lavoura']}`")
        if 'estadio_fenologico' in selected_row.index:
            st.markdown(f"**Growth Stage:** `{selected_row['estadio_fenologico']}`")

        # ✅ Exibir valor ajustado
        yield_adjusted = selected_row.get('produtividade_estimada_clculo_automtico_sacasha')

        if yield_adjusted and pd.notna(yield_adjusted):
            try:
                adj_val = float(yield_adjusted)
                st.markdown(f"**Estimated Yield:** `{adj_val:.2f}`")
            except:
                st.markdown("**Estimated Yield:** Not available")
        else:
            st.markdown("**Estimated Yield:** Not available")

        obs_raw = selected_row.get("observacoes", "")
        obs = "No observations available." if pd.isna(obs_raw) or str(obs_raw).strip() in ["", "nan"] else str(
            obs_raw).strip()
        st.markdown(f"""
            <div style="margin-top:20px; padding:10px; background:#1a1a2e; border-radius:5px; border-left: 3px solid #4a4a8a;">
                <small style="color:#888; text-transform:uppercase;">Notes</small><br/>
                <span style="font-size:14px; color:#ddd;">{obs}</span>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        all_foto_ids = []

        if "fotos" in selected_row.index:
            fotos_raw = str(selected_row.get("fotos", ""))
            all_foto_ids.extend([id.strip() for id in fotos_raw.split(",") if id.strip() not in ["nan", ""]])

        for col in ["fotos_das_espigas_cap_do_carro", "foto_das_linhas", "fotos_adicionais"]:
            if col in selected_row.index:
                fotos_raw = str(selected_row.get(col, ""))
                all_foto_ids.extend([id.strip() for id in fotos_raw.split(",") if id.strip() not in ["nan", ""]])

        foto_paths = [image_index.get(id) for id in all_foto_ids]
        valid_fotos = [(id, path) for id, path in zip(all_foto_ids, foto_paths) if path]

        if valid_fotos:
            if len(valid_fotos) > 1:
                tabs = st.tabs([f"Photo {i + 1}" for i in range(len(valid_fotos))])
                for tab, (f_id, f_path) in zip(tabs, valid_fotos):
                    with tab: st.image(f_path, width='stretch', caption=f"Photo ID: {f_id}")
            else:
                st.image(valid_fotos[0][1], width='stretch', caption=f"Sample Photo")
        else:
            st.info("📷 No photos found for this sample.")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("🗺️ Select a point on the map to view detailed field information and photos.")