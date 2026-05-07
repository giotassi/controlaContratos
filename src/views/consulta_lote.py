import streamlit as st
from services.monitor import MonitorService
import pandas as pd
import time
from datetime import timedelta
from services.relatorio import RelatorioService
from views.cadin_auth import exibir_status_cadin

# Nomes aceitos para cada coluna (case-insensitive)
_CNPJ_COLS    = ["cpf/cnpj", "cnpj", "cpf", "documento", "cpf / cnpj", "cpf_cnpj"]
_NOME_COLS    = ["contratado", "razão social", "razao social", "empresa", "nome", "fornecedor"]


def _detectar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    mapa = {c.lower().strip(): c for c in df.columns}
    for cand in candidatos:
        if cand in mapa:
            return mapa[cand]
    return None


def render():
    st.header("Consulta em Lote")

    exibir_status_cadin()

    monitor = MonitorService()

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

    # ── Detecção automática de colunas ────────────────────────────────────────
    col_cnpj  = _detectar_coluna(df, _CNPJ_COLS)
    col_nome  = _detectar_coluna(df, _NOME_COLS)

    colunas = list(df.columns)

    col1, col2 = st.columns(2)
    with col1:
        col_cnpj = st.selectbox(
            "Coluna de CNPJ",
            colunas,
            index=colunas.index(col_cnpj) if col_cnpj else 0,
        )
    with col2:
        col_nome = st.selectbox(
            "Coluna de Razão Social",
            colunas,
            index=colunas.index(col_nome) if col_nome else 0,
        )

    incluir_cadin = st.checkbox(
        "Incluir CADIN/RS na consulta (requer autenticação acima)",
        value=False,
        help="Desmarque para pular o CADIN e evitar alertas de sessão não autenticada.",
    )

    if not st.button("Processar Planilha", type="primary"):
        return

    # ── Filtra linhas com CNPJ válido ─────────────────────────────────────────
    def _limpar_cnpj(valor) -> str:
        digits = "".join(c for c in str(valor) if c.isdigit())
        if len(digits) == 13:   # zero à esquerda perdido pelo Excel
            digits = digits.zfill(14)
        elif len(digits) == 10: # CPF sem zero
            digits = digits.zfill(11)
        return digits

    df_proc = df.copy()
    df_proc["_cnpj_clean"] = df_proc[col_cnpj].apply(_limpar_cnpj)
    df_proc = df_proc[df_proc["_cnpj_clean"].str.len().isin([11, 14])].reset_index(drop=True)

    if df_proc.empty:
        st.error(f"Nenhuma linha com CNPJ válido encontrada na coluna '{col_cnpj}'.")
        return

    total = len(df_proc)

    # ── Progresso ─────────────────────────────────────────────────────────────
    st.subheader("Progresso")
    progress_bar   = st.progress(0.0)
    txt_progresso  = st.empty()
    txt_decorrido  = st.empty()
    txt_restante   = st.empty()
    txt_media      = st.empty()
    txt_status     = st.empty()

    start_time = time.time()
    tempos: list[float] = []
    resultados: list   = []

    for idx in range(total):
        row        = df_proc.iloc[idx]
        cnpj       = row["_cnpj_clean"]
        razao      = str(row[col_nome]).strip() if col_nome else cnpj

        txt_status.info(f"🔄 Consultando ({idx + 1}/{total}): {razao}")

        t0        = time.time()
        resultado = monitor.verificar_empresa(cnpj, razao)
        resultados.append(resultado)

        elapsed_item = time.time() - t0
        tempos.append(elapsed_item)
        media        = sum(tempos) / len(tempos)
        decorrido    = time.time() - start_time
        restante     = media * (total - (idx + 1))

        progress_bar.progress((idx + 1) / total)
        txt_progresso.markdown(f"**{idx + 1} / {total}** empresas processadas")
        txt_decorrido.markdown(f"⏰ Decorrido: **{str(timedelta(seconds=int(decorrido)))}**")
        txt_restante.markdown(f"⏳ Estimado restante: **{str(timedelta(seconds=int(restante)))}**")
        txt_media.markdown(f"⚡ Média por empresa: **{media:.1f}s**")

    txt_status.success("✅ Processamento concluído!")

    # ── Resultados ────────────────────────────────────────────────────────────
    st.subheader("Resultados")
    for idx in range(total):
        row    = df_proc.iloc[idx]
        cnpj   = row["_cnpj_clean"]
        razao  = str(row[col_nome]).strip() if col_nome else cnpj
        resultado = resultados[idx]
        label  = f"{razao} ({cnpj})"

        if not isinstance(resultado, dict) or "error" in resultado:
            st.error(f"❌ {label}: Erro — {resultado}")
            continue

        irregulares     = []
        nao_consultados = []
        for sistema, res in resultado.items():
            if sistema == "status" or not isinstance(res, dict):
                continue
            if not incluir_cadin and sistema.lower() == "cadin":
                continue
            s = res.get("status")
            if s is None:
                nao_consultados.append(sistema.upper())
            elif not s:
                irregulares.append((sistema.upper(), res.get("observacoes", "N/A")))

        if irregulares:
            with st.expander(f"❌ {label} — Irregular"):
                for sistema, obs in irregulares:
                    st.write(f"- **{sistema}:** {obs}")
        else:
            st.success(f"✅ {label} — Regular em todos os sistemas")

        if nao_consultados:
            st.warning(
                f"⚠️ {label}: {', '.join(nao_consultados)} não consultado(s) "
                "— autentique o CADIN acima para incluir."
            )

    # ── Relatório ─────────────────────────────────────────────────────────────
    try:
        relatorio = RelatorioService()
        dados_relatorio = []
        for idx in range(total):
            row       = df_proc.iloc[idx]
            resultado = resultados[idx]
            if isinstance(resultado, dict) and "error" not in resultado:
                dados_relatorio.append({
                    "cnpj":        row["_cnpj_clean"],
                    "razao_social": str(row[col_nome]).strip() if col_nome else "",
                    **{k: v for k, v in resultado.items() if k not in ("status", "empresa_id")},
                })
        arquivo = relatorio.gerar_relatorio_impedimentos(dados_relatorio)
        if arquivo:
            st.success(f"Relatório gerado: {arquivo}")
    except Exception as e:
        st.warning(f"Relatório não gerado: {e}")
