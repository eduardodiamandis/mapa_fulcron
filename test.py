import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# Configuração da página
st.set_page_config(layout="wide", page_title="Crop Tour Soja - Mapa")

st.title("🌱 Mapa de Coleta: Crop Tour Soja")
import os
if os.path.exists("crop_tour_soja.xlsx"):
    st.success("Arquivo Excel encontrado!")
else:
    st.error("ERRO: Arquivo crop_tour_soja.xlsx NÃO encontrado no servidor!")
    st.write("Arquivos presentes na pasta:", os.listdir("."))

# 1. Carregar os dados
@st.cache_data
def load_data():
    df = pd.read_excel("crop_tour_soja.xlsx")
    # Limpa linhas que não tenham latitude ou longitude
    df = df.dropna(subset=['latitude', 'longitude'])
    return df


df = load_data()

# 2. Filtros na Barra Lateral (Sidebar)
st.sidebar.header("Filtros")
condicao = st.sidebar.multiselect(
    "Condição da Lavoura:",
    options=df["condicao_da_lavoura"].unique(),
    default=df["condicao_da_lavoura"].unique()
)

df_filtered = df[df["condicao_da_lavoura"].isin(condicao)]

# 3. Criação do Mapa
# Centraliza o mapa na média das coordenadas
center_lat = df_filtered['latitude'].mean()
center_lon = df_filtered['longitude'].mean()

m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap")

# 4. Adicionar os pontos (Markers)
for _, row in df_filtered.iterrows():
    # Criando o conteúdo do Pop-up (HTML)
    popup_html = f"""
    <div style='width: 200px;'>
        <b>Localidade:</b> {row['localidade_']}<br>
        <b>Estádio:</b> {row['estadio_fenologico']}<br>
        <b>Produtividade (Grãos/ha):</b> {row['graosha_k']:.2f}K<br>
        <b>Condição:</b> {row['condicao_da_lavoura']}<br>
        <hr>
        <a href='{row['fotos_url']}' target='_blank'>Ver Foto da Amostra</a>
    </div>
    """

    # Define a cor do ícone com base na condição
    color = "green" if "Bom" in str(row['condicao_da_lavoura']) else "orange"

    folium.Marker(
        location=[row['latitude'], row['longitude']],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=f"Amostra: {row['localidade_']}",
        icon=folium.Icon(color=color, icon="leaf")
    ).add_to(m)

# 5. Exibição no Streamlit
st_folium(m, width="100%", height=600)

# Exibir tabela de dados abaixo do mapa
if st.checkbox("Mostrar tabela de dados"):
    st.dataframe(df_filtered)