import hashlib
import time
from datetime import timedelta

import pandas as pd
import streamlit as st

from services.monitor import MonitorService
from services.relatorio import RelatorioService
from services.tcu_apf import TCUAPFService

_CNPJ_COLS = ["cpf/cnpj", "cnpj", "cpf", "documento", "cpf / cnpj", "cpf_cnpj"]
_NOME_COLS = ["contratado", "razão social", "razao social", "empresa", "nome", "fornecedor"]
_STATE_PREFIX = "consulta_lote"


def _detectar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    mapa = {c.lower().strip(): c for c in df.columns}
    for cand in candidatos:
        if cand in mapa:
            return mapa[cand]
    return None


def _limpar_cnpj(valor) -> str:
    digits = "".join(c for c in str(valor) if c.isdigit())
    if len(digits) == 13:
        digits = digits.zfill(14)
    elif len(digits) == 10:
        digits = digits.zfill(11)
    return digits


def _file_key(uploaded_file) -> str:
    return hashlib.sha256(uploaded_file.getvalue()).hexdigest()


def _state_key(name: str) -> str:
    return f"{_STATE_PREFIX}_{name}"


def _reset_state():
    for key in list(st.session_state.keys()):
        if key.startswith(f"{_STATE_PREFIX}_"):
            del st.session_state[key]


def _state_ready() -> bool:
    return _state_key("df") in st.session_state


def _empresa_nome(row, col_nome: str):
    return str(row[col_nome]).strip() if col_nome else row["_cnpj_clean"]


def _init_state(df_proc: pd.DataFrame, col_nome: str, incluir_cfil: bool):
    st.session_state[_state_key("df")] = df_proc
    st.session_state[_state_key("col_nome")] = col_nome
    st.session_state[_state_key("incluir_cfil")] = incluir_cfil
    st.session_state[_state_key("idx")] = 0
    st.session_state[_state_key("running")] = True
    st.session_state[_state_key("resultados")] = []
    st.session_state[_state_key("pdfs_tcu")] = []
    st.session_state[_state_key("pdfs_cadin")] = []
    st.session_state[_state_key("tempos")] = []
    st.session_state[_state_key("started_at")] = time.time()
    st.session_state[_state_key("last_status")] = ""


def _consultar_empresa(row, col_nome: str, incluir_cfil: bool):
    monitor = MonitorService()
    tcu_service = TCUAPFService()
    cnpj = row["_cnpj_clean"]
    razao = _empresa_nome(row, col_nome)

    resultado = monitor.verificar_empresa(
        cnpj,
        razao,
        incluir_cadin=True,
        incluir_cfil=incluir_cfil,
        salvar=True,
    )

    pdf_tcu = None
    pdf_cadin = None
    if isinstance(resultado, dict) and (resultado.get("tcu") or {}).get("status") is False:
        certidao_tcu = tcu_service.consultar(cnpj, emitir_pdf=True)
        pdf_tcu = certidao_tcu.get("pdf_bytes") or {"error": certidao_tcu.get("error", "sem retorno")}

    if isinstance(resultado, dict) and (resultado.get("cadin") or {}).get("status") is False:
        certidao_cadin = monitor.cadin.emitir_certidao_cadin(cnpj)
        pdf_cadin = certidao_cadin.get("pdf_bytes") or {"error": certidao_cadin.get("error", "sem retorno")}

    try:
        monitor.cadin.fechar()
    except Exception:
        pass

    return resultado, pdf_tcu, pdf_cadin


def _processar_uma_empresa():
    df_proc = st.session_state[_state_key("df")]
    idx = st.session_state[_state_key("idx")]
    if idx >= len(df_proc):
        st.session_state[_state_key("running")] = False
        return

    col_nome = st.session_state[_state_key("col_nome")]
    incluir_cfil = st.session_state[_state_key("incluir_cfil")]
    row = df_proc.iloc[idx]
    razao = _empresa_nome(row, col_nome)
    cnpj = row["_cnpj_clean"]

    st.session_state[_state_key("last_status")] = f"Processando {idx + 1}/{len(df_proc)}: {razao}"
    t0 = time.time()
    try:
        resultado, pdf_tcu, pdf_cadin = _consultar_empresa(row, col_nome, incluir_cfil)
    except Exception as e:
        resultado, pdf_tcu, pdf_cadin = {"error": str(e)}, None, None

    tempo = time.time() - t0
    st.session_state[_state_key("resultados")].append(resultado)
    st.session_state[_state_key("pdfs_tcu")].append(pdf_tcu)
    st.session_state[_state_key("pdfs_cadin")].append(pdf_cadin)
    st.session_state[_state_key("tempos")].append(tempo)
    st.session_state[_state_key("idx")] = idx + 1
    st.session_state[_state_key("last_status")] = f"Última: {razao} ({cnpj}) em {tempo:.1f}s"

    if st.session_state[_state_key("idx")] >= len(df_proc):
        st.session_state[_state_key("running")] = False


