from datetime import datetime
import io
import json
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Monitor Presupuestal SUNASS - MEF", layout="wide")
st.title("📊 Control Presupuestal SUNASS (Nivel Específica)")

# --- CONFIGURACIÓN ---
RESOURCE_ID = "615644aa-ef73-4358-b4e0-0c20931632f3"
NOMBRE_SHEET = "Historial_MEF_SUNASS"

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_gsheets():
    scopes = [
        "https://googleapis.com" + "/auth/spreadsheets",
        "https://googleapis.com" + "/auth/drive"
    ]
    info = json.loads(st.secrets["json_crudo"], strict=False)
    info["auth_uri"] = "https://google.com" + "/o/oauth2/auth"
    info["token_uri"] = "https://googleapis.com" + "/token"
    
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(NOMBRE_SHEET).worksheet("datos")

def leer_historial():
    sheet = conectar_gsheets()
    registros = sheet.get_all_records()
    if not registros:
        return pd.DataFrame()
    df = pd.DataFrame(registros)
    cols_num = ['mes_eje', 'pim', 'cert', 'comp', 'at_mensual', 'dev', 'gir']
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    df['meta'] = df['meta'].astype(str).str.zfill(4)
    return df

def guardar_foto_hoy(df_hoy):
    sheet = conectar_gsheets()
    df_actual = leer_historial()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    df_hoy['fecha_consulta'] = fecha_hoy
    
    if not df_actual.empty:
        df_actual = df_actual[df_actual['fecha_consulta'] != fecha_hoy]
        df_final = pd.concat([df_actual, df_hoy], ignore_index=True)
    else:
        df_final = df_hoy

    sheet.clear()
    sheet.update([df_final.columns.values.tolist()] + df_final.values.tolist())

# --- CONSULTA ÚNICA AL MEF (SUNASS) ---
def descargar_datos_mef():
    sql = f"""
    SELECT 
        CAST(MES_EJE AS INTEGER) as mes_eje,
        META as meta,
        FUENTE_FINANC_NOMBRE as fuente,
        GENERICA_NOMBRE as generica,
        ESPECIFICA_DET as especifica,
        ESPECIFICA_DET_NOMBRE as especifica_nombre,
        SUM(CAST(MONTO_PIM AS NUMERIC)) as pim,
        SUM(CAST(MONTO_CERTIFICADO AS NUMERIC)) as cert,
        SUM(CAST(MONTO_COMPROMETIDO_ANUAL AS NUMERIC)) as comp,
        SUM(CAST(MONTO_COMPROMETIDO AS NUMERIC)) as at_mensual,
        SUM(CAST(MONTO_DEVENGADO AS NUMERIC)) as dev,
        SUM(CAST(MONTO_GIRADO AS NUMERIC)) as gir
    FROM "{RESOURCE_ID}"
    WHERE PLIEGO = '021'
      AND META IN ('0001', '0061', '0160')
      AND FUENTE_FINANC IN ('1', '2')
      AND GENERICA IN ('1', '3')
    GROUP BY MES_EJE, META, FUENTE_FINANC_NOMBRE, GENERICA_NOMBRE, ESPECIFICA_DET, ESPECIFICA_DET_NOMBRE
    """
    url = "https://mef.gob.pe"
    resp = requests.get(url, params={"sql": sql}, timeout=60)
    data = resp.json()
    
    if data.get("success"):
        df = pd.DataFrame(data["result"]["records"])
        cols_num = ['pim', 'cert', 'comp', 'at_mensual', 'dev', 'gir']
        for col in cols_num:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        df['mes_eje'] = pd.to_numeric(df['mes_eje'], errors='coerce').astype(int)
        return df
    return pd.DataFrame()

# --- CÁLCULO DE BRECHAS E INDICADORES ---
def calcular_indicadores(df):
    df = df.copy()
    df['PIM - CERT'] = df['pim'] - df['cert']
    df['CERT - Comp'] = df['cert'] - df['comp']
    df['Comp - AtMensual'] = df['comp'] - df['at_mensual']
    df['AtMensual - Dev'] = df['at_mensual'] - df['dev']
    df['Dev - Gir'] = df['dev'] - df['gir']
    df['% Ejec (Dev/PIM)'] = (df['dev'] / df['pim'] * 100).fillna(0).round(2)
    return df

