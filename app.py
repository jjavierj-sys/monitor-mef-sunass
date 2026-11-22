import io
import json
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Monitor Presupuestal SUNASS - MEF", layout="wide")
st.title("📊 Monitor Presupuestal SUNASS (Consulta Amigable MEF)")

NOMBRE_SHEET = "Historial_MEF_SUNASS"

@st.cache_resource
def conectar_gsheets():
    p = "https://"
    g = "googleapis.com"
    s1 = p + "www." + g + "/auth/spreadsheets"
    s2 = p + "www." + g + "/auth/drive"
    info = json.loads(st.secrets["json_crudo"], strict=False)
    info["auth_uri"] = p + "accounts." + "://google.com"
    info["token_uri"] = p + "oauth2." + g + "/token"
    creds = Credentials.from_service_account_info(info, scopes=[s1, s2])
    return gspread.authorize(creds).open(NOMBRE_SHEET)

@st.cache_data(ttl=60)
def leer_pestana(nombre):
    wb = conectar_gsheets()
    regs = wb.worksheet(nombre).get_all_records(value_render_option='UNFORMATTED_VALUE')
    if not regs:
        return pd.DataFrame()
    df = pd.DataFrame(regs)
    
    # Convertir fecha serial de Excel/Sheets (ej. 46347) a formato legible YYYY-MM-DD
    if 'Fecha' in df.columns:
        df['Fecha'] = df['Fecha'].apply(
            lambda x: pd.to_datetime(x, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
            if isinstance(x, (int, float)) else str(x).strip()
        )
    # Normalizar Meta, Fuente y Generica como texto limpio
    if 'Meta' in df.columns:
        df['Meta'] = df['Meta'].astype(str).str.replace('.0', '', regex=False).str.strip()
    if 'Fuente' in df.columns:
        df['Fuente'] = df['Fuente'].astype(str).str.strip()
    if 'Generica' in df.columns:
        df['Generica'] = df['Generica'].apply(lambda x: f"{float(x):.1f}" if str(x).replace('.','',1).isdigit() else str(x).strip())
        
    return df

if st.button("🔄 Refrescar Vista Web", type="primary"):
    st.cache_data.clear()
    st.rerun()

df_cons = leer_pestana("MEF_Consolidado_Unico")
df_mens = leer_pestana("tblMensual")

if df_cons.empty:
    st.info("Ejecuta 'Actualizar Todo MEF (Hoy)' desde el menú de tu Google Sheet para cargar los datos.")
else:
    st.sidebar.header("Filtros Rápidos")
    fechas = sorted(df_cons['Fecha'].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox("Fecha de corte:", fechas)
    
    # 1. Filtro rápido Área DRE (Metas 1 y 61)
    solo_dre = st.sidebar.checkbox("Solo Área DRE (Metas 1 y 61)")
    metas_default = ['1', '61'] if solo_dre else ['1', '61', '160']
    metas = st.sidebar.multiselect("Meta:", ['1', '61', '160'], default=metas_default)
    
    # 2. Filtro de Fuente (RO y RDR)
    fuentes = st.sidebar.multiselect("Fuente:", ['RO', 'RDR'], default=['RO', 'RDR'])
    
    # 3. Filtro de Genérica (2.1 y 2.3)
    genericas = st.sidebar.multiselect("Genérica:", ['2.1', '2.3'], default=['2.1', '2.3'])
    
    solo_cambios_dev = st.sidebar.checkbox("Solo con variación en Devengado (.Devengado)")
    solo_pim_mayor_0 = st.sidebar.checkbox("Solo PIM > 0", value=True)

    df_view = df_cons[
        (df_cons['Fecha'] == fecha_sel) & 
        (df_cons['Meta'].isin(metas)) &
        (df_cons['Fuente'].isin(fuentes)) &
        (df_cons['Generica'].isin(genericas))
    ]
    if solo_pim_mayor_0:
        df_view = df_view[df_view['PIM.'] == 'PIM>0']
    if solo_cambios_dev:
        df_view = df_view[df_view['.Devengado'] == '.Devengado']

    # KPIs superiores exactos
    c1, c2, c3, c4 = st.columns(4)
    pim_tot = pd.to_numeric(df_view['PIM'], errors='coerce').fillna(0).sum()
    dev_tot = pd.to_numeric(df_view['Devengado'], errors='coerce').fillna(0).sum()
    dif_dev = pd.to_numeric(df_view['Dif_Devengado'], errors='coerce').fillna(0).sum()
    pct_tot = (dev_tot / pim_tot * 100) if pim_tot > 0 else 0

    c1.metric("PIM Total", f"S/ {pim_tot:,.2f}")
    c2.metric("Devengado Acumulado", f"S/ {dev_tot:,.2f}", f"S/ {dif_dev:,.2f} hoy")
    c3.metric("% Ejecución (Dev/PIM)", f"{pct_tot:.2f}%")
    c4.metric("Saldo PIM - Dev", f"S/ {(pim_tot - dev_tot):,.2f}")

    t1, t2 = st.tabs(["📌 Consolidado Acumulado y Variaciones", "📅 Ejecución Último Mes"])
    with t1:
        st.dataframe(df_view, use_container_width=True)
    with t2:
        st.dataframe(df_mens, use_container_width=True)

    # Descarga Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_cons.to_excel(writer, index=False, sheet_name='MEF_Consolidado_Unico')
        df_mens.to_excel(writer, index=False, sheet_name='tblMensual')

    st.sidebar.download_button(
        label="📥 Descargar Excel Completo (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"SUNASS_MEF_{fecha_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