def _coletar_resumo():
    df_proc = st.session_state[_state_key("df")]
    col_nome = st.session_state[_state_key("col_nome")]
    resultados = st.session_state[_state_key("resultados")]
    irregulares, erros, regulares = [], [], 0

    for idx, res in enumerate(resultados):
        row = df_proc.iloc[idx]
        cnpj = row["_cnpj_clean"]
        razao = _empresa_nome(row, col_nome)
        if not isinstance(res, dict) or "error" in res:
            erros.append({
                "Empresa": razao,
                "CNPJ": cnpj,
                "Erro": res.get("error", str(res)) if isinstance(res, dict) else str(res),
            })
            continue

        sistemas_irreg = []
        for sistema, dados in res.items():
            if sistema in ("status", "empresa_id") or not isinstance(dados, dict):
                continue
            if dados.get("status") is False:
                sistemas_irreg.append({
                    "Sistema": sistema.upper(),
                    "Observações": dados.get("observacoes", ""),
                })

        if sistemas_irreg:
            irregulares.append({"empresa": razao, "cnpj": cnpj, "sistemas": sistemas_irreg})
        else:
            regulares += 1

    return irregulares, erros, regulares


def _render_progresso():
    df_proc = st.session_state[_state_key("df")]
    idx = st.session_state[_state_key("idx")]
    tempos = st.session_state[_state_key("tempos")]
    total = len(df_proc)
    media = sum(tempos) / len(tempos) if tempos else 0
    restante = media * (total - idx)

    st.subheader("Progresso")
    st.progress(idx / total if total else 0)
    st.markdown(f"**{idx} / {total}** empresas processadas")
    if st.session_state.get(_state_key("last_status")):
        st.info(st.session_state[_state_key("last_status")])
    if tempos:
        st.caption(
            f"Última consulta: {tempos[-1]:.1f}s | Média: {media:.1f}s/empresa | "
            f"Restante estimado: {str(timedelta(seconds=int(restante)))}"
        )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if idx < total and not st.session_state[_state_key("running")]:
            if st.button("Continuar processamento", type="primary"):
                st.session_state[_state_key("running")] = True
                st.rerun()
    with col2:
        if idx < total and st.session_state[_state_key("running")]:
            if st.button("Pausar"):
                st.session_state[_state_key("running")] = False
                st.rerun()
    with col3:
        if st.button("Reiniciar"):
            _reset_state()
            st.rerun()


def _render_resultados():
    df_proc = st.session_state[_state_key("df")]
    idx = st.session_state[_state_key("idx")]
    irregulares, erros, regulares = _coletar_resumo()

    st.subheader("Resumo parcial" if idx < len(df_proc) else "Resumo final")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Processadas", idx)
    m2.metric("Pendentes", len(df_proc) - idx)
    m3.metric("Com impedimento", len(irregulares))
    m4.metric("Regulares", regulares)

    if erros:
        st.warning(f"{len(erros)} empresa(s) com erro técnico:")
        st.dataframe(pd.DataFrame(erros), use_container_width=True)

    _render_certidoes()

    if irregulares:
        st.error(f"### Empresas com impedimento ({len(irregulares)})")
        for item in irregulares:
            with st.expander(f"{item['empresa']} — {item['cnpj']}"):
                for sistema in item["sistemas"]:
                    st.markdown(f"**{sistema['Sistema']}:** {sistema['Observações']}")

    if idx == len(df_proc):
        _render_relatorio()


def _render_certidoes():
    df_proc = st.session_state[_state_key("df")]
    col_nome = st.session_state[_state_key("col_nome")]
    pdfs_tcu = st.session_state[_state_key("pdfs_tcu")]
    pdfs_cadin = st.session_state[_state_key("pdfs_cadin")]

    certidoes_emitidas = 0
    for idx, (pdf_tcu, pdf_cadin) in enumerate(zip(pdfs_tcu, pdfs_cadin)):
        row = df_proc.iloc[idx]
        cnpj = row["_cnpj_clean"]
        razao = _empresa_nome(row, col_nome)
        if isinstance(pdf_tcu, bytes):
            certidoes_emitidas += 1
            st.download_button(
                f"Baixar TCU - {razao}",
                data=pdf_tcu,
                file_name=f"certidao_tcu_{cnpj}.pdf",
                mime="application/pdf",
                key=f"pdf_tcu_{idx}",
            )
        if isinstance(pdf_cadin, bytes):
            certidoes_emitidas += 1
            st.download_button(
                f"Baixar CADIN/RS - {razao}",
                data=pdf_cadin,
                file_name=f"certidao_cadin_rs_{cnpj}.pdf",
                mime="application/pdf",
                key=f"pdf_cadin_{idx}",
            )

    if certidoes_emitidas:
        st.caption(f"{certidoes_emitidas} certidão(ões) emitida(s) automaticamente.")


