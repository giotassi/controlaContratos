import streamlit as st
from services.monitor import MonitorService
from services.tcu_apf import TCUAPFService
import pandas as pd
import time
from datetime import timedelta
from services.relatorio import RelatorioService
from views.cadin_auth import exibir_status_cadin

_CNPJ_COLS = ["cpf/cnpj", "cnpj", "cpf", "documento", "cpf / cnpj", "cpf_cnpj"]
_NOME_COLS = ["contratado", "razão social", "razao social", "empresa", "nome", "fornecedor"]


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


def render():
    st.header("Consulta em Lote")

    exibir_status_cadin()

    monitor = MonitorService()
    tcu_service = TCUAPFService()

    uploaded_file = st.file_uploader(
        "Escolha uma planilha Excel",
        type=["xlsx", "xls"],
        help="A planilha deve conter colunas de CNPJ e nome da empresa",
    )

    if not uploaded_file:
        return

    try:
        df = pd.read_excel(uploaded_file, dtype=str)
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return

    st.write("Preview:")
    st.dataframe(df.head())

    # ── Detecção de colunas ───────────────────────────────────────────────────
    col_cnpj = _detectar_coluna(df, _CNPJ_COLS)
    col_nome = _detectar_coluna(df, _NOME_COLS)
    colunas  = list(df.columns)

    c1, c2 = st.columns(2)
    with c1:
        col_cnpj = st.selectbox("Coluna de CNPJ", colunas,
                                index=colunas.index(col_cnpj) if col_cnpj else 0)
    with c2:
        col_nome = st.selectbox("Coluna de Razão Social", colunas,
                                index=colunas.index(col_nome) if col_nome else 0)

    incluir_cadin = st.checkbox(
        "Incluir CADIN/RS na consulta (requer autenticação acima)",
        value=False,
        help="Desmarque para pular o CADIN e evitar alertas de sessão não autenticada.",
    )
    emitir_pdf_tcu = st.checkbox(
        "Emitir PDFs consolidados do TCU para a planilha",
        value=False,
        help="Deixe desmarcado para a consulta rapida. Marque apenas quando precisar anexar as certidoes consolidadas.",
    )

    if not st.button("Processar Planilha", type="primary"):
        return

    # ── Prepara linhas válidas ────────────────────────────────────────────────
    df_proc = df.copy()
    df_proc["_cnpj_clean"] = df_proc[col_cnpj].apply(_limpar_cnpj)
    linhas_originais = len(df_proc)
    df_proc = df_proc[df_proc["_cnpj_clean"].str.len().isin([11, 14])].reset_index(drop=True)

    if df_proc.empty:
        st.error(f"Nenhuma linha com CNPJ válido na coluna '{col_cnpj}'.")
        return
    if len(df_proc) < linhas_originais:
        st.warning(f"{linhas_originais - len(df_proc)} linha(s) ignorada(s) por documento vazio ou com tamanho invalido.")

    total = len(df_proc)

    # ── Progresso ─────────────────────────────────────────────────────────────
    st.subheader("Progresso")
    progress_bar  = st.progress(0.0)
    txt_progresso = st.empty()
    txt_tempo     = st.empty()
    txt_status    = st.empty()

    start_time = time.time()
    tempos: list[float] = []
    resultados: list    = []
    pdfs_tcu: list       = []

    for idx in range(total):
        row   = df_proc.iloc[idx]
        cnpj  = row["_cnpj_clean"]
        razao = str(row[col_nome]).strip() if col_nome else cnpj

        txt_status.info(f"🔄 ({idx + 1}/{total}) {razao}")

        t0 = time.time()
        pdf_tcu = None
        try:
            resultado = monitor.verificar_empresa(cnpj, razao, incluir_cadin=incluir_cadin)
            if emitir_pdf_tcu:
                consulta_tcu = tcu_service.consultar(cnpj, emitir_pdf=True)
                if consulta_tcu.get("error"):
                    pdf_tcu = {"error": consulta_tcu["error"]}
                else:
                    pdf_tcu = consulta_tcu.get("pdf_bytes")
        except Exception as e:
            resultado = {"error": str(e)}
            txt_status.error(f"Erro em {razao}: {e}")
        resultados.append(resultado)
        pdfs_tcu.append(pdf_tcu)

        elapsed_item = time.time() - t0
        tempos.append(elapsed_item)
        media     = sum(tempos) / len(tempos)
        decorrido = time.time() - start_time
        restante  = media * (total - (idx + 1))

        progress_bar.progress((idx + 1) / total)
        txt_progresso.markdown(f"**{idx + 1} / {total}** empresas processadas")
        txt_tempo.markdown(
            f"⏰ Decorrido: **{str(timedelta(seconds=int(decorrido)))}** &nbsp;|&nbsp; "
            f"⏳ Restante: **{str(timedelta(seconds=int(restante)))}** &nbsp;|&nbsp; "
            f"⚡ Média: **{media:.1f}s/empresa**"
        )

    try:
        monitor.cadin.fechar()
    except Exception:
        pass

    txt_status.success("✅ Processamento concluído!")

    # ── Resumo ─────────────────────────────────────────────────────────────────
    st.subheader("Resumo dos Resultados")

    irregulares_list = []
    erros_list       = []
    regulares        = 0

    for idx in range(total):
        row    = df_proc.iloc[idx]
        cnpj   = row["_cnpj_clean"]
        razao  = str(row[col_nome]).strip() if col_nome else cnpj
        res    = resultados[idx]

        if not isinstance(res, dict) or "error" in res:
            erros_list.append({
                "Empresa": razao,
                "CNPJ": cnpj,
                "Erro": res.get("error", str(res)) if isinstance(res, dict) else str(res),
            })
            continue

        sistemas_irreg = []
        for sistema, dados in res.items():
            if sistema in ("status", "empresa_id") or not isinstance(dados, dict):
                continue
            if not incluir_cadin and sistema.lower() in ("cadin", "cfil"):
                continue
            s = dados.get("status")
            if s is False:
                sistemas_irreg.append({
                    "Sistema": sistema.upper(),
                    "Observações": dados.get("observacoes", ""),
                })

        if sistemas_irreg:
            irregulares_list.append({
                "empresa": razao,
                "cnpj": cnpj,
                "sistemas": sistemas_irreg,
            })
        else:
            regulares += 1

    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("Total processado", total)
    m2.metric("Com impedimento", len(irregulares_list), delta=None)
    m3.metric("Regulares", regulares)

    if erros_list:
        st.warning(f"⚠️ {len(erros_list)} empresa(s) com erro de consulta:")
        st.dataframe(pd.DataFrame(erros_list), use_container_width=True)

    if emitir_pdf_tcu:
        st.subheader("PDFs consolidados do TCU")
        pdfs_emitidos = 0
        for idx, pdf in enumerate(pdfs_tcu):
            row = df_proc.iloc[idx]
            cnpj = row["_cnpj_clean"]
            razao = str(row[col_nome]).strip() if col_nome else cnpj
            if isinstance(pdf, bytes):
                pdfs_emitidos += 1
                st.download_button(
                    f"Baixar PDF TCU - {razao}",
                    data=pdf,
                    file_name=f"certidao_tcu_{cnpj}.pdf",
                    mime="application/pdf",
                    key=f"pdf_tcu_{idx}",
                )
            elif isinstance(pdf, dict) and pdf.get("error"):
                st.warning(f"{razao}: PDF do TCU nao emitido ({pdf['error']})")
        if pdfs_emitidos == 0:
            st.info("Nenhum PDF do TCU foi emitido.")

    # Tabela de impedimentos
    if irregulares_list:
        st.error(f"### ❌ Empresas com impedimento ({len(irregulares_list)})")
        for item in irregulares_list:
            with st.expander(f"❌ {item['empresa']} — {item['cnpj']}"):
                for s in item["sistemas"]:
                    st.markdown(f"**{s['Sistema']}:** {s['Observações']}")
    else:
        st.success("✅ Nenhum impedimento encontrado nas empresas consultadas.")

    # ── Relatório ─────────────────────────────────────────────────────────────
    try:
        relatorio = RelatorioService()
        dados_relatorio = []
        for idx in range(total):
            row = df_proc.iloc[idx]
            res = resultados[idx]
            if isinstance(res, dict) and "error" not in res:
                dados_relatorio.append({
                    "cnpj":        row["_cnpj_clean"],
                    "razao_social": str(row[col_nome]).strip() if col_nome else "",
                    **{k: v for k, v in res.items() if k not in ("status", "empresa_id")},
                })
        arquivo = relatorio.gerar_relatorio_impedimentos(dados_relatorio)
        if arquivo:
            st.success(f"Relatório gerado: {arquivo}")
    except Exception as e:
        st.warning(f"Relatório não gerado: {e}")
