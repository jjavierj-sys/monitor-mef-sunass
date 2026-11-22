import io
import json
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="SUNASS MEF",
    page_icon="🇵🇪",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 900px; }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 12px 14px;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🇵🇪 Monitor MEF - SUNASS")

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
        "Dif_PIA", "Dif_PIM", "Dif_Certificacion", "Dif_Compromiso", "Dif_AtencionMensual",
        "Dif_Devengado", "Dif_Girado"
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    return df

# Barra superior compacta (funciona perfecto en celular)
col_ref, col_fec = st.columns([1, 2])
with col_ref:
    if st.button("🔄 Actualizar", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

df_cons = leer_pestana("MEF_Consolidado_Unico")
df_mens = leer_pestana("tblMensual")

if df_cons.empty:
    st.info("Ejecuta 'Actualizar Todo MEF (Hoy)' en Google Sheets para cargar los datos.")
    st.stop()

fechas = sorted(df_cons['Fecha'].unique(), reverse=True)
with col_fec:
    fecha_sel = st.selectbox("Fecha de corte", fechas, label_visibility="collapsed")

# Filtros rápidos horizontales
f1, f2, f3 = st.columns(3)
area_opt = f1.selectbox("Área", ["DRE (1 y 61)", "Todas", "Meta 160"], index=0)
fuente_opt = f2.selectbox("Fuente", ["Todas", "RO", "RDR"], index=0)
gen_opt = f3.selectbox("Genérica", ["Todas", "2.1", "2.3"], index=0)

df_view = df_cons[df_cons['Fecha'] == fecha_sel].copy()
if area_opt == "DRE (1 y 61)":
    df_view = df_view[df_view['Meta'].isin(['1', '61'])]
elif area_opt == "Meta 160":
    df_view = df_view[df_view['Meta'] == '160']

if fuente_opt != "Todas":
    df_view = df_view[df_view['Fuente'] == fuente_opt]
if gen_opt != "Todas":
    df_view = df_view[df_view['Generica'] == gen_opt]

# 4 KPIs Principales (2x2 automático en celular)
pim_tot = df_view['PIM'].sum()
dev_tot = df_view['Devengado'].sum()
dif_dev = df_view['Dif_Devengado'].sum()
pct_tot = (dev_tot / pim_tot * 100) if pim_tot > 0 else 0.0
saldo_tot = pim_tot - dev_tot

k1, k2 = st.columns(2)
k1.metric("PIM Total", f"{pim_tot:,.2f}")
k2.metric("Devengado", f"{dev_tot:,.2f}", f"{dif_dev:+,.2f} hoy" if abs(dif_dev) > 0 else "Sin cambio hoy")

k3, k4 = st.columns(2)
k3.metric("% Ejecución", f"{pct_tot:.2f}%")
k4.metric("Saldo (PIM - Dev)", f"{saldo_tot:,.2f}")

# 3 Pestañas Ejecutivas
tab_resumen, tab_movs, tab_mes = st.tabs([
    "📌 Resumen",
    "⚡ Movimientos Hoy",
    "📅 Mensual"
])

with tab_resumen:
    if df_view.empty:
        st.warning("Sin datos para los filtros seleccionados.")
    else:
        res = df_view.groupby(["Programa", "Fuente", "Generica"], as_index=False)[
            ["PIM", "Certificacion", "Devengado", "Dif_Devengado"]
        ].sum()
        res["%Ejec."] = res.apply(lambda r: (r["Devengado"] / r["PIM"] * 100) if r["PIM"] > 0 else 0.0, axis=1)
        res["Grupo"] = res["Programa"] + " | " + res["Fuente"] + " | " + res["Generica"]

        # Fila Total General
        tot_row = pd.DataFrame([{
            "Grupo": "TOTAL GENERAL",
            "PIM": res["PIM"].sum(),
            "Certificacion": res["Certificacion"].sum(),
            "Devengado": res["Devengado"].sum(),
            "%Ejec.": pct_tot,
            "Dif_Devengado": res["Dif_Devengado"].sum()
        }])
        tabla_res = pd.concat([res[["Grupo", "PIM", "Certificacion", "Devengado", "%Ejec.", "Dif_Devengado"]], tot_row], ignore_index=True)

        def fmt_cero_blanco(v, dec=2, suf=""):
            return "" if abs(v) < 1e-6 else f"{v:,.{dec}f}{suf}"

        def fmt_var_blanco(v):
            return "" if abs(v) < 1e-6 else f"{v:+,.2f}"

        def color_var(v):
            if abs(v) < 1e-6:
                return ""
            return "color: #0052CC; font-weight: bold;" if v > 0 else "color: #D93025; font-weight: bold;"

        styler_res = tabla_res.style.format({
            "PIM": lambda x: fmt_cero_blanco(x),
            "Certificacion": lambda x: fmt_cero_blanco(x),
            "Devengado": lambda x: fmt_cero_blanco(x),
            "%Ejec.": lambda x: fmt_cero_blanco(x, 2, "%"),
            "Dif_Devengado": fmt_var_blanco
        }).map(color_var, subset=["Dif_Devengado"])

        st.dataframe(styler_res, use_container_width=True, hide_index=True)

        st.caption("Comparativo PIM vs. Devengado por Grupo")
        chart_df = res.set_index("Grupo")[["PIM", "Devengado"]]
        st.bar_chart(chart_df, height=260)

with tab_movs:
    st.caption(f"Cambios detectados el {fecha_sel}")
    etapas = [
        ("PIM", "PIM", "Dif_PIM"),
        ("Certificación", "Certificacion", "Dif_Certificacion"),
        ("Compromiso", "Compromiso", "Dif_Compromiso"),
        ("At. Mensual", "AtencionMensual", "Dif_AtencionMensual"),
        ("Devengado", "Devengado", "Dif_Devengado"),
        ("Girado", "Girado", "Dif_Girado")
    ]
    movs = []
    for _, row in df_view.iterrows():
        for nombre_etapa, col_act, col_dif in etapas:
            val_dif = row[col_dif]
            if abs(val_dif) >= 0.01:
                movs.append({
                    "Grupo": f"{row['Programa']} | {row['Fuente']} | {row['Generica']}",
                    "Específica": row["EspecificaCompleta"],
                    "Rubro": nombre_etapa,
                    "Acumulado": row[col_act],
                    "Variación": val_dif
                })

    if not movs:
        st.info("No se registraron variaciones presupuestales en esta fecha.")
    else:
        df_movs = pd.DataFrame(movs)
        rubros_disp = ["Todos"] + sorted(df_movs["Rubro"].unique().tolist())
        rubro_sel = st.selectbox("Filtrar por rubro:", rubros_disp, label_visibility="collapsed")
        if rubro_sel != "Todos":
            df_movs = df_movs[df_movs["Rubro"] == rubro_sel]

        def color_mov(v):
            return "color: #0052CC; font-weight: bold;" if v > 0 else "color: #D93025; font-weight: bold;"

        styler_mov = df_movs.style.format({
            "Acumulado": "{:,.2f}",
            "Variación": "{:+,.2f}"
        }).map(color_mov, subset=["Variación"])

        st.dataframe(styler_mov, use_container_width=True, hide_index=True)

with tab_mes:
    if df_mens.empty:
        st.info("Sin datos mensuales cargados.")
    else:
        var_m = st.selectbox("Variable mensual", ["Devengado", "Certificacion", "Compromiso", "AtencionMensual", "Girado"], label_visibility="collapsed")
        df_m = df_mens.copy()
        if area_opt == "DRE (1 y 61)":
            df_m = df_m[df_m['Meta'].isin(['1', '61'])]
        elif area_opt == "Meta 160":
            df_m = df_m[df_m['Meta'] == '160']
        if fuente_opt != "Todas":
            df_m = df_m[df_m['Fuente'] == fuente_opt]
        if gen_opt != "Todas":
            df_m = df_m[df_m['Generica'] == gen_opt]

        orden_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]
        res_m = df_m.groupby("Mes", as_index=False)[var_m].sum()
        res_m["Orden"] = res_m["Mes"].apply(lambda m: orden_meses.index(m) if m in orden_meses else 99)
        res_m = res_m.sort_values("Orden").drop(columns=["Orden"])

        st.bar_chart(res_m.set_index("Mes")[var_m], height=240)
        st.dataframe(
            res_m.style.format({var_m: lambda x: "" if abs(x) < 1e-6 else f"{x:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

# Descarga Excel al pie
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_cons.to_excel(writer, index=False, sheet_name='MEF_Consolidado_Unico')
    df_mens.to_excel(writer, index=False, sheet_name='tblMensual')

st.download_button(
    label="📥 Descargar Base Completa (.xlsx)",
    data=buffer.getvalue(),
    file_name=f"SUNASS_MEF_{fecha_sel}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
