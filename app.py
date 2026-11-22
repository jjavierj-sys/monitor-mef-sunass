import io
import json
import altair as alt
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Monitor DRE - SUNASS",
    page_icon="🇵🇪",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .block-container { padding-top: 1.2rem; padding-bottom: 1.5rem; max-width: 900px; }
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px 12px;
        border-radius: 10px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.35rem !important;
    }
    table td, table th {
        white-space: normal !important;
        word-wrap: break-word !important;
        font-size: 0.85rem !important;
        vertical-align: middle !important;
    }
    /* Mantiene bloques de 2 columnas en celular para evitar listas largas */
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 0.5rem !important;
        }
        div[data-testid="stHorizontalBlock"] > div {
            width: 100% !important;
            min-width: 0 !important;
        }
    }
    </style>
""", unsafe_allow_html=True)


st.markdown(
    "<div style='font-size: 1.25rem; font-weight: 700; line-height: 1.25; margin-top: 0.25rem; margin-bottom: 0.75rem; white-space: normal;'>🇵🇪 Monitor Presupuestal DRE - SUNASS</div>",
    unsafe_allow_html=True
)


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

def mapear_unidad(meta):
    m = str(meta).strip()
    if m == "1":
        return "SRT"
    elif m == "61":
        return "SDEM"
    return f"Meta {m}"

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
        df = df[df['Meta'].isin(['1', '61'])].copy()
        df['Unidad'] = df['Meta'].apply(mapear_unidad)

    num_cols = [
        "PIA", "PIM", "Certificacion", "Compromiso", "AtencionMensual", "Devengado", "Girado",
        "Dif_PIA", "Dif_PIM", "Dif_Certificacion", "Dif_Compromiso", "Dif_AtencionMensual",
        "Dif_Devengado", "Dif_Girado"
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

    return df

# Barra superior compacta
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

# Inicializar estado de filtros para el botón limpiador
if "fecha_sel" not in st.session_state or st.session_state.fecha_sel not in fechas:
    st.session_state.fecha_sel = fechas[0]
if "unidad_opt" not in st.session_state:
    st.session_state.unidad_opt = "DRE (Global)"
if "fuente_opt" not in st.session_state:
    st.session_state.fuente_opt = "Todas"
if "gen_opt" not in st.session_state:
    st.session_state.gen_opt = "Todas"

def limpiar_filtros():
    st.session_state.fecha_sel = fechas[0]
    st.session_state.unidad_opt = "DRE (Global)"
    st.session_state.fuente_opt = "Todas"
    st.session_state.gen_opt = "Todas"

with col_fec:
    fecha_sel = st.selectbox("Fecha de corte", fechas, key="fecha_sel", label_visibility="collapsed")

# Filtros rápidos en cuadrícula compacta 2x2
f1, f2 = st.columns(2)
unidad_opt = f1.selectbox(
    "Unidad Orgánica",
    ["DRE (Global)", "SRT", "SDEM"],
    key="unidad_opt"
)
fuente_opt = f2.selectbox(
    "Fuente",
    ["Todas", "RO", "RDR"],
    key="fuente_opt"
)

f3, f4 = st.columns([2, 1.2])
gen_opt = f3.selectbox(
    "Genérica",
    ["Todas", "2.1", "2.3", "2.3 (Sin practicantes)"],
    key="gen_opt"
)
with f4:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    st.button("🧹 Limpiar", on_click=limpiar_filtros, use_container_width=True)

def filtrar_unidad(df):
    if unidad_opt == "SRT":
        return df[df['Unidad'] == "SRT"]
    elif unidad_opt == "SDEM":
        return df[df['Unidad'] == "SDEM"]
    return df

def filtrar_generica(df):
    if gen_opt == "2.1":
        return df[df['Generica'].astype(str).str.startswith("2.1")]
    elif gen_opt == "2.3":
        return df[df['Generica'].astype(str).str.startswith("2.3")]
    elif gen_opt == "2.3 (Sin practicantes)":
        return df[
            (df['Generica'].astype(str).str.startswith("2.3")) &
            (~df['EspecificaCompleta'].astype(str).str.startswith("2.3.2.7.5.2"))
        ]
    return df

# Base filtrada por Fecha, Fuente y Genérica
df_fecha = filtrar_generica(df_cons[df_cons['Fecha'] == fecha_sel].copy())
if fuente_opt != "Todas":
    df_fecha = df_fecha[df_fecha['Fuente'] == fuente_opt]

df_view = filtrar_unidad(df_fecha)

# 4 KPIs Principales (con respaldo automático al último corte válido si hoy está vacío)
if df_view.empty or df_view['PIM'].sum() == 0:
    df_hist_comb = filtrar_generica(filtrar_unidad(df_cons.copy()))
    if fuente_opt != "Todas":
        df_hist_comb = df_hist_comb[df_hist_comb['Fuente'] == fuente_opt]
    df_hist_comb = df_hist_comb[df_hist_comb['PIM'] > 0]
    if not df_hist_comb.empty:
        ultima_fec_valida = df_hist_comb['Fecha'].max()
        df_view = df_hist_comb[df_hist_comb['Fecha'] == ultima_fec_valida]

pim_tot = df_view['PIM'].sum()
dev_tot = df_view['Devengado'].sum()
dif_dev = df_view['Dif_Devengado'].sum()
pct_tot = (dev_tot / pim_tot * 100) if pim_tot > 0 else 0.0
saldo_tot = pim_tot - dev_tot

k1, k2 = st.columns(2)
k1.metric(f"PIM {unidad_opt}", f"{pim_tot:,.2f}")
k2.metric("Devengado", f"{dev_tot:,.2f}", f"{dif_dev:+,.2f} hoy" if abs(dif_dev) > 0 else "Sin cambio hoy")

k3, k4 = st.columns(2)
k3.metric("% Ejecución", f"{pct_tot:.2f}%")
k4.metric("Saldo (PIM - Dev)", f"{saldo_tot:,.2f}")

tab_resumen, tab_movs, tab_mes = st.tabs([
    "📌 Resumen",
    "⚡ Movimientos Hoy",
    "📅 Mensual"
])

with tab_resumen:
    if df_view.empty:
        st.warning("Sin datos para los filtros seleccionados.")
    else:
        res = df_view.groupby(["Unidad"], as_index=False)[
            ["PIM", "Certificacion", "Devengado"]
        ].sum()
        res["%Ejec."] = res.apply(lambda r: (r["Devengado"] / r["PIM"] * 100) if r["PIM"] > 0 else 0.0, axis=1)

        tot_row = pd.DataFrame([{
            "Unidad": f"TOTAL {unidad_opt}",
            "PIM": res["PIM"].sum(),
            "Certificacion": res["Certificacion"].sum(),
            "Devengado": res["Devengado"].sum(),
            "%Ejec.": pct_tot
        }])
        tabla_res = pd.concat([res[["Unidad", "PIM", "Certificacion", "Devengado", "%Ejec."]], tot_row], ignore_index=True)

        def fmt_cero_blanco(v, dec=2, suf=""):
            return "" if abs(v) < 1e-6 else f"{v:,.{dec}f}{suf}"

        styler_res = tabla_res.style.format({
            "PIM": lambda x: fmt_cero_blanco(x),
            "Certificacion": lambda x: fmt_cero_blanco(x),
            "Devengado": lambda x: fmt_cero_blanco(x),
            "%Ejec.": lambda x: fmt_cero_blanco(x, 2, "%")
        })

        st.table(styler_res)

        st.caption("Ejecución por Unidad Orgánica — Barra ancha gris: PIM | Barra interior azul: Devengado")
        if unidad_opt == "DRE (Global)":
            g_unidades = df_fecha.groupby("Unidad", as_index=False)[["PIM", "Devengado"]].sum()
            g_dre = pd.DataFrame([{
                "Unidad": "DRE (Global)",
                "PIM": df_fecha["PIM"].sum(),
                "Devengado": df_fecha["Devengado"].sum()
            }])
            chart_df = pd.concat([g_dre, g_unidades], ignore_index=True)
            orden_u = ["DRE (Global)", "SRT", "SDEM"]
        else:
            chart_df = df_view.groupby("Unidad", as_index=False)[["PIM", "Devengado"]].sum()
            orden_u = [unidad_opt]

        chart_df["Porcentaje"] = chart_df.apply(lambda r: f"{(r['Devengado']/r['PIM']*100):.2f}%" if r["PIM"] > 0 else "0.00%", axis=1)

        barra_pim = alt.Chart(chart_df).mark_bar(
            color="#D0D7DE",
            size=52,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4
        ).encode(
            x=alt.X("Unidad:N", sort=orden_u, title=None, axis=alt.Axis(labelAngle=0, labelFontWeight="bold")),
            y=alt.Y("PIM:Q", title="Monto (S/)"),
            tooltip=["Unidad", alt.Tooltip("PIM:Q", format=",.2f"), alt.Tooltip("Devengado:Q", format=",.2f"), "Porcentaje"]
        )

        barra_dev = alt.Chart(chart_df).mark_bar(
            color="#0052CC",
            size=24,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4
        ).encode(
            x=alt.X("Unidad:N", sort=orden_u),
            y=alt.Y("Devengado:Q"),
            tooltip=["Unidad", alt.Tooltip("PIM:Q", format=",.2f"), alt.Tooltip("Devengado:Q", format=",.2f"), "Porcentaje"]
        )

        etiquetas = alt.Chart(chart_df).mark_text(
            dy=-10,
            color="#0052CC",
            fontWeight="bold",
            fontSize=12
        ).encode(
            x=alt.X("Unidad:N", sort=orden_u),
            y=alt.Y("Devengado:Q"),
            text=alt.Text("Porcentaje:N")
        )

        st.altair_chart((barra_pim + barra_dev + etiquetas).properties(height=280), use_container_width=True)

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
                    "Unidad": f"{row['Unidad']} | {row['Generica']}",
                    "Específica": row["EspecificaCompleta"],
                    "Rubro": nombre_etapa,
                    "Acumulado": row[col_act],
                    "Variación": val_dif
                })

    if not movs:
        st.info("No se registraron variaciones presupuestales en esta fecha.")
    else:
        df_movs = pd.DataFrame(movs)

        # Orden presupuestal oficial por fase de gasto + importe de positivo a negativo
        orden_fases = {
            "PIM": 1,
            "Certificación": 2,
            "Compromiso": 3,
            "At. Mensual": 4,
            "Devengado": 5,
            "Girado": 6
        }
        df_movs["_orden_fase"] = df_movs["Rubro"].map(orden_fases).fillna(99)
        df_movs = df_movs.sort_values(
            by=["_orden_fase", "Variación"],
            ascending=[True, False]
        ).drop(columns=["_orden_fase"]).reset_index(drop=True)

        rubros_disp = ["Todos"] + [r for r in orden_fases.keys() if r in df_movs["Rubro"].unique()]
        rubro_sel = st.selectbox("Filtrar por rubro:", rubros_disp, label_visibility="collapsed")
        if rubro_sel != "Todos":
            df_movs = df_movs[df_movs["Rubro"] == rubro_sel]

        def color_mov(v):
            return "color: #0052CC; font-weight: bold;" if v > 0 else "color: #D93025; font-weight: bold;"

        styler_mov = df_movs.style.format({
            "Acumulado": "{:,.2f}",
            "Variación": "{:+,.2f}"
        }).map(color_mov, subset=["Variación"])

        st.table(styler_mov)

with tab_mes:
    if df_mens.empty:
        st.info("Sin datos mensuales cargados.")
    else:
        var_m = st.selectbox("Variable mensual", ["Devengado", "Certificacion", "Compromiso", "AtencionMensual", "Girado"], label_visibility="collapsed")
        df_m = filtrar_generica(filtrar_unidad(df_mens.copy()))
        if fuente_opt != "Todas":
            df_m = df_m[df_m['Fuente'] == fuente_opt]

        orden_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]
        res_m = df_m.groupby("Mes", as_index=False)[var_m].sum()
        res_m["Orden"] = res_m["Mes"].apply(lambda m: orden_meses.index(m) if m in orden_meses else 99)
        res_m = res_m.sort_values("Orden").drop(columns=["Orden"]).reset_index(drop=True)

        chart_mes = alt.Chart(res_m).mark_bar(
            color="#0052CC",
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4
        ).encode(
            x=alt.X(
                "Mes:N",
                sort=orden_meses,
                title=None,
                axis=alt.Axis(labelAngle=-45, labelOverlap=False, labelFontSize=10)
            ),
            y=alt.Y(f"{var_m}:Q", title="Monto (S/)"),
            tooltip=["Mes", alt.Tooltip(f"{var_m}:Q", format=",.2f")]
        ).properties(height=260)

        st.altair_chart(chart_mes, use_container_width=True)
        st.table(
            res_m.set_index("Mes").style.format({var_m: lambda x: "" if abs(x) < 1e-6 else f"{x:,.2f}"})
        )

# Descarga Excel solo con la información de la DRE
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df_cons.to_excel(writer, index=False, sheet_name='Consolidado_DRE')
    df_mens.to_excel(writer, index=False, sheet_name='Mensual_DRE')

st.download_button(
    label="📥 Descargar Excel DRE (.xlsx)",
    data=buffer.getvalue(),
    file_name=f"SUNASS_DRE_{fecha_sel}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)
