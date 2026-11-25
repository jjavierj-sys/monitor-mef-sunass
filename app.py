import io
import json
import re
from datetime import datetime
import altair as alt
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Monitor DRE - SUNASS",
    page_icon="🇵🇪",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .block-container { padding-top: 3.5rem; padding-bottom: 2rem; max-width: 960px; }

    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-top: 4px solid #3B82F6;
        padding: 12px 14px;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
        font-weight: 800 !important;
    }

    table {
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    table td, table th {
        white-space: normal !important;
        word-wrap: break-word !important;
        font-size: 0.83rem !important;
        vertical-align: middle !important;
        padding: 8px 8px !important;
    }

    div[data-baseweb="select"] input {
        caret-color: transparent !important;
        pointer-events: none !important;
    }

    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 0.6rem !important;
        }
        div[data-testid="stHorizontalBlock"] > div {
            width: 100% !important;
            min-width: 0 !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.subheader("🇵🇪 Monitor Presupuestal y Documental DRE - SUNASS")

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

# =====================================================================
# MOTOR DE CLASIFICACIÓN SIGED (81 CATEGORÍAS DE TU POWER QUERY)
# =====================================================================
def clasificar_subtipo_tecnico(txt):
    reglas = [
        (["ptap", "tratamiento del agua", "confiabilidad operativa", "infraestructura de tratamiento"], "29. FISCALIZACIÓN PTAP"),
        (["meta de gestión", "metas de gestión", "fiscalización de metas"], "30. METAS DE GESTIÓN EPS"),
        (["base comercial", "facturación"], "31. BASE COMERCIAL EPS"),
        (["continuidad", "presión"], "32. CONTINUIDAD Y PRESIÓN"),
        (["revisión medio término", "medio término"], "33. REVISIÓN MEDIO TÉRMINO EPS"),
        (["documento técnico", "estudio técnico", "análisis de los factores críticos"], "34. ESTUDIOS TÉCNICOS REGULATORIOS"),
        (["asistencia técnica", "asistencias técnicas"], "35. ASISTENCIA TÉCNICA EPS"),
        (["actualización del prestador", "jass"], "36. ACTUALIZACIÓN PRESTADORES / JASS"),
        (["área de prestación", "socialización del área"], "37. SOCIALIZACIÓN ÁREA PRESTACIÓN"),
        (["costeo abc", "indicadores abc"], "38. COSTEO ABC"),
        (["integración de prestadores", "integración"], "39. INTEGRACIÓN PRESTADORES"),
        (["micromedición", "medidor", "medidores"], "41. MICROMEDICIÓN"),
        (["alcantarillado", "desagüe", "aguas residuales"], "42. ALCANTARILLADO SANITARIO"),
        (["cloración", "cloro", "desinfección"], "43. CLORACIÓN Y DESINFECCIÓN"),
        (["captación", "fuente de agua"], "44. CAPTACIÓN DE AGUA"),
        (["reservorio", "tanque"], "45. RESERVORIOS"),
        (["pozo", "pozos"], "46. POZOS"),
        (["bombeo", "estación de bombeo"], "47. SISTEMAS DE BOMBEO"),
        (["catastro técnico", "catastro"], "48. CATASTRO TÉCNICO"),
        (["redes de distribución", "red de agua"], "49. REDES DE DISTRIBUCIÓN"),
        (["pérdidas de agua", "agua no facturada"], "50. PÉRDIDAS DE AGUA"),
        (["mantenimiento preventivo", "mantenimiento correctivo"], "51. MANTENIMIENTO OPERATIVO"),
        (["laboratorio", "calidad de agua"], "52. CONTROL DE CALIDAD DE AGUA"),
        (["plan de emergencia", "contingencia"], "53. PLANES DE CONTINGENCIA"),
        (["reclamos operacionales", "incidencia operativa"], "54. RECLAMOS OPERACIONALES"),
        (["rehabilitación", "mejoramiento"], "55. REHABILITACIÓN DE INFRAESTRUCTURA"),
        (["ampliación", "expansión"], "56. AMPLIACIÓN DE COBERTURA"),
        (["diagnóstico hidráulico", "modelamiento hidráulico"], "57. MODELAMIENTO HIDRÁULICO"),
        (["sectorización", "macrosector"], "58. SECTORIZACIÓN"),
        (["macro medición", "caudalímetro"], "59. MACROMEDICIÓN"),
        (["presa", "embalse"], "60. FUENTES SUPERFICIALES"),
        (["tarifa técnica", "costos operativos"], "61. COSTOS OPERATIVOS EPS"),
        (["diagnóstico situacional", "evaluación técnica"], "62. DIAGNÓSTICOS TÉCNICOS"),
        (["fiscalización comercial", "usuarios no domésticos"], "63. FISCALIZACIÓN COMERCIAL"),
        (["reposición", "renovación de redes"], "64. REPOSICIÓN DE REDES"),
        (["eficiencia energética", "consumo eléctrico"], "65. EFICIENCIA ENERGÉTICA"),
        (["telemetría", "scada"], "66. TELEMETRÍA Y SCADA"),
        (["interrupción del servicio", "corte del servicio"], "67. INTERRUPCIONES DEL SERVICIO"),
        (["densidad poblacional", "proyección poblacional"], "68. PROYECCIÓN DEMANDA"),
        (["riesgo operacional", "gestión de riesgos"], "69. GESTIÓN DE RIESGOS"),
        (["supervisión técnica", "inspección técnica"], "70. SUPERVISIÓN TÉCNICA"),
        (["rehuso", "reúso"], "71. REÚSO DE AGUAS"),
        (["lodos", "biosólidos"], "72. MANEJO DE LODOS"),
        (["planta de tratamiento residual", "ptar"], "73. PTAR"),
        (["saneamiento rural", "centro poblado"], "74. SANEAMIENTO RURAL"),
        (["indicadores de gestión", "benchmarking"], "75. INDICADORES DE GESTIÓN"),
        (["expediente técnico", "memoria descriptiva"], "76. EXPEDIENTES TÉCNICOS"),
        (["obra paralizada", "reinicio de obra"], "77. OBRAS PARALIZADAS"),
        (["transferencia de infraestructura", "recepción de obra"], "78. TRANSFERENCIA DE INFRAESTRUCTURA"),
        (["cumplimiento normativo", "adecuación normativa"], "79. CUMPLIMIENTO NORMATIVO"),
        (["evaluación residual", "análisis residual"], "80. EVALUACIÓN TÉCNICA ESPECIAL"),
    ]
    for kws, etiqueta in reglas:
        if any(k in txt for k in kws):
            return etiqueta
    return ""

def clasificar_tipo_gestion(row):
    txt = str(row.get("Asunto", "")).lower()
    areaH = str(row.get("Área remitente", "")).lower()
    areaE = str(row.get("Ubicación Área", "")).lower()
    comentF = str(row.get("Observación", "")).lower()
    proc = str(row.get("Proceso", "")).lower()
    adm = str(row.get("Administrado", "")).lower()
    subtipo = clasificar_subtipo_tecnico(txt)

    esPasaje = any(k in txt for k in ["pasaje", "pasajes", "boleto", "boletos"])
    esViatico = any(k in txt for k in ["viatico", "viático", "viatic", "viátic", "viaje"])
    esRendicion = any(k in txt for k in ["rendicion", "rendición", "informe de viáticos"])
    esInforme = "informe" in txt
    esDeCuentas = "de cuentas" in txt
    esUT = "ut" in areaE
    esPara = "para" in comentF
    esUC = ("uc" in areaH) or ("uc" in areaE)
    esSIAF = "siaf" in txt
    esEncargo = "encargo" in txt

    esEntregable = (
        ("entregable" in txt or "conformidad" in txt)
        and not ("inventario" in txt or "acciones orientadas" in txt)
    )

    areas_cont = ["upp", "gg", "oppm", "sdem", "srt", "dre", "ua"]
    kws_cont = [
        "contratacion", "contratación", "servicio de elaboración", "servicio de seguimiento",
        "servicio para", "servicio especializado", "locacion", "locación", "tdr", "requerimiento"
    ]
    excl_cont = [
        "airhsp", "de listado", "personal", "firma", "plan maestro", "requerimiento de informacion",
        "requerimiento de información", "clausula para", "cláusula para", "lineamientos para",
        "lineamiento para", "requerimiento base", "estructura de requerimiento",
        "modificación presupuest", "plaza cas", "entregable"
    ]
    esContratacion = (
        any(a in areaE for a in areas_cont)
        and any(k in txt for k in kws_cont)
        and not any(e in txt for e in excl_cont)
    )

    esPeruano = "peruano" in txt
    esCMN = (
        any(k in txt for k in ["cmn", "fase", "inclusión", "exclusión", "cuadro multianual", "de necesidades"])
        and not any(e in txt for e in ["airhsp", "terminos de referencia", "términos de referencia", "cambio de denominación"])
    )
    esPlaneamiento = (
        any(k in txt for k in ["plan", "programacion", "programación", "poi", "pei", "memoria"])
        and not any(e in txt for e in [
            "reprogramación", "reporte de avance", "reprogramacion", "vacacion", "servicio",
            "base", "maestro", "inversion", "planta", "asistencia tecnica", "asistencia técnica", "asistencias técnicas"
        ])
    )
    esPresupuesto = (
        any(k in txt for k in ["presupuest", "certificacion", "certificación", "ejecucion", "rebaja", "certificado", "ccp"])
        and not any(e in txt for e in ["seguimiento", "mef", "macrofiscal", "inventario", "tarifa", "cuota", "inversiones"])
    )

    if esPasaje and not esPresupuesto:
        return "01. PASAJES", subtipo
    if esUT and esPara and esViatico and not esRendicion and not esInforme and not esPresupuesto:
        return "02. VIÁTICOS", subtipo
    if esUT and not esPara and esViatico and not esRendicion and not esInforme and not esPresupuesto:
        return "02. VIÁTICOS PAGADOS", subtipo
    if esPara and esRendicion and not esDeCuentas and (esSIAF or esUC or esEncargo):
        return "03. RENDICIONES", subtipo
    if esRendicion and not esDeCuentas and (esSIAF or esUC or esPara or esEncargo):
        return "03. RENDICIONES PAGADAS", subtipo
    if esViatico and not esRendicion and not esInforme and not esPresupuesto:
        return "02. VIÁTICOS", subtipo
    if esRendicion and not esDeCuentas:
        return "03. RENDICIONES", subtipo
    if esEntregable:
        return "04. ENTREGABLE", subtipo
    if esContratacion and not esPresupuesto:
        return "05. CONTRATACIONES", subtipo
    if esPeruano and not esPresupuesto:
        return "05. EL PERUANO", subtipo
    if esCMN:
        return "06. CMN", subtipo
    if esPlaneamiento:
        return "07. PLANEAMIENTO", subtipo
    if esPresupuesto:
        return "08. PRESUPUESTO", subtipo
    if any(k in txt for k in ["gdr", "gestion del rendimiento", "gestión del rendimiento", "reporte de avance", "informe de avance", "rendimiento"]):
        return "09. GDR", subtipo
    if any(k in txt for k in ["teletrabajo", "trabajo remoto"]):
        return "10. TELETRABAJO", subtipo
    if "vacacion" in txt:
        return "11. VACACIONES", subtipo
    if "orh -" in areaH or any(k in txt for k in ["practica", "práctica", "airhsp", "reemplazo", "suplencia"]):
        return "12. RRHH", subtipo
    if "oti" in areaH or "oti" in areaE or any(k in txt for k in ["plataforma", "sistema", "vpn", "siged", "dashboard", "bases de datos", "clustering"]):
        return "13. TECNOLOGÍA", subtipo
    if "sedapal" in txt or adm == "serv agua potab y alcant de lima-sedapal(ruc:20100152356)":
        return "14. SEDAPAL", subtipo
    if "rebalanceo" in txt:
        return "15. REBALANCEO", subtipo
    if any(k in txt for k in ["plan maestro", "optimizado", "pmo"]):
        return "16. PMO", subtipo
    if any(k in txt for k in ["actualizacion tarifaria", "actualización tarifaria", "estudio tarifario", "estudios tarifarios"]):
        return "17. ESTUDIO TARIFARIO", subtipo
    if any(k in txt for k in ["tarifa", "tarifas", "estructura tarifaria", "nivel tarifario"]):
        return "18. TARIFAS", subtipo
    if any(k in txt for k in ["ugm", "pequeña ciudad", "pequeñas ciudades"]):
        return "19. PEQUEÑAS CIUDADES", subtipo
    if any(k in txt for k in ["cuota familiar", "cuotas familiares"]):
        return "20. CUOTA FAMILIAR", subtipo
    if any(k in txt for k in ["caracterizacion", "caracterización"]):
        return "21. CARACTERIZACIÓN", subtipo
    if any(k in txt for k in ["área de prestación", "adp"]):
        return "22. ÁREA DE PRESTACIÓN", subtipo
    if any(k in txt for k in ["inversion", "inversión", "inversiones", "proyecto", "pip", "ioarr", "brechas"]):
        return "23. INVERSIONES", subtipo
    if any(k in txt for k in ["contabilidad regulatoria", "oficio", "estado financiero", "balance"]):
        return "24. CONTABILIDAD REGULATORIA", subtipo
    if "pedido" in txt:
        return "25. PEDIDOS EXTERNOS", subtipo
    if " pas " in txt:
        return "26. PAS", subtipo
    if any(k in txt for k in ["apelacion", "apelación"]):
        return "27. APELACIÓN", subtipo
    if "solicitud de acceso" in proc:
        return "28. TRANSPARENCIA", subtipo
    if subtipo:
        return subtipo, subtipo
    return "81. TÉCNICO RESIDUAL", subtipo

def leer_archivo_siged_universal(contenido_bytes, skip_extra=0):
    """Lee archivos .xls binarios, .xlsx o tablas HTML disfrazadas de .xls que entrega SIGED."""
    df_raw = None
    for engine in [None, "xlrd", "openpyxl"]:
        try:
            df_raw = pd.read_excel(io.BytesIO(contenido_bytes), header=None, engine=engine)
            break
        except Exception:
            continue
    if df_raw is None:
        try:
            tablas = pd.read_html(io.BytesIO(contenido_bytes))
            if tablas:
                df_raw = max(tablas, key=len)
        except Exception:
            return pd.DataFrame()

    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    header_idx = 0
    for idx, row in df_raw.iterrows():
        vals = [str(v).strip().lower() for v in row.values if pd.notna(v)]
        if "número de registro" in vals or "número expediente" in vals or "asunto" in vals:
            header_idx = idx
            break

    df = df_raw.iloc[header_idx + 1:].copy()
    df.columns = [str(c).strip() for c in df_raw.iloc[header_idx].values]
    df = df.loc[:, ~df.columns.str.contains("^nan$|^None$", case=False)]
    return df.reset_index(drop=True)

from concurrent.futures import ThreadPoolExecutor

def extraer_expedientes_en_texto(texto):
    """Detecta códigos tipo 2026-I01-042565 o 2026-E01-104847 dentro de Observaciones o Asuntos."""
    if not texto:
        return []
    return re.findall(r"\b20\d{2}-[A-Za-z0-9]{2,4}-\d{5,7}\b", str(texto).upper())

def descargar_url_siged(tarea):
    etiqueta, url, meta = tarea
    try:
        r = requests.get(url, timeout=35)
        if r.status_code == 200 and len(r.content) > 200:
            df_part = leer_archivo_siged_universal(r.content)
            if not df_part.empty:
                for k, v in meta.items():
                    df_part[k] = v
                return etiqueta, df_part, None
            return etiqueta, pd.DataFrame(), f"{etiqueta}: sin registros"
        return etiqueta, pd.DataFrame(), f"{etiqueta}: HTTP {r.status_code}"
    except Exception as e:
        return etiqueta, pd.DataFrame(), f"{etiqueta}: {str(e)[:40]}"

def descargar_siged_completo_desde_api(anio, exps_gasto=None):
    p = "https://"
    base_exp = p + "api.sunass.gob.pe/api-sgd/reporte/busqueda/expediente"

    tareas = []
    areas = [("DRE", "8"), ("SDEM", "353"), ("SRT", "352")]
    tipos = [("Recibido", "ubicacionHistoricaRecibidoArea"), ("Enviado", "ubicacionHistoricaEnviadoArea")]
    for area_nom, area_cod in areas:
        for tipo_nom, param_area in tipos:
            url = f"{base_exp}?busquedaFechaDesde=01/01/{anio}&busquedaFechaHasta=31/12/{anio}&{param_area}={area_cod}"
            tareas.append((f"SIGED_{area_nom}_{tipo_nom}", url, {"Grupo": "SIGED", "Tipo": tipo_nom, "Área": area_nom}))

    # Descargar en paralelo expedientes enviados por Unidad de Abastecimiento (UA = 45)
    url_ua = f"{base_exp}?busquedaFechaDesde=01/01/{anio}&busquedaFechaHasta=31/12/{anio}&ubicacionHistoricaEnviadoArea=45"
    tareas.append(("UA_Enviado", url_ua, {"Grupo": "UA", "Tipo": "Enviado", "Área": "UA"}))

    lotes_siged, lotes_ua, errores = [], [], []
    with ThreadPoolExecutor(max_workers=7) as executor:
        for etiqueta, df_res, err in executor.map(descargar_url_siged, tareas):
            if err:
                errores.append(err)
            elif not df_res.empty:
                grp = df_res["Grupo"].iloc[0]
                df_res = df_res.drop(columns=["Grupo"])
                if grp == "SIGED":
                    lotes_siged.append(df_res)
                elif grp == "UA":
                    lotes_ua.append(df_res)

    if not lotes_siged:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), errores

    df = pd.concat(lotes_siged, ignore_index=True)
    df = df[df["Número de registro"].notna()].copy()
    df["Número de registro"] = df["Número de registro"].astype(str).str.strip().str.upper()
    df = df[df["Número de registro"] != "NÚMERO DE REGISTRO"]
    df = df.drop_duplicates(subset=["Número de registro"], keep="first").reset_index(drop=True)
    clasif = df.apply(clasificar_tipo_gestion, axis=1)
    df["COLUMNA AUXILIAR"] = "1"
    df["TIPO_GESTION"] = [c[0] for c in clasif]
    df["SUBTIPO_TÉCNICO"] = [c[1] for c in clasif]

    # Preparar base ligera de UA (filtrada solo a expedientes citados en Observaciones o relacionados a pasajes)
    df_ua = pd.DataFrame()
    if lotes_ua:
        df_ua_raw = pd.concat(lotes_ua, ignore_index=True)
        if "Número de registro" in df_ua_raw.columns:
            df_ua_raw = df_ua_raw[df_ua_raw["Número de registro"].notna()].copy()
            df_ua_raw["Número de registro"] = df_ua_raw["Número de registro"].astype(str).str.strip().str.upper()
            df_ua_raw = df_ua_raw.drop_duplicates(subset=["Número de registro"], keep="first")

            exps_citados = set()
            if "Observación" in df.columns:
                for obs in df["Observación"].dropna():
                    exps_citados.update(extraer_expedientes_en_texto(obs))
            if exps_gasto:
                exps_citados.update(exps_gasto)

            mask_pasaje = df_ua_raw["Asunto"].astype(str).str.lower().str.contains("pasaje|boleto|aereo|aéreo|solicitud de pago", na=False)
            df_ua = df_ua_raw[df_ua_raw["Número de registro"].isin(exps_citados) | mask_pasaje].reset_index(drop=True)

    return df, df_ua, pd.DataFrame(), errores