# --- INTERFAZ WEB ---
if st.button("🔄 Actualizar Datos MEF (Hoy)", type="primary"):
    with st.spinner("Consultando API del MEF y guardando en Google Sheets..."):
        df_hoy = descargar_datos_mef()
        if not df_hoy.empty:
            guardar_foto_hoy(df_hoy)
            st.success("¡Sincronización exitosa! Datos guardados en Google Sheets.")
        else:
            st.error("No se obtuvieron datos. Verifica el RESOURCE_ID del año vigente.")

df_hist = leer_historial()

if df_hist.empty:
    st.info("Tu Google Sheet está vacío. Haz clic en **'Actualizar Datos MEF (Hoy)'** para cargar la primera foto.")
else:
    fechas_disponibles = sorted(df_hist['fecha_consulta'].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox("Fecha de consulta:", fechas_disponibles)
    mes_actual = datetime.strptime(fecha_sel, "%Y-%m-%d").month
    metas_sel = st.sidebar.multiselect("Filtrar Metas:", ['0001', '0061', '0160'], default=['0001', '0061', '0160'])

    df_corte = df_hist[(df_hist['fecha_consulta'] == fecha_sel) & (df_hist['meta'].isin(metas_sel))]

    # 1. Acumulado al día
    df_acum = df_corte.groupby(['meta', 'fuente', 'generica', 'especifica', 'especifica_nombre'], as_index=False)[
        ['pim', 'cert', 'comp', 'at_mensual', 'dev', 'gir']
    ].sum()
    df_acum = calcular_indicadores(df_acum)

    # 2. Último mes
    df_mes = df_corte[df_corte['mes_eje'] == mes_actual].copy()
    df_mes = calcular_indicadores(df_mes)

    # 3. Variación diaria
    df_var_diaria = pd.DataFrame()
    if len(fechas_disponibles) > 1:
        fecha_ayer = fechas_disponibles[1]
        df_ayer = df_hist[(df_hist['fecha_consulta'] == fecha_ayer) & (df_hist['meta'].isin(metas_sel))]
        df_ayer_grp = df_ayer.groupby(['meta', 'fuente', 'especifica'], as_index=False)[['pim', 'dev']].sum()
        df_ayer_grp['% Ejec Ayer'] = (df_ayer_grp['dev'] / df_ayer_grp['pim'] * 100).fillna(0)

        df_var_diaria = pd.merge(
            df_acum[['meta', 'fuente', 'especifica', 'especifica_nombre', 'pim', 'dev', '% Ejec (Dev/PIM)']],
            df_ayer_grp[['meta', 'fuente', 'especifica', 'dev', '% Ejec Ayer']],
            on=['meta', 'fuente', 'especifica'], suffixes=('_Hoy', '_Ayer'), how='left'
        ).fillna(0)
        df_var_diaria['Var_Dev_Diaria'] = df_var_diaria['dev_Hoy'] - df_var_diaria['dev_Ayer']
        df_var_diaria['Var_%Ejec_Diaria'] = (df_var_diaria['% Ejec (Dev/PIM)'] - df_var_diaria['% Ejec Ayer']).round(2)

    # 4. Acumulado Mes a Mes
    df_mensual = df_corte.pivot_table(
        index=['meta', 'fuente', 'especifica', 'especifica_nombre'],
        columns='mes_eje', values='dev', aggfunc='sum', fill_value=0
    ).reset_index()

    # Pestañas visuales
    t1, t2, t3, t4 = st.tabs(["📌 Acumulado Hoy", f"📅 Último Mes ({mes_actual})", "📈 Variación Diaria", "📊 Mes a Mes"])
    with t1: st.dataframe(df_acum, use_container_width=True)
    with t2: st.dataframe(df_mes, use_container_width=True)
    with t3:
        if not df_var_diaria.empty:
            st.dataframe(df_var_diaria, use_container_width=True)
        else:
            st.warning("Vuelve a actualizar mañana para ver la comparación Hoy vs. Ayer.")
    with t4: st.dataframe(df_mensual, use_container_width=True)

    # Descarga Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_acum.to_excel(writer, index=False, sheet_name='Acumulado_Hoy')
        df_mes.to_excel(writer, index=False, sheet_name='Ultimo_Mes')
        if not df_var_diaria.empty:
            df_var_diaria.to_excel(writer, index=False, sheet_name='Variacion_Diaria')
        df_mensual.to_excel(writer, index=False, sheet_name='Mes_a_Mes')

    st.sidebar.download_button(
        label="📥 Descargar Excel (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"SUNASS_MEF_{fecha_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
  
