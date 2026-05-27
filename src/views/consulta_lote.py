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


def _formatar_restricoes_tcu(restricoes: list[dict]) -> str:
    return "\n".join(
        " | ".join([
            f"Tipo: {certidao.get('tipo', 'TCU')}",
            f"Situação: {certidao.get('situacao', 'Restrição')}",
            f"Emissor: {certidao.get('emissor', 'N/A')}",
            f"Observação: {certidao.get('observacao') or 'N/A'}",
        ])
        for certidao in restricoes
    )


def _file_key(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    return hashlib.sha256(data).hexdigest()


def _reset_state():
    for key in list(st.session_state.keys()):
        if key.startswith(f"{_STATE_PREFIX}_"):
            del st.session_state[key]


def _init_state(df_proc: pd.DataFrame, col_nome: str, incluir_cfil: bool):
    st.session_state[f"{_STATE_PREFIX}_df"] = df_proc
    st.session_state[f"{_STATE_PREFIX}_col_nome"] = col_nome
    st.session_state[f"{_STATE_PREFIX}_incluir_cfil"] = incluir_cfil
    st.session_state[f"{_STATE_PREFIX}_idx"] = 0
    st.session_state[f"{_STATE_PREFIX}_resultados"] = []
    st.session_state[f"{_STATE_PREFIX}_pdfs_tcu"] = []
    st.session_state[f"{_STATE_PREFIX}_pdfs_cadin"] = []
    st.session_state[f"{_STATE_PREFIX}_tempos"] = []
    st.session_state[f"{_STATE_PREFIX}_started_at"] = time.time()


def _state_ready() -> bool:
    return f"{_STATE_PREFIX}_df" in st.session_state


def _empresa_nome(row, col_nome: str):
    return str(row[col_nome]).strip() if col_nome else row["_cnpj_clean"]


def _consultar_empresa(row, col_nome: str, incluir_cfil: bool, monitor: MonitorService, tcu_service: TCUAPFService):
    cnpj = row["_cnpj_clean"]
    razao = _empresa_nome(row, col_nome)
    resultado = monitor.verificar_empresa(
        cnpj,
        razao,
        incluir_cadin=True,
        incluir_cfil=incluir_cfil,
    )

    pdf_tcu = None
    pdf_cadin = None

    consulta_tcu = tcu_service.consultar(cnpj, emitir_pdf=False)
    if consulta_tcu and not consulta_tcu.get("error"):
        restricoes_tcu = [
            certidao for certidao in consulta_tcu.get("certidoes", [])
            if str(certidao.get("situacao", "")).upper() != "NADA_CONSTA"
        ]
        if isinstance(resultado, dict):
            resultado["tcu"] = {
                "status": not bool(restricoes_tcu),
                "observacoes": _formatar_restricoes_tcu(restricoes_tcu) if restricoes_tcu else "Regular",
            }
        if restricoes_tcu:
            certidao_tcu = tcu_service.consultar(cnpj, emitir_pdf=True)
            pdf_tcu = certidao_tcu.get("pdf_bytes") or {"error": certidao_tcu.get("error", "sem retorno")}
    elif consulta_tcu and consulta_tcu.get("error") and isinstance(resultado, dict):
        resultado["tcu"] = {"status": None, "observacoes": consulta_tcu["error"]}

    if isinstance(resultado, dict) and (resultado.get("cadin") or {}).get("status") is False:
        certidao_cadin = monitor.cadin.emitir_certidao_cadin(cnpj)
        pdf_cadin = certidao_cadin.get("pdf_bytes") or {"error": certidao_cadin.get("error", "sem retorno")}

    return resultado, pdf_tcu, pdf_cadin


def _processar_bloco(tamanho_bloco: int):
    df_proc = st.session_state[f"{_STATE_PREFIX}_df"]
    col_nome = st.session_state[f"{_STATE_PREFIX}_col_nome"]
    incluir_cfil = st.session_state[f"{_STATE_PREFIX}_incluir_cfil"]
    inicio = st.session_state[f"{_STATE_PREFIX}_idx"]
    fim = min(inicio + tamanho_bloco, len(df_proc))

    status_box = st.empty()
    progress = st.progress(inicio / len(df_proc))
    monitor = MonitorService()
    tcu_service = TCUAPFService()

    try:
        for idx in range(inicio, fim):
            row = df_proc.iloc[idx]
            razao = _empresa_nome(row, col_nome)
            status_box.info(f"Processando {idx + 1}/{len(df_proc)}: {razao}")
            t0 = time.time()
            try:
                resultado, pdf_tcu, pdf_cadin = _consultar_empresa(
                    row,
                    col_nome,
                    incluir_cfil,
                    monitor,
                    tcu_service,
                )
            except Exception as e:
                resultado, pdf_tcu, pdf_cadin = {"error": str(e)}, None, None

            st.session_state[f"{_STATE_PREFIX}_resultados"].append(resultado)
            st.session_state[f"{_STATE_PREFIX}_pdfs_tcu"].append(pdf_tcu)
            st.session_state[f"{_STATE_PREFIX}_pdfs_cadin"].append(pdf_cadin)
            st.session_state[f"{_STATE_PREFIX}_tempos"].append(time.time() - t0)
            st.session_state[f"{_STATE_PREFIX}_idx"] = idx + 1
            progress.progress((idx + 1) / len(df_proc))
    finally:
        try:
            monitor.cadin.fechar()
        except Exception:
            pass

    status_box.success(f"Bloco concluído: {fim}/{len(df_proc)} empresas processadas.")


def _coletar_resumo():
    df_proc = st.session_state[f"{_STATE_PREFIX}_df"]
    col_nome = st.session_state[f"{_STATE_PREFIX}_col_nome"]
    resultados = st.session_state[f"{_STATE_PREFIX}_resultados"]
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


def _render_status(tamanho_bloco: int):
    df_proc = st.session_state[f"{_STATE_PREFIX}_df"]
    idx = st.session_state[f"{_STATE_PREFIX}_idx"]
    tempos = st.session_state[f"{_STATE_PREFIX}_tempos"]
    total = len(df_proc)
    media = sum(tempos) / len(tempos) if tempos else 0
    restante = media * (total - idx)

    st.subheader("Progresso")
    st.progress(idx / total if total else 0)
    st.markdown(f"**{idx} / {total}** empresas processadas")
    if tempos:
        st.caption(
            f"Média: {media:.1f}s/empresa | Restante estimado: {str(timedelta(seconds=int(restante)))}"
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        if idx < total and st.button("Processar próximo bloco", type="primary"):
            _processar_bloco(tamanho_bloco)
            st.rerun()
    with col2:
        if st.button("Reiniciar este lote"):
            _reset_state()
            st.rerun()


def _render_resultados():
    if not _state_ready():
        return

    df_proc = st.session_state[f"{_STATE_PREFIX}_df"]
    idx = st.session_state[f"{_STATE_PREFIX}_idx"]
    irregulares, erros, regulares = _coletar_resumo()

    st.subheader("Resumo parcial" if idx < len(df_proc) else "Resumo final")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Processadas", idx)
    m2.metric("Pendentes", len(df_proc) - idx)
    m3.metric("Com impedimento", len(irregulares))
    m4.metric("Regulares", regulares)

    if erros:
        st.warning(f"{len(erros)} empresa(s) com erro de consulta:")
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
    df_proc = st.session_state[f"{_STATE_PREFIX}_df"]
    col_nome = st.session_state[f"{_STATE_PREFIX}_col_nome"]
    pdfs_tcu = st.session_state[f"{_STATE_PREFIX}_pdfs_tcu"]
    pdfs_cadin = st.session_state[f"{_STATE_PREFIX}_pdfs_cadin"]

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
    df_proc = st.session_state[f"{_STATE_PREFIX}_df"]
    col_nome = st.session_state[f"{_STATE_PREFIX}_col_nome"]
    resultados = st.session_state[f"{_STATE_PREFIX}_resultados"]

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
    if st.session_state.get(f"{_STATE_PREFIX}_file_key") != current_file_key:
        _reset_state()
        st.session_state[f"{_STATE_PREFIX}_file_key"] = current_file_key

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
        "Incluir CFIL/RS no lote",
        value=False,
        help="CFIL usa o relatório Power BI e deixa o lote muito mais lento. CADIN/RS será sempre consultado.",
        disabled=_state_ready(),
    )
    tamanho_bloco = st.slider(
        "Empresas por bloco",
        min_value=1,
        max_value=20,
        value=5,
        help="Blocos menores evitam perda de sessão no Streamlit Cloud.",
    )

    if not _state_ready():
        df_proc = df.copy()
        df_proc["_cnpj_clean"] = df_proc[col_cnpj].apply(_limpar_cnpj)
        linhas_originais = len(df_proc)
        df_proc = df_proc[df_proc["_cnpj_clean"].str.len().isin([11, 14])].reset_index(drop=True)

        if df_proc.empty:
            st.error(f"Nenhuma linha com CNPJ válido na coluna '{col_cnpj}'.")
            return
        if len(df_proc) < linhas_originais:
            st.warning(
                f"{linhas_originais - len(df_proc)} linha(s) ignorada(s) por documento vazio ou com tamanho inválido."
            )

        st.info(
            f"{len(df_proc)} empresa(s) serão processadas. CADIN/RS será consultado em todas."
        )
        if st.button("Iniciar processamento", type="primary"):
            _init_state(df_proc, col_nome, incluir_cfil)
            st.rerun()
        return

    _render_status(tamanho_bloco)
    _render_resultados()
