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
        partes = df['ConsultaRealizada'].astype(str).str.split('|', expand=True)
        df['Meta'] = partes.get(0, '').astype(str).str.strip()
        df['Fuente'] = partes.get(1, '').astype(str).str.strip()
        df['Generica'] = partes.get(2, '').astype(str).str.strip()
        
    return df

def generar_td_subtotales(df, cols_suma, incluir_pct=True):
    if df.empty:
        return pd.DataFrame()
    df_work = df.copy()
    for c in cols_suma:
        df_work[c] = pd.to_numeric(df_work[c], errors='coerce').fillna(0.0)

    bloques = []
    for (prog, fuente, gen), grp in df_work.groupby(["Programa", "Fuente", "Generica"], sort=True):
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

    tot_gen = df_work[cols_suma].sum().to_dict()
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

    # Pestañas con tus 15 Tablas Dinámicas + tus vistas originales
    t_td_diario, t_td_mensual, t_td_vars, t1, t2 = st.tabs([
        "📊 TD Diario",
        "📅 TD Mensual",
        "📈 TD Variaciones (13 Hojas)",
        "📌 Datos Consolidados",
        "📋 Datos Último Mes"
    ])

    with t_td_diario:
        cols_diario = ["PIA", "PIM", "Certificacion", "Compromiso", "AtencionMensual", "Devengado", "Girado", "PIM-CERT", "CERT-COMP", "COMP-CM", "CM-DEV", "DEV-GIR", "PIM-DEV"]
        td_d = generar_td_subtotales(df_view, cols_diario, incluir_pct=True)
        if not td_d.empty:
            fmt_d = {c: "S/ {:,.2f}" for c in cols_diario}
            fmt_d["%Ejec."] = "{:.2f}%"
            st.dataframe(td_d.style.format(fmt_d), use_container_width=True, height=550)

    with t_td_mensual:
        if not df_mens.empty:
            metrica_m = st.selectbox("Variable mensual a visualizar:", ["Devengado", "Certificacion", "Compromiso", "AtencionMensual", "Girado"], index=0)
            df_m_filt = df_mens[
                (df_mens['Meta'].isin(metas)) &
                (df_mens['Fuente'].isin(fuentes)) &
                (df_mens['Generica'].isin(genericas))
            ].copy()
            df_m_filt[metrica_m] = pd.to_numeric(df_m_filt[metrica_m], errors='coerce').fillna(0.0)

            orden_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Setiembre", "Octubre", "Noviembre", "Diciembre"]
            meses_disp = [m for m in orden_meses if m in df_m_filt["Mes"].unique()]

            if meses_disp:
                piv = df_m_filt.pivot_table(
                    index=["Programa", "Fuente", "Generica", "EspecificaCompleta"],
                    columns="Mes",
                    values=metrica_m,
                    aggfunc="sum",
                    fill_value=0.0
                ).reset_index()
                piv["Total General"] = piv[meses_disp].sum(axis=1)
                td_m = generar_td_subtotales(piv, meses_disp + ["Total General"], incluir_pct=False)
                fmt_m = {c: "S/ {:,.2f}" for c in meses_disp + ["Total General"]}
                st.dataframe(td_m.style.format(fmt_m), use_container_width=True, height=550)

    with t_td_vars:
        mapa_vars = {
            "PIM": ("PIM", "Dif_PIM", ".PIM"),
            "CERT": ("Certificacion", "Dif_Certificacion", ".Certificacion"),
            "COMP": ("Compromiso", "Dif_Compromiso", ".Compromiso"),
            "CM": ("AtencionMensual", "Dif_AtencionMensual", ".AtencionMensual"),
            "DEV": ("Devengado", "Dif_Devengado", ".Devengado"),
            "GIR": ("Girado", "Dif_Girado", ".Girado"),
            "PIM-CERT": ("PIM-CERT", "Dif_PIM-CERT", ".PIM-CERT"),
            "CERT-COMP": ("CERT-COMP", "Dif_CERT-COMP", ".CERT-COMP"),
            "COMP-CM": ("COMP-CM", "Dif_COMP-CM", ".COMP-CM"),
            "CM-DEV": ("CM-DEV", "Dif_CM-DEV", ".CM-DEV"),
            "DEV-GIR": ("DEV-GIR", "Dif_DEV-GIR", ".DEV-GIR"),
            "PIM-DEV": ("PIM-DEV", "Dif_PIM-DEV", ".PIM-DEV"),
            "%Ejec": ("%Ejec.", "Dif_%Ejec.", ".%Ejec.")
        }

        c_var1, c_var2 = st.columns([2, 2])
        var_sel = c_var1.selectbox("Selecciona la hoja / variable histórica:", list(mapa_vars.keys()), index=4)
        modo_val = c_var2.radio("Mostrar en columnas por fecha:", ["Variación del día (Dif_)", "Saldo acumulado"], horizontal=True)

        col_act, col_dif, col_flag = mapa_vars[var_sel]
        col_metrica = col_dif if "Variación" in modo_val else col_act

        # Filtrar por Meta, Fuente, Genérica y la bandera de movimiento en TODA LA HISTORIA (sin restringir a 1 fecha)
        df_v = df_cons[
            (df_cons['Meta'].isin(metas)) &
            (df_cons['Fuente'].isin(fuentes)) &
            (df_cons['Generica'].isin(genericas)) &
            (df_cons[col_flag] == col_flag)
        ].copy()
        df_v[col_metrica] = pd.to_numeric(df_v[col_metrica], errors='coerce').fillna(0.0)

        if df_v.empty:
            st.info(f"No hay registros históricos con movimiento en {var_sel} para los filtros actuales.")
        else:
            fechas_hist = sorted(df_v["Fecha"].unique())
            piv_hist = df_v.pivot_table(
                index=["Programa", "Fuente", "Generica", "EspecificaCompleta"],
                columns="Fecha",
                values=col_metrica,
                aggfunc="sum",
                fill_value=0.0
            ).reset_index()

            if "Variación" in modo_val and var_sel != "%Ejec":
                piv_hist["Total Variación"] = piv_hist[fechas_hist].sum(axis=1)
                cols_h = fechas_hist + ["Total Variación"]
            else:
                cols_h = fechas_hist

            td_v = generar_td_subtotales(piv_hist, cols_h, incluir_pct=False)
            fmt_v = {c: ("{:+.2f}%" if "Variación" in modo_val else "{:.2f}%") for c in cols_h} if var_sel == "%Ejec" else {c: ("S/ {:+,.2f}" if "Variación" in modo_val else "S/ {:,.2f}") for c in cols_h}
            st.dataframe(td_v.style.format(fmt_v), use_container_width=True, height=550)

    with t1:
        st.dataframe(df_view, use_container_width=True)
    with t2:
        st.dataframe(df_mens, use_container_width=True)

    # Descarga Excel con las 15 hojas de Tablas Dinámicas + datos crudos
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if not df_view.empty:
            td_d.to_excel(writer, index=False, sheet_name='TD_Diario')
        if not df_mens.empty and 'td_m' in locals():
            td_m.to_excel(writer, index=False, sheet_name='TD_Mensual')
        for nombre_hoja, (c_act, c_dif, c_flg) in mapa_vars.items():
            df_h = df_cons[(df_cons['Meta'].isin(metas)) & (df_cons['Fuente'].isin(fuentes)) & (df_cons['Generica'].isin(genericas)) & (df_cons[c_flg] == c_flg)].copy()
            if not df_h.empty:
                df_h[c_dif] = pd.to_numeric(df_h[c_dif], errors='coerce').fillna(0.0)
                f_h = sorted(df_h["Fecha"].unique())
                p_h = df_h.pivot_table(index=["Programa", "Fuente", "Generica", "EspecificaCompleta"], columns="Fecha", values=c_dif, aggfunc="sum", fill_value=0.0).reset_index()
                td_h = generar_td_subtotales(p_h, f_h, incluir_pct=False)
                td_h.to_excel(writer, index=False, sheet_name=nombre_hoja[:31])
        df_cons.to_excel(writer, index=False, sheet_name='MEF_Consolidado_Unico')
        df_mens.to_excel(writer, index=False, sheet_name='tblMensual')

    st.sidebar.download_button(
        label="📥 Descargar Excel con 15 TDs (.xlsx)",
        data=buffer.getvalue(),
        file_name=f"SUNASS_MEF_{fecha_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
