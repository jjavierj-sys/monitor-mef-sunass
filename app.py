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
    regs = wb.worksheet(nombre).get_all_records()
    return pd.DataFrame(regs) if regs else pd.DataFrame()

if st.button("🔄 Refrescar Vista Web", type="primary"):
    st.cache_data.clear()
    st.rerun()

df_cons = leer_pestana("MEF_Consolidado_Unico")
df_mens = leer_pestana("tblMensual")

if df_cons.empty:
    st.info("Ejecuta 'Actualizar Todo MEF (Hoy)' desde el menú de tu Google Sheet para cargar los datos.")
else:
    st.sidebar.header("Filtros Rápidos")
    fechas = sorted(df_cons['Fecha'].astype(str).unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox("Fecha de corte:", fechas)
    metas = st.sidebar.multiselect("Meta:", ['1', '61', '160'], default=['1', '61', '160'], format_func=str)
    solo_cambios_dev = st.sidebar.checkbox("Solo con variación en Devengado (.Devengado)")
    solo_pim_mayor_0 = st.sidebar.checkbox("Solo PIM > 0", value=True)

    df_view = df_cons[(df_cons['Fecha'].astype(str) == fecha_sel) & (df_cons['Meta'].astype(str).isin(metas))]
    if solo_pim_mayor_0:
        df_view = df_view[df_view['PIM.'] == 'PIM>0']
    if solo_cambios_dev:
        df_view = df_view[df_view['.Devengado'] == '.Devengado']

    # KPIs superiores
    c1, c2, c3, c4 = st.columns(4)
    pim_tot = pd.to_numeric(df_view['PIM'], errors='coerce').sum()
    dev_tot = pd.to_numeric(df_view['Devengado'], errors='coerce').sum()
    dif_dev = pd.to_numeric(df_view['Dif_Devengado'], errors='coerce').sum()
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
