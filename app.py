import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from io import BytesIO

st.set_page_config(page_title="Monitor Presupuestal MEF - SUNASS", page_icon="🇵🇪", layout="wide")

st.title("🇵🇪 Monitor de Ejecución Presupuestal MEF - SUNASS")

@st.cache_data(ttl=120)
def cargar_datos():
    scopes = ["https://googleapis.com"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open("Historial_MEF_SUNASS")

    def leer_hoja(nombre):
        ws = sh.worksheet(nombre)
        data = ws.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame()
        df = pd.DataFrame(data[1:], columns=data[0])
        num_cols = [
            "PIA", "PIM", "Certificacion", "Compromiso", "AtencionMensual", "Devengado", "Girado",
            "PIM-CERT", "CERT-COMP", "COMP-CM", "CM-DEV", "DEV-GIR", "PIM-DEV", "%Ejec.",
            "Dif_PIA", "Dif_PIM", "Dif_Certificacion", "Dif_Compromiso", "Dif_AtencionMensual",
            "Dif_Devengado", "Dif_Girado", "Dif_PIM-CERT", "Dif_CERT-COMP", "Dif_COMP-CM",
            "Dif_CM-DEV", "Dif_DEV-GIR", "Dif_PIM-DEV", "Dif_%Ejec."
        ]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0.0)
        return df

    return leer_hoja("MEF_Consolidado_Unico"), leer_hoja("tblMensual")

def tabla_con_subtotales(df, cols_suma, incluir_pct=True):
    if df.empty:
        return pd.DataFrame()
    bloques = []
    for (prog, fuente, gen), grp in df.groupby(["Programa", "Fuente", "Generica"], sort=True):
        sub = grp[["EspecificaCompleta"] + cols_suma].copy()
        sub.insert(0, "Nivel", f"{prog} | {fuente} | {gen}")
        if incluir_pct and "PIM" in cols_suma and "Devengado" in cols_suma:
            sub["%Ejec."] = sub.apply(lambda r: (r["Devengado"] / r["PIM"] * 100) if r["PIM"] != 0 else 0.0, axis=1)
        bloques.append(sub)

        tot_grp = grp[cols_suma].sum().to_dict()
        tot_grp["Nivel"] = f"Total {prog} | {fuente} | {gen}"
        tot_grp["EspecificaCompleta"] = "SUBTOTAL"
        if incluir_pct and "PIM" in cols_suma and "Devengado" in cols_suma:
            tot_grp["%Ejec."] = (tot_grp["Devengado"] / tot_grp["PIM"] * 100) if tot_grp["PIM"] != 0 else 0.0
        bloques.append(pd.DataFrame([tot_grp]))

    tot_gen = df[cols_suma].sum().to_dict()
    tot_gen["Nivel"] = "TOTAL GENERAL"
    tot_gen["EspecificaCompleta"] = ""
    if incluir_pct and "PIM" in cols_suma and "Devengado" in cols_suma:
        tot_gen["%Ejec."] = (tot_gen["Devengado"] / tot_gen["PIM"] * 100) if tot_gen["PIM"] != 0 else 0.0
    bloques.append(pd.DataFrame([tot_gen]))

    res = pd.concat(bloques, ignore_index=True)
    cols_orden = ["Nivel", "EspecificaCompleta"] + cols_suma + (["%Ejec."] if incluir_pct and "PIM" in cols_suma else [])
    return res[cols_orden]

def descargar_excel(df_export, nombre_archivo):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Reporte")
    return buffer.getvalue()

col_btn, _ = st.columns([1, 4])
if col_btn.button("🔄 Refrescar Vista Web"):
    st.cache_data.clear()
    st.rerun()

df_cons, df_mens = cargar_datos()

if df_cons.empty:
    st.warning("No hay datos disponibles en MEF_Consolidado_Unico.")
    st.stop()

# Barra lateral de filtros globales (idénticos a los filtros superiores de tus TDs)
st.sidebar.header("Filtros Globales")
fechas = sorted(df_cons["Fecha"].unique(), reverse=True)
fecha_sel = st.sidebar.selectbox("Fecha de corte", fechas, index=0)
area_sel = st.sidebar.radio("Área", ["DRE (Metas 1 y 61)", "Meta 160", "Todas"], index=0)
solo_pim = st.sidebar.checkbox("Solo PIM > 0", value=True)
gens_disp = sorted(df_cons["Generica"].unique())
gen_sel = st.sidebar.multiselect("Genérica", gens_disp, default=gens_disp)

df_f = df_cons[df_cons["Fecha"] == fecha_sel].copy()
if area_sel == "DRE (Metas 1 y 61)":
    df_f = df_f[df_f["Area."] == "DRE."]
elif area_sel == "Meta 160":
    df_f = df_f[df_f["Area."] != "DRE."]
if solo_pim:
    df_f = df_f[df_f["PIM"] > 0]
