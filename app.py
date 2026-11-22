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
    
    # Convertir fecha serial (ej. 46347) a YYYY-MM-DD
    if 'Fecha' in df.columns:
        df['Fecha'] = df['Fecha'].apply(
            lambda x: pd.to_datetime(x, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
            if isinstance(x, (int, float)) else str(x).strip()
        )
    # Extraer Meta, Fuente y Generica limpios desde ConsultaRealizada ("61 | RDR | 2.1 | Acumulado")
    if 'ConsultaRealizada' in df.columns:
        partes = df['ConsultaRealizada'].astype(str).str.split('|')
        df['Meta'] = partes.str.str.strip()
        df['Fuente'] = partes.str.str.strip()
        df['Generica'] = partes.str.str.strip()
        
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
    metas_disp = sorted(df_cons['Meta'].unique())
    metas_default = [m for m in ['1', '61'] if m in metas_disp] if solo_dre else metas_disp
    metas = st.sidebar.multiselect("Meta:", metas_disp, default=metas_default)
    
    # 2. Filtro de Fuente (RO y RDR)
    fuentes_disp = sorted(df_cons['Fuente'].unique())
    fuentes = st.sidebar.multiselect("Fuente:", fuentes_disp, default=fuentes_disp)
    
    # 3. Filtro de Genérica (2.1 y 2.3)
    gen_disp = sorted(df_cons['Generica'].unique())
    genericas = st.sidebar.multiselect("Genérica:", gen_disp, default=gen_disp)
    
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
