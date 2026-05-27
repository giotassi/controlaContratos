import time
from datetime import timedelta

import pandas as pd
import streamlit as st

from services.monitor import MonitorService
from services.relatorio import RelatorioService
from services.tcu_apf import TCUAPFService

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
        )
    with c2:
        col_nome = st.selectbox(
            "Coluna de Razão Social",
            colunas,
            index=colunas.index(col_nome) if col_nome else 0,
        )

    incluir_cadin = st.checkbox(
        "Incluir CADIN/RS na consulta",
        value=True,
        help="Desmarque apenas se quiser acelerar o lote pulando o CADIN/RS.",
    )

    if not st.button("Processar Planilha", type="primary"):
        return

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

    total = len(df_proc)
    st.subheader("Progresso")
    progress_bar = st.progress(0.0)
    txt_progresso = st.empty()
    txt_tempo = st.empty()
    txt_status = st.empty()

    start_time = time.time()
    tempos: list[float] = []
    resultados: list = []
    pdfs_tcu: list = []
    pdfs_cadin: list = []

    for idx in range(total):
        row = df_proc.iloc[idx]
        cnpj = row["_cnpj_clean"]
        razao = str(row[col_nome]).strip() if col_nome else cnpj

        txt_status.info(f"({idx + 1}/{total}) {razao}")
        t0 = time.time()
        pdf_tcu = None
        pdf_cadin = None

        try:
            resultado = monitor.verificar_empresa(cnpj, razao, incluir_cadin=incluir_cadin)

            consulta_tcu = tcu_service.consultar(cnpj, emitir_pdf=False)
            if consulta_tcu and not consulta_tcu.get("error") and tcu_service.tem_restricao(consulta_tcu):
                certidao_tcu = tcu_service.consultar(cnpj, emitir_pdf=True)
                pdf_tcu = certidao_tcu.get("pdf_bytes") or {"error": certidao_tcu.get("error", "sem retorno")}

            if incluir_cadin and isinstance(resultado, dict):
                dados_cadin = resultado.get("cadin") or {}
                if dados_cadin.get("status") is False:
                    certidao_cadin = monitor.cadin.emitir_certidao_cadin(cnpj)
                    pdf_cadin = certidao_cadin.get("pdf_bytes") or {
                        "error": certidao_cadin.get("error", "sem retorno")
                    }
        except Exception as e:
            resultado = {"error": str(e)}
            txt_status.error(f"Erro em {razao}: {e}")

        resultados.append(resultado)
        pdfs_tcu.append(pdf_tcu)
        pdfs_cadin.append(pdf_cadin)

        elapsed_item = time.time() - t0
        tempos.append(elapsed_item)
        media = sum(tempos) / len(tempos)
        decorrido = time.time() - start_time
        restante = media * (total - (idx + 1))

        progress_bar.progress((idx + 1) / total)
        txt_progresso.markdown(f"**{idx + 1} / {total}** empresas processadas")
        txt_tempo.markdown(
            f"Decorrido: **{str(timedelta(seconds=int(decorrido)))}** | "
            f"Restante: **{str(timedelta(seconds=int(restante)))}** | "
            f"Média: **{media:.1f}s/empresa**"
        )

    try:
        monitor.cadin.fechar()
    except Exception:
        pass

    txt_status.success("Processamento concluído!")

    st.subheader("Resumo dos Resultados")
    irregulares_list = []
    erros_list = []
    regulares = 0

    for idx in range(total):
        row = df_proc.iloc[idx]
        cnpj = row["_cnpj_clean"]
        razao = str(row[col_nome]).strip() if col_nome else cnpj
        res = resultados[idx]

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
            if dados.get("status") is False:
                sistemas_irreg.append({
                    "Sistema": sistema.upper(),
                    "Observações": dados.get("observacoes", ""),
                })

        if sistemas_irreg:
            irregulares_list.append({"empresa": razao, "cnpj": cnpj, "sistemas": sistemas_irreg})
        else:
            regulares += 1

    m1, m2, m3 = st.columns(3)
    m1.metric("Total processado", total)
    m2.metric("Com impedimento", len(irregulares_list))
    m3.metric("Regulares", regulares)

    if erros_list:
        st.warning(f"{len(erros_list)} empresa(s) com erro de consulta:")
        st.dataframe(pd.DataFrame(erros_list), use_container_width=True)

    st.subheader("Certidões geradas automaticamente")
    certidoes_emitidas = 0
    for idx, (pdf_tcu, pdf_cadin) in enumerate(zip(pdfs_tcu, pdfs_cadin)):
        row = df_proc.iloc[idx]
        cnpj = row["_cnpj_clean"]
        razao = str(row[col_nome]).strip() if col_nome else cnpj
        if isinstance(pdf_tcu, bytes):
            certidoes_emitidas += 1
            st.download_button(
                f"Baixar TCU - {razao}",
                data=pdf_tcu,
                file_name=f"certidao_tcu_{cnpj}.pdf",
                mime="application/pdf",
                key=f"pdf_tcu_{idx}",
            )
        elif isinstance(pdf_tcu, dict) and pdf_tcu.get("error"):
            st.warning(f"{razao}: PDF TCU não emitido ({pdf_tcu['error']})")

        if isinstance(pdf_cadin, bytes):
            certidoes_emitidas += 1
            st.download_button(
                f"Baixar CADIN/RS - {razao}",
                data=pdf_cadin,
                file_name=f"certidao_cadin_rs_{cnpj}.pdf",
                mime="application/pdf",
                key=f"pdf_cadin_{idx}",
            )
        elif isinstance(pdf_cadin, dict) and pdf_cadin.get("error"):
            st.warning(f"{razao}: certidão CADIN/RS não emitida ({pdf_cadin['error']})")

    if certidoes_emitidas == 0:
        st.info("Nenhuma restrição em TCU ou CADIN/RS exigiu emissão de certidão.")

    if irregulares_list:
        st.error(f"### Empresas com impedimento ({len(irregulares_list)})")
        for item in irregulares_list:
            with st.expander(f"{item['empresa']} — {item['cnpj']}"):
                for sistema in item["sistemas"]:
                    st.markdown(f"**{sistema['Sistema']}:** {sistema['Observações']}")
    else:
        st.success("Nenhum impedimento encontrado nas empresas consultadas.")

    try:
        relatorio = RelatorioService()
        dados_relatorio = []
        for idx in range(total):
            row = df_proc.iloc[idx]
            res = resultados[idx]
            if isinstance(res, dict) and "error" not in res:
                dados_relatorio.append({
                    "cnpj": row["_cnpj_clean"],
                    "razao_social": str(row[col_nome]).strip() if col_nome else "",
                    **{k: v for k, v in res.items() if k not in ("status", "empresa_id")},
                })
        arquivo = relatorio.gerar_relatorio_impedimentos(dados_relatorio)
        if arquivo:
            st.success(f"Relatório gerado: {arquivo}")
    except Exception as e:
        st.warning(f"Relatório não gerado: {e}")