def guardar_dataframe_en_sheet(wb, nombre_hoja, df):
    if df is None or df.empty:
        return
    try:
        ws = wb.worksheet(nombre_hoja)
    except gspread.WorksheetNotFound:
        ws = wb.add_worksheet(title=nombre_hoja, rows=max(len(df) + 50, 500), cols=max(len(df.columns) + 2, 22))
    df_clean = df.fillna("").astype(str)
    ws.clear()
    ws.update([df_clean.columns.tolist()] + df_clean.values.tolist(), value_input_option="RAW")


# =====================================================================
# NAVEGACIÓN PRINCIPAL (PRESUPUESTO MEF vs SIGED & GASTO)
# =====================================================================
modulo_activo = st.radio(
    "Módulo",
    ["💰 Presupuesto MEF", "📂 SIGED & Gasto"],
    horizontal=True,
    label_visibility="collapsed"
)

# =====================================================================
# MÓDULO 1: MONITOR PRESUPUESTAL MEF (INTACTO)
# =====================================================================
if modulo_activo == "💰 Presupuesto MEF":
    def mapear_unidad(meta):
        m = str(meta).strip()
        if m == "1":
            return "SRT"
        elif m == "61":
            return "SDEM"
        return f"Meta {m}"

    @st.cache_data(ttl=60)
    def leer_pestana_mef(nombre):
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

    col_ref, col_fec = st.columns([1, 2])
    with col_ref:
        if st.button("🔄 Actualizar", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()

    df_cons = leer_pestana_mef("MEF_Consolidado_Unico")
    df_mens = leer_pestana_mef("tblMensual")

    if df_cons.empty:
        st.info("Ejecuta 'Actualizar Todo MEF (Hoy)' en Google Sheets para cargar los datos.")
        st.stop()

    fechas = sorted(df_cons['Fecha'].unique(), reverse=True)

    if "fecha_sel" not in st.session_state or st.session_state.fecha_sel not in fechas:
        st.session_state.fecha_sel = fechas
    if "unidad_opt" not in st.session_state:
        st.session_state.unidad_opt = "DRE (Global)"
    if "fuente_opt" not in st.session_state:
        st.session_state.fuente_opt = "Todas"
    if "gen_opt" not in st.session_state:
        st.session_state.gen_opt = "Todas"

    def limpiar_filtros():
        st.session_state.fecha_sel = fechas
        st.session_state.unidad_opt = "DRE (Global)"
        st.session_state.fuente_opt = "Todas"
        st.session_state.gen_opt = "Todas"

    with col_fec:
        fecha_sel = st.selectbox("Fecha de corte", fechas, key="fecha_sel", label_visibility="collapsed")

    f1, f2 = st.columns(2)
    unidad_opt = f1.selectbox("Unidad Orgánica", ["DRE (Global)", "SRT", "SDEM"], key="unidad_opt")
    fuente_opt = f2.selectbox("Fuente", ["Todas", "RO", "RDR"], key="fuente_opt")

    f3, f4 = st.columns([2, 1.2])
    gen_opt = f3.selectbox("Genérica", ["Todas", "2.1", "2.3", "2.3 (Sin practicantes)"], key="gen_opt")
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

    df_fecha = filtrar_generica(df_cons[df_cons['Fecha'] == fecha_sel].copy())
    if fuente_opt != "Todas":
        df_fecha = df_fecha[df_fecha['Fuente'] == fuente_opt]

    df_view = filtrar_unidad(df_fecha)

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

    pct_bar = min(max(pct_tot, 0), 100)
    color_estado = "#10B981" if pct_tot >= 85 else ("#3B82F6" if pct_tot >= 65 else "#F59E0B")
    emoji_estado = "🌟" if pct_tot >= 85 else ("🚀" if pct_tot >= 65 else "⚡")
    texto_estado = (
        f"{emoji_estado} ¡Excelente ritmo! <b>{unidad_opt}</b> ya ejecutó el <b>{pct_tot:.1f}%</b> de su presupuesto."
        if pct_tot >= 85 else
        f"{emoji_estado} <b>{unidad_opt}</b> lleva el <b>{pct_tot:.1f}%</b> ejecutado de su meta."
    )

    st.markdown(f"""
    <div style="background-color: var(--secondary-background-color); border-radius: 16px; padding: 14px 16px; margin: 8px 0 14px 0; border: 1px solid rgba(128,128,128,0.15); box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
        <div style="font-size: 0.92rem; margin-bottom: 8px;">{texto_estado}</div>
        <div style="width: 100%; background-color: rgba(128,128,128,0.2); border-radius: 999px; height: 14px; overflow: hidden;">
            <div style="width: {pct_bar}%; background: linear-gradient(90deg, #3B82F6, {color_estado}); height: 100%; border-radius: 999px;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    k1, k2 = st.columns(2)
    k1.metric(f"🎯 Meta (PIM {unidad_opt})", f"{pim_tot:,.2f}")
    k2.metric("🚀 Ya Ejecutado", f"{dev_tot:,.2f}", f"{dif_dev:+,.2f} hoy" if abs(dif_dev) > 0 else "Sin cambio hoy")

    k3, k4 = st.columns(2)
    k3.metric("🏆 Avance Total", f"{pct_tot:.2f}%")
    k4.metric("💰 Por Ejecutar", f"{saldo_tot:,.2f}")

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

            st.caption("Comparativo visual — Barra suave: Meta (PIM) | Barra azul: Ya ejecutado")
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
                color="#93C5FD",
                opacity=0.45,
                size=54,
                cornerRadiusTopLeft=8,
                cornerRadiusTopRight=8
            ).encode(
                x=alt.X("Unidad:N", sort=orden_u, title=None, axis=alt.Axis(labelAngle=0, labelFontWeight="bold")),
                y=alt.Y("PIM:Q", title="Monto (S/)"),
                tooltip=["Unidad", alt.Tooltip("PIM:Q", format=",.2f"), alt.Tooltip("Devengado:Q", format=",.2f"), "Porcentaje"]
            )

            barra_dev = alt.Chart(chart_df).mark_bar(
                color="#2563EB",
                size=26,
                cornerRadiusTopLeft=8,
                cornerRadiusTopRight=8
            ).encode(
                x=alt.X("Unidad:N", sort=orden_u),
                y=alt.Y("Devengado:Q"),
                tooltip=["Unidad", alt.Tooltip("PIM:Q", format=",.2f"), alt.Tooltip("Devengado:Q", format=",.2f"), "Porcentaje"]
            )

            etiquetas = alt.Chart(chart_df).mark_text(
                dy=-10,
                color="#2563EB",
                fontWeight="bold",
                fontSize=13
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
                return "color: #2563EB; font-weight: bold;" if v > 0 else "color: #EF4444; font-weight: bold;"

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
                color="#3B82F6",
                cornerRadiusTopLeft=8,
                cornerRadiusTopRight=8
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

# =====================================================================
# MÓDULO 2: SIGED & PROGRAMACIÓN DE GASTO (CRUCE INTELIGENTE)
# =====================================================================
else:
    @st.cache_data(ttl=60)
    def leer_hoja_segura(nombre):
        wb = conectar_gsheets()
        try:
            regs = wb.worksheet(nombre).get_all_records(value_render_option='UNFORMATTED_VALUE')
            return pd.DataFrame(regs) if regs else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    df_gasto_pre = leer_hoja_segura("GASTO")
    cols_exp_gasto = [
        "Exp.Solicitud", "Exp.Rebaja", "Exp.Rebaja2", "Exp.Rebaja3",
        "Exp.Devengado", "Exp.Dev.De.Ref.1", "Exp.Dev.De.Ref.2",
        "Exp.Trámite.Presupuestal", "Exp.Rendición", "Exp.Rend.De.Ref.1", "Exp.Informe"
    ]
    exps_gasto_set = set()
    if not df_gasto_pre.empty:
        for col in cols_exp_gasto:
            if col in df_gasto_pre.columns:
                vals = df_gasto_pre[col].dropna().astype(str).str.strip().str.upper()
                exps_gasto_set.update(v for v in vals if v.startswith("202"))

    c_api, c_up = st.columns([1.3, 1.7])
    with c_api:
        if st.button("🔄 Sincronizar SIGED (API SUNASS)", type="primary", use_container_width=True):
            with st.spinner("Sincronizando expedientes SIGED (DRE, SDEM, SRT y rastreo UA)..."):
                anio_actual = datetime.now().year
                df_nuevo_siged, df_nuevo_ua, _, errs = descargar_siged_completo_desde_api(anio_actual, exps_gasto_set)
                if not df_nuevo_siged.empty:
                    wb = conectar_gsheets()
                    guardar_dataframe_en_sheet(wb, "SIGED_Consolidado", df_nuevo_siged)
                    guardar_dataframe_en_sheet(wb, "UA_Vuelos", df_nuevo_ua)
                    st.cache_data.clear()
                    st.success(f"¡Listo! {len(df_nuevo_siged):,} expedientes SIGED y {len(df_nuevo_ua):,} rastreos UA sincronizados.")
                    if errs:
                        st.caption("Avisos: " + " | ".join(errs))
                    st.rerun()
                else:
                    st.error("La API de SUNASS no respondió ahora. Usa el cargador manual a la derecha.")

    with c_up:
        archivos_xls = st.file_uploader(
            "Respaldo manual (.xls / .xlsx de SIGED)",
            type=["xls", "xlsx"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
        if archivos_xls:
            lotes_manual = []
            for f in archivos_xls:
                df_p = leer_archivo_siged_universal(f.read())
                if not df_p.empty and "Número de registro" in df_p.columns:
                    df_p["Tipo"] = "Manual"
                    df_p["Área"] = "DRE"
                    lotes_manual.append(df_p)
            if lotes_manual:
                df_m_siged = pd.concat(lotes_manual, ignore_index=True).drop_duplicates(subset=["Número de registro"])
                clasif = df_m_siged.apply(clasificar_tipo_gestion, axis=1)
                df_m_siged["COLUMNA AUXILIAR"] = "1"
                df_m_siged["TIPO_GESTION"] = [c for c in clasif]
                df_m_siged["SUBTIPO_TÉCNICO"] = [c for c in clasif]
                wb = conectar_gsheets()
                guardar_dataframe_en_sheet(wb, "SIGED_Consolidado", df_m_siged)
                st.cache_data.clear()
                st.success(f"¡Cargados {len(df_m_siged)} expedientes desde archivo!")
                st.rerun()

    df_siged = leer_hoja_segura("SIGED_Consolidado")
    df_ua = leer_hoja_segura("UA_Vuelos")
    df_sunass = pd.DataFrame()
    df_gasto = df_gasto_pre
    df_anulados = leer_hoja_segura("ANULADOS")

    if df_siged.empty:
        st.info("Presiona **🔄 Sincronizar SIGED (API SUNASS)** o sube los `.xls` de SIGED para comenzar.")
        st.stop()

    exps_usados = set(exps_gasto_set)
    if not df_anulados.empty:
        col_anul = df_anulados.columns[0]
        vals_a = df_anulados[col_anul].dropna().astype(str).str.strip().str.upper()
        exps_usados.update(v for v in vals_a if v.startswith("202"))

    df_siged["Número de registro"] = df_siged["Número de registro"].astype(str).str.strip().str.upper()
    df_pendientes = df_siged[~df_siged["Número de registro"].isin(exps_usados)].copy()

    # Detección de expedientes ocultos de devengue en Observaciones (ej. Vuelos / Pasajes)
    filas_ocultas = []
    if "Observación" in df_siged.columns:
        mapa_ua = {}
        if not df_ua.empty and "Número de registro" in df_ua.columns:
            for _, rua in df_ua.iterrows():
                mapa_ua[str(rua["Número de registro"]).strip().upper()] = rua.to_dict()

        exps_ya_en_pend = set(df_pendientes["Número de registro"])
        for _, r_orig in df_siged.iterrows():
            exp_orig = str(r_orig.get("Número de registro", "")).strip().upper()
            obs = str(r_orig.get("Observación", ""))
            if exp_orig in exps_gasto_set and obs:
                for exp_citado in extraer_expedientes_en_texto(obs):
                    if exp_citado == exp_orig:
                        continue

                    # 1. Búsqueda exacta y variantes flexibles si tiene 5 dígitos (ej. 2026-I01-01314 -> 001314 o 013140)
                    exp_resuelto = exp_citado
                    info_ua = mapa_ua.get(exp_citado, {})
                    if len(info_ua) == 0 and len(mapa_ua) > 0:
                        partes = exp_citado.split("-")
                        if len(partes) == 3 and len(partes[2]) == 5:
                            p_anio, p_tipo, num5 = partes[0], partes[1], partes[2]
                            candidatos = [f"{p_anio}-{p_tipo}-0{num5}"]
                            for pos in range(1, 6):
                                for d in range(10):
                                    cand_num = num5[:pos] + str(d) + num5[pos:]
                                    candidatos.append(f"{p_anio}-{p_tipo}-{cand_num}")

                            fec_orig = pd.to_datetime(r_orig.get("Fecha de creación", None), dayfirst=True, errors="coerce")
                            for cand in dict.fromkeys(candidatos):
                                if cand in mapa_ua and cand not in exps_usados:
                                    asunto_cand = str(mapa_ua[cand].get("Asunto", "")).lower()
                                    if any(k in asunto_cand for k in ["solicitud de pago", "pasaje", "boleto", "aereo", "aéreo"]):
                                        fec_cand = pd.to_datetime(mapa_ua[cand].get("Fecha de creación", None), dayfirst=True, errors="coerce")
                                        if pd.notna(fec_orig) and pd.notna(fec_cand) and fec_cand.date() < fec_orig.date():
                                            continue
                                        exp_resuelto = cand
                                        info_ua = mapa_ua[cand]
                                        break

                    if exp_resuelto not in exps_usados and exp_resuelto not in exps_ya_en_pend:
                        exps_ya_en_pend.add(exp_resuelto)
                        asunto_ua = info_ua.get("Asunto", f"Expediente generado desde observación de {exp_orig}")
                        area_ua = info_ua.get("Ubicación Área", "UA / Tesorería")
                        pers_ua = info_ua.get("Ubicación Persona", "")
                        pers_gasto = ""
                        if not df_gasto.empty and "Exp.Solicitud" in df_gasto.columns:
                            m_g = df_gasto[df_gasto["Exp.Solicitud"].astype(str).str.strip().str.upper() == exp_orig]
                            if not m_g.empty:
                                pers_gasto = f" ({m_g.iloc[0].get('Persona', '')})"

                        nota_flex = f" [Corregido desde {exp_citado}]" if exp_resuelto != exp_citado else ""
                        filas_ocultas.append({
                            "Número de registro": exp_resuelto,
                            "TIPO_GESTION": "01. PASAJES (DEVENGUE UA)",
                            "Asunto": asunto_ua,
                            "Ubicación Área": area_ua,
                            "Ubicación Persona": pers_ua,
                            "Sugerencia_GASTO": f"✈️ Asociado a solicitud {exp_orig}{pers_gasto}{nota_flex} -> Registrar en Exp.Devengado (Obs: {obs[:80]})"
                        })

    def sugerir_imputacion(row):
        asunto = str(row.get("Asunto", ""))
        tipo = str(row.get("TIPO_GESTION", ""))
        if df_gasto.empty:
            return "Sin base GASTO"

        m_siaf = re.search(r"siaf[^\d]{0,8}0*(\d{2,6})", asunto, re.IGNORECASE)
        if m_siaf:
            num_siaf = m_siaf.group(1)
            if "SIAF" in df_gasto.columns:
                match = df_gasto[df_gasto["SIAF"].astype(str).str.strip().str.lstrip("0") == num_siaf]
                if not match.empty:
                    r0 = match.iloc[0]
                    return f"🔗 SIAF {num_siaf} -> {r0.get('Persona', '')} | {r0.get('Genérica', '')} (Rend: {r0.get('Exp.Rendición', '')})"
            return f"🔍 SIAF {num_siaf} detectado (no hallado en GASTO)"

        if "ENTREGABLE" in tipo and "Persona" in df_gasto.columns and "GASTO" in df_gasto.columns:
            por_dev = df_gasto[df_gasto["GASTO"].astype(str).str.upper() == "POR DEVENGAR"]
            asunto_low = asunto.lower()
            for _, rg in por_dev.iterrows():
                pers = str(rg.get("Persona", "")).strip()
                if len(pers) > 5:
                    apellidos = [p.lower() for p in pers.split() if len(p) > 3]
                    if sum(1 for a in apellidos if a in asunto_low) >= 2:
                        return f"📄 Cuota pendiente -> {pers} ({rg.get('OS', '')} | Mes {rg.get('Mes.Devengue', '')})"

        return "🆕 Nuevo registro para GASTO"

    rubros_interes = [
        "01. PASAJES", "01. PASAJES (DEVENGUE UA)", "02. VIÁTICOS", "02. VIÁTICOS PAGADOS",
        "03. RENDICIONES", "03. RENDICIONES PAGADAS",
        "04. ENTREGABLE", "05. CONTRATACIONES", "05. EL PERUANO"
    ]
    df_pend_interes = df_pendientes[df_pendientes["TIPO_GESTION"].isin(rubros_interes)].copy()
    if not df_pend_interes.empty:
        df_pend_interes["Sugerencia_GASTO"] = df_pend_interes.apply(sugerir_imputacion, axis=1)

    if filas_ocultas:
        df_ocultos = pd.DataFrame(filas_ocultas)
        df_pend_interes = pd.concat([df_ocultos, df_pend_interes], ignore_index=True)

    
    s1, s2 = st.columns(2)
    s1.metric("📥 Expedientes SIGED", f"{len(df_siged):,}")
    s2.metric("🆕 Pendientes de Interés", f"{len(df_pend_interes):,}", "Listos para imputar en GASTO")

    t_bandeja, t_gestion, t_vuelos, t_viaticos = st.tabs([
        "🆕 Bandeja Pendientes (SIGED2)",
        "📊 Por Tipo de Gestión",
        "✈️ Vuelos (USD/PEN)",
        "🧳 Viáticos y Rendiciones"
    ])

    with t_bandeja:
        f_rubro = st.selectbox("Filtrar tipo de trámite pendiente", ["Todos de interés"] + rubros_interes)
        df_b = df_pend_interes.sort_values(by=["TIPO_GESTION", "Número de registro"]).copy()
        if f_rubro != "Todos de interés":
            df_b = df_b[df_b["TIPO_GESTION"] == f_rubro]

        if df_b.empty:
            st.success("🎉 ¡Cero expedientes pendientes por imputar en este rubro!")
        else:
            cols_ver = ["Número de registro", "TIPO_GESTION", "Asunto", "Ubicación Área", "Ubicación Persona", "Sugerencia_GASTO"]
            cols_ver = [c for c in cols_ver if c in df_b.columns]
            st.table(df_b[cols_ver].set_index("Número de registro"))

    with t_gestion:
        res_tg = df_siged.groupby("TIPO_GESTION", as_index=False).agg(
            Total_SIGED=("Número de registro", "count")
        ).sort_values("Total_SIGED", ascending=False)
        pend_tg = df_pendientes.groupby("TIPO_GESTION", as_index=False).agg(
            Pendientes=("Número de registro", "count")
        )
        res_tg = res_tg.merge(pend_tg, on="TIPO_GESTION", how="left").fillna({"Pendientes": 0})
        res_tg["Pendientes"] = res_tg["Pendientes"].astype(int)
        st.dataframe(res_tg, use_container_width=True, hide_index=True)

    with t_vuelos:
        if df_gasto.empty or "Genérica" not in df_gasto.columns:
            st.info("Sin datos de GASTO cargados.")
        else:
            df_v = df_gasto[df_gasto["Genérica"].astype(str).str.lower() == "vuelos"].copy()
            for col_n in ["Monto.USD", "Monto.Dev.", "Monto.Por.Devengar"]:
                if col_n in df_v.columns:
                    df_v[col_n] = pd.to_numeric(df_v[col_n], errors="coerce").fillna(0.0)
            res_v = df_v.groupby(["Programa", "Fuente", "GASTO"], as_index=False)[
                ["Monto.USD", "Monto.Dev.", "Monto.Por.Devengar"]
            ].sum()
            st.dataframe(res_v, use_container_width=True, hide_index=True)

    with t_viaticos:
        if df_gasto.empty or "Genérica" not in df_gasto.columns:
            st.info("Sin datos de GASTO cargados.")
        else:
            df_viat = df_gasto[df_gasto["Genérica"].astype(str).str.lower() == "viaticos"].copy()
            for col_n in ["Monto.Dev.", "Monto.Por.Devengar", "Monto.Devuelto", "Monto.Por.Rendir"]:
                if col_n in df_viat.columns:
                    df_viat[col_n] = pd.to_numeric(df_viat[col_n], errors="coerce").fillna(0.0)
            res_viat = df_viat.groupby(["Programa", "Fuente", "GASTO", "RENDICIÓN"], as_index=False)[
                ["Monto.Dev.", "Monto.Por.Devengar", "Monto.Devuelto", "Monto.Por.Rendir"]
            ].sum()
            st.dataframe(res_viat, use_container_width=True, hide_index=True)

    buf_siged = io.BytesIO()
    with pd.ExcelWriter(buf_siged, engine='openpyxl') as writer:
        df_pend_interes.to_excel(writer, index=False, sheet_name='Pendientes_SIGED2')
        df_siged.to_excel(writer, index=False, sheet_name='SIGED_Completo')
        if not df_gasto.empty:
            df_gasto.to_excel(writer, index=False, sheet_name='GASTO')

    st.download_button(
        label="📥 Descargar Reporte SIGED & Cruce (.xlsx)",
        data=buf_siged.getvalue(),
        file_name=f"SUNASS_SIGED_Cruce_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