def _render_relatorio():
    df_proc = st.session_state[_state_key("df")]
    col_nome = st.session_state[_state_key("col_nome")]
    resultados = st.session_state[_state_key("resultados")]

    relatorio = RelatorioService()
    dados_relatorio = []
    for idx, res in enumerate(resultados):
        row = df_proc.iloc[idx]
        if isinstance(res, dict) and "error" not in res:
            dados_relatorio.append({
                "cnpj": row["_cnpj_clean"],
                "razao_social": _empresa_nome(row, col_nome),
                **{k: v for k, v in res.items() if k not in ("status", "empresa_id")},
            })

    arquivo = relatorio.gerar_relatorio_impedimentos(dados_relatorio)
    if not arquivo:
        st.info("Nenhum impedimento para gerar relatório.")
        return

    pdf_relatorio = relatorio.ler_relatorio(arquivo)
    if pdf_relatorio:
        st.download_button(
            "Baixar relatório de empresas impedidas",
            data=pdf_relatorio,
            file_name=arquivo,
            mime="application/pdf",
        )


def _preparar_planilha(df: pd.DataFrame, col_cnpj: str):
    df_proc = df.copy()
    df_proc["_cnpj_clean"] = df_proc[col_cnpj].apply(_limpar_cnpj)
    linhas_originais = len(df_proc)
    df_proc = df_proc[df_proc["_cnpj_clean"].str.len().isin([11, 14])].reset_index(drop=True)
    return df_proc, linhas_originais - len(df_proc)


def render():
    st.header("Consulta em Lote")

    uploaded_file = st.file_uploader(
        "Escolha uma planilha Excel",
        type=["xlsx", "xls"],
        help="A planilha deve conter colunas de CNPJ e nome da empresa",
    )
    if not uploaded_file:
        return

    current_file_key = _file_key(uploaded_file)
    if st.session_state.get(_state_key("file_key")) != current_file_key:
        _reset_state()
        st.session_state[_state_key("file_key")] = current_file_key

    try:
        df = pd.read_excel(uploaded_file, dtype=str)
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return

    st.write("Preview:")
    st.dataframe(df.head(), use_container_width=True)

    col_cnpj = _detectar_coluna(df, _CNPJ_COLS)
    col_nome = _detectar_coluna(df, _NOME_COLS)
    colunas = list(df.columns)

    c1, c2 = st.columns(2)
    with c1:
        col_cnpj = st.selectbox(
            "Coluna de CNPJ",
            colunas,
            index=colunas.index(col_cnpj) if col_cnpj else 0,
            disabled=_state_ready(),
        )
    with c2:
        col_nome = st.selectbox(
            "Coluna de Razão Social",
            colunas,
            index=colunas.index(col_nome) if col_nome else 0,
            disabled=_state_ready(),
        )

    incluir_cfil = st.checkbox(
        "Incluir CFIL/RS no processamento",
        value=False,
        help="CFIL usa Power BI/Selenium e pode deixar a consulta muito lenta. CADIN/RS será sempre consultado.",
        disabled=_state_ready(),
    )

    if not _state_ready():
        df_proc, ignoradas = _preparar_planilha(df, col_cnpj)
        if df_proc.empty:
            st.error(f"Nenhuma linha com CNPJ válido na coluna '{col_cnpj}'.")
            return
        if ignoradas:
            st.warning(f"{ignoradas} linha(s) ignorada(s) por documento vazio ou com tamanho inválido.")
        st.info(f"{len(df_proc)} empresa(s) serão processadas. CADIN/RS será consultado em todas.")
        if st.button("Iniciar processamento", type="primary"):
            _init_state(df_proc, col_nome, incluir_cfil)
            st.rerun()
        return

    _render_progresso()
    _render_resultados()

    if st.session_state.get(_state_key("running")):
        _processar_uma_empresa()
        time.sleep(0.2)
        st.rerun()