if gen_sel:
    df_f = df_f[df_f["Generica"].isin(gen_sel)]

# Tarjetas KPI superiores
pim_tot = df_f["PIM"].sum()
cert_tot = df_f["Certificacion"].sum()
comp_tot = df_f["Compromiso"].sum()
dev_tot = df_f["Devengado"].sum()
ejec_tot = (dev_tot / pim_tot * 100) if pim_tot != 0 else 0.0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("PIM Total", f"S/ {pim_tot:,.2f}")
k2.metric("Certificado", f"S/ {cert_tot:,.2f}")
k3.metric("Comprometido", f"S/ {comp_tot:,.2f}")
k4.metric("Devengado", f"S/ {dev_tot:,.2f}")
k5.metric("% Ejecución (Dev/PIM)", f"{ejec_tot:.2f}%")

tab_diario, tab_mensual, tab_vars = st.tabs([
    "📊 Diario (Acumulado)",
    "📅 Mensual (Enero - Diciembre)",
    "📈 Variaciones del Día (13 Variables)"
])

with tab_diario:
    cols_diario = ["PIA", "PIM", "Certificacion", "Compromiso", "AtencionMensual", "Devengado", "Girado", "PIM-CERT", "CERT-COMP", "COMP-CM", "CM-DEV", "DEV-GIR", "PIM-DEV"]
    td_diario = tabla_con_subtotales(df_f, cols_diario, incluir_pct=True)
    fmt_d = {c: "S/ {:,.2f}" for c in cols_diario}
    fmt_d["%Ejec."] = "{:.2f}%"
    st.dataframe(td_diario.style.format(fmt_d), use_container_width=True, height=550)
    st.download_button("⬇️ Descargar Diario en Excel", descargar_excel(td_diario, "Diario.xlsx"), f"MEF_Diario_{fecha_sel}.xlsx")

with tab_mensual:
    if not df_mens.empty:
        metrica_m = st.selectbox("Variable mensual a visualizar", ["Devengado", "Certificacion", "Compromiso", "AtencionMensual", "Girado"], index=0)
        df_m = df_mens.copy()
        if area_sel == "DRE (Metas 1 y 61)":
            df_m = df_m[df_m["Meta"].isin(["1", "61"])]
        elif area_sel == "Meta 160":
            df_m = df_m[df_m["Meta"] == "160"]
        if gen_sel:
            df_m = df_m[df_m["Generica"].isin(gen_sel)]

        orden_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]
        meses_presentes = [m for m in orden_meses if m in df_m["Mes"].unique()]

        piv = df_m.pivot_table(
            index=["Programa", "Fuente", "Generica", "EspecificaCompleta"],
            columns="Mes",
            values=metrica_m,
            aggfunc="sum",
            fill_value=0.0
        ).reset_index()

        cols_m = [m for m in meses_presentes if m in piv.columns]
        piv["Total General"] = piv[cols_m].sum(axis=1)
        td_mensual = tabla_con_subtotales(piv, cols_m + ["Total General"], incluir_pct=False)
        fmt_m = {c: "S/ {:,.2f}" for c in cols_m + ["Total General"]}
        st.dataframe(td_mensual.style.format(fmt_m), use_container_width=True, height=550)
        st.download_button("⬇️ Descargar Mensual en Excel", descargar_excel(td_mensual, "Mensual.xlsx"), f"MEF_Mensual_{metrica_m}.xlsx")

with tab_vars:
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
    var_sel = st.selectbox("Selecciona la pestaña de variación diaria", list(mapa_vars.keys()), index=4)
    col_actual, col_dif, col_flag = mapa_vars[var_sel]

    df_v = df_cons[(df_cons["Fecha"] == fecha_sel) & (df_cons[col_flag] != "-")].copy()
    if area_sel == "DRE (Metas 1 y 61)":
        df_v = df_v[df_v["Area."] == "DRE."]
    elif area_sel == "Meta 160":
        df_v = df_v[df_v["Area."] != "DRE."]
    if gen_sel:
        df_v = df_v[df_v["Generica"].isin(gen_sel)]

    if df_v.empty:
        st.info(f"No se registraron variaciones en {var_sel} para la fecha {fecha_sel}.")
    else:
        td_var = tabla_con_subtotales(df_v, [col_actual, col_dif], incluir_pct=False)
        fmt_v = {col_actual: "{:.2f}%", col_dif: "{:+.2f}%"} if "%Ejec." in var_sel else {col_actual: "S/ {:,.2f}", col_dif: "S/ {:+,.2f}"}
        st.dataframe(td_var.style.format(fmt_v), use_container_width=True, height=500)
        st.download_button(f"⬇️ Descargar {var_sel} en Excel", descargar_excel(td_var, "Variacion.xlsx"), f"MEF_Var_{var_sel.split()[0]}_{fecha_sel}.xlsx")
