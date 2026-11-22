import io
import json
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Monitor Presupuestal SUNASS - MEF", page_icon="🇵🇪", layout="wide")
st.title("📊 Monitor Presupuestal SUNASS (Consulta Amigable MEF)")

NOMBRE_SHEET = "Historial_MEF_SUNASS"

@st.cache_resource
def conectar_gsheets():
    p = "https://"
    g = "googleapis.com"
    s1 = p + "www." + g + "/auth/spreadsheets"
    s2 = p + "www." + g + "/auth/drive"
    info = json.loads(st.secrets["json_crudo"], strict=False)
    info["auth_uri"] = p + "accounts." + "google.com"
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

    if 'Fecha' in df.columns:
        df['Fecha'] = df['Fecha'].apply(
            lambda x: pd.to_datetime(x, unit='D', origin='1899-12-30').strftime('%Y-%m-%d')
            if isinstance(x, (int, float)) else str(x).strip()
        )
    if 'ConsultaRealizada' in df.columns:
        partes = df['ConsultaRealizada'].astype(str).str.split('|', expand=True)
        df['Meta'] = partes.get(0, '').astype(str).str.strip()
        df['Fuente'] = partes.get(1, '').astype(str).str.strip()
        df['Generica'] = partes.get(2, '').astype(str).str.strip()

    num_cols = [
        "PIA", "PIM", "Certificacion", "Compromiso", "AtencionMensual", "Devengado", "Girado",
        "PIM-CERT", "CERT-COMP", "COMP-CM", "CM-DEV", "DEV-GIR", "PIM-DEV", "%Ejec.",
        "Dif_PIA", "Dif_PIM", "Dif_Certificacion", "Dif_Compromiso", "Dif_AtencionMensual",
        "Dif_Devengado", "Dif_Girado", "Dif_PIM-CERT", "Dif_CERT-COMP", "Dif_COMP-CM",
        "Dif_CM-DEV", "Dif_DEV-GIR", "Dif_PIM-DEV", "Dif_%Ejec."
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    return df

def construir_td(df, cols_suma, incluir_pct=True):
    if df.empty:
        return pd.DataFrame()
    bloques = []
    for (prog, fuente, gen), grp in df.groupby(["Programa", "Fuente", "Generica"], sort=True):
        sub = grp[["EspecificaCompleta"] + cols_suma].copy()
        sub.insert(0, "Grupo (Prog | Fuente | Gen)", f"{prog} | {fuente} | {gen}")
        if incluir_pct and "PIM" in cols_suma and "Devengado" in cols_suma:
            sub["%Ejec."] = sub.apply(lambda r: (r["Devengado"] / r["PIM"] * 100) if r["PIM"] != 0 else 0.0, axis=1)
        bloques.append(sub)

        tot_grp = grp[cols_suma].sum().to_dict()
        tot_grp["Grupo (Prog | Fuente | Gen)"] = f"▶ SUBTOTAL {prog} | {fuente} | {gen}"
        tot_grp["EspecificaCompleta"] = ""
        if incluir_pct and "PIM" in cols_suma and "Devengado" in cols_suma:
            tot_grp["%Ejec."] = (tot_grp["Devengado"] / tot_grp["PIM"] * 100) if tot_grp["PIM"] != 0 else 0.0
        bloques.append(pd.DataFrame([tot_grp]))

    tot_gen = df[cols_suma].sum().to_dict()
    tot_gen["Grupo (Prog | Fuente | Gen)"] = "🏆 TOTAL GENERAL"
    tot_gen["EspecificaCompleta"] = ""
    if incluir_pct and "PIM" in cols_suma and "Devengado" in cols_suma:
        tot_gen["%Ejec."] = (tot_gen["Devengado"] / tot_gen["PIM"] * 100) if tot_gen["PIM"] != 0 else 0.0
    bloques.append(pd.DataFrame([tot_gen]))

    res = pd.concat(bloques, ignore_index=True)
    cols_orden = ["Grupo (Prog | Fuente | Gen)", "EspecificaCompleta"] + cols_suma + (["%Ejec."] if incluir_pct and "PIM" in cols_suma else [])
    return res[cols_orden]

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

    solo_dre = st.sidebar.checkbox("Solo Área DRE (Metas 1 y 61)")
    metas_disp = sorted(df_cons['Meta'].unique())
    metas_default = [m for m in ['1', '61'] if m in metas_disp] if solo_dre else metas_disp
    metas = st.sidebar.multiselect("Meta:", metas_disp, default=metas_default)

    fuentes_disp = sorted(df_cons['Fuente'].unique())
    fuentes = st.sidebar.multiselect("Fuente:", fuentes_disp, default=fuentes_disp)

    gen_disp = sorted(df_cons['Generica'].unique())
    genericas = st.sidebar.multiselect("Genérica:", gen_disp, default=gen_disp)

    solo_pim_mayor_0 = st.sidebar.checkbox("Solo PIM > 0", value=True)

    df_view = df_cons[
        (df_cons['Fecha'] == fecha_sel) &
        (df_cons['Meta'].isin(metas)) &
        (df_cons['Fuente'].isin(fuentes)) &
        (df_cons['Generica'].isin(genericas))
    ].copy()
    if solo_pim_mayor_0:
        df_view = df_view[df_view['PIM.'] == 'PIM>0']

    c1, c2, c3, c4 = st.columns(4)
    pim_tot = df_view['PIM'].sum()
    dev_tot = df_view['Devengado'].sum()
    dif_dev = df_view['Dif_Devengado'].sum()
    pct_tot = (dev_tot / pim_tot * 100) if pim_tot > 0 else 0

    c1.metric("PIM Total", f"S/ {pim_tot:,.2f}")
    c2.metric("Devengado Acumulado", f"S/ {dev_tot:,.2f}", f"S/ {dif_dev:,.2f} hoy")
    c3.metric("% Ejecución (Dev/PIM)", f"{pct_tot:.2f}%")
    c4.metric("Saldo PIM - Dev", f"S/ {(pim_tot - dev_tot):,.2f}")

    t_diario, t_mensual, t_vars, t_crudo = st.tabs([
        "📊 TD Diario (Acumulado)",
        "📅 TD Mensual (Enero - Diciembre)",
        "📈 TD Variaciones del Día (13 Hojas)",
        "📋 Datos Crudos"
    ])

    with t_diario:
        cols_diario = ["PIA", "PIM", "Certificacion", "Compromiso", "AtencionMensual", "Devengado", "Girado", "PIM-CERT", "CERT-COMP", "COMP-CM", "CM-DEV", "DEV-GIR", "PIM-DEV"]
        td_d = construir_td(df_view, cols_diario, incluir_pct=True)
        fmt_d = {c: "S/ {:,.2f}" for c in cols_diario}
        fmt_d["%Ejec."] = "{:.2f}%"
        st.dataframe(td_d.style.format(fmt_d), use_container_width=True, height=560)

    with t_mensual:
        if not df_mens.empty:
            metrica_m = st.selectbox(
                "Variable mensual a resumir:",
                ["Devengado", "Certificacion", "Compromiso", "AtencionMensual", "Girado"],
                index=0
            )
            df_m = df_mens[
                (df_mens['Meta'].isin(metas)) &
                (df_mens['Fuente'].isin(fuentes)) &
                (df_mens['Generica'].isin(genericas))
            ].copy()

            orden_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]
            meses_disp = [m for m in orden_meses if m in df_m["Mes"].unique()]

            piv = df_m.pivot_table(
                index=["Programa", "Fuente", "Generica", "EspecificaCompleta"],
                columns="Mes",
                values=metrica_m,
                aggfunc="sum",
                fill_value=0.0
            ).reset_index()

            cols_m = [m for m in meses_disp if m in piv.columns]
            piv["Total General"] = piv[cols_m].sum(axis=1)
            td_m = construir_td(piv, cols_m + ["Total General"], incluir_pct=False)
            fmt_m = {c: "S/ {:,.2f}" for c in cols_m + ["Total General"]}
            st.dataframe(td_m.style.format(fmt_m), use_container_width=True, height=560)

    with t_vars:
        mapa_vars = {
            "PIM": ("PIM", "Dif_PIM", ".PIM"),
            "CERT (Certificación)": ("Certificacion", "Dif_Certificacion", ".Certificacion"),
            "COMP (Compromiso)": ("Compromiso", "Dif_Compromiso", ".Compromiso"),
            "CM (Atención Mensual)": ("AtencionMensual", "Dif_AtencionMensual", ".AtencionMensual"),
            "DEV (Devengado)": ("Devengado", "Dif_Devengado", ".Devengado"),
            "GIR (Girado)": ("Girado", "Dif_Girado", ".Girado"),
            "PIM-CERT": ("PIM-CERT", "Dif_PIM-CERT", ".PIM-CERT"),
            "CERT-COMP": ("CERT-COMP", "Dif_CERT-COMP", ".CERT-COMP"),
            "COMP-CM": ("COMP-CM", "Dif_COMP-CM", ".COMP-CM"),
            "CM-DEV": ("CM-DEV", "Dif_CM-DEV", ".CM-DEV"),
            "DEV-GIR": ("DEV-GIR", "Dif_DEV-GIR", ".DEV-GIR"),
            "PIM-DEV": ("PIM-DEV", "Dif_PIM-DEV", ".PIM-DEV"),
            "%Ejec.": ("%Ejec.", "Dif_%Ejec.", ".%Ejec.")
        }
        var_sel = st.selectbox("Selecciona la pestaña de variación diaria:", list(mapa_vars.keys()), index=4)
        col_act, col_dif, col_flag = mapa_vars[var_sel]

        df_v = df_cons[
            (df_cons['Fecha'] == fecha_sel) &
            (df_cons['Meta'].isin(metas)) &
            (df_cons['Fuente'].isin(fuentes)) &
            (df_cons['Generica'].isin(genericas)) &
            (df_cons[col_flag] == col_flag)
        ].copy()

        if df_v.empty:
            st.info(f"No se registraron movimientos en {var_sel} para la fecha {fecha_sel} con los filtros actuales.")
        else:
            td_v = construir_td(df_v, [col_act, col_dif], incluir_pct=False)
            fmt_v = {col_act: "{:.2f}%", col_dif: "{:+.2f}%"} if "%Ejec." in var_sel else {col_act: "S/ {:,.2f}", col_dif: "S/ {:+,.2f}"}
            st.dataframe(td_v.style.format(fmt_v), use_container_width=True, height=520)

    with t_crudo:
        st.subheader("Consolidado Acumulado (Detalle)")
        st.dataframe(df_view, use_container_width=True)
        st.subheader("Ejecución Mensual (Detalle)")
        st.dataframe(df_mens, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        td_d.to_excel(writer, index=False, sheet_name='TD_Diario')
        if not df_mens.empty:
td_m.to_excel(writer, index=False, sheet_name='TD_Mensual')
df_cons.to_excel(writer, index=False, sheet_name='MEF_Consolidado_Unico')
df_mens.to_excel(writer, index=False, sheet_name='tblMensual')
st.sidebar.download_button(
label="📥 Descargar Excel con TDs (.xlsx)",
data=buffer.getvalue(),
file_name=f"SUNASS_MEF_{fecha_sel}.xlsx",
mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

