import streamlit as st
from datetime import datetime, date
from services.database import DatabaseService
from services.certidoes_service import (
    consultar_cnpj,
    links_para_empresa,
    extrair_data_validade,
    classificar_status,
    resumo_alertas,
    TIPOS_CERTIDAO,
)


def render():
    st.header("Certidões Negativas")

    db = DatabaseService()
    tab_dash, tab_add, tab_list = st.tabs(["📊 Dashboard", "➕ Adicionar", "📋 Listar"])

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1 — Dashboard de alertas
    # ──────────────────────────────────────────────────────────────────────────
    with tab_dash:
        todas = db.listar_certidoes()
        alertas = resumo_alertas(todas)
        total = sum(alertas.values())

        if total == 0:
            st.info("Nenhuma certidão cadastrada ainda. Use a aba **Adicionar** para começar.")
        else:
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("🔴 Vencidas",       alertas["vencidas"])
            col2.metric("🟠 Vence em 7d",    alertas["a7"])
            col3.metric("🟡 Vence em 15d",   alertas["a15"])
            col4.metric("🔵 Vence em 30d",   alertas["a30"])
            col5.metric("🟢 Regulares",      alertas["regulares"])

            st.divider()

            # Certidões que precisam de atenção
            proximas = db.listar_certidoes_proximas(dias=30)
            if proximas:
                st.subheader("Atenção — Certidões vencidas ou a vencer em 30 dias")
                hoje = date.today()
                for cert in proximas:
                    emp = cert.get("empresas") or {}
                    razao = emp.get("razao_social", "—")
                    cnpj  = emp.get("cnpj", "—")
                    try:
                        val  = date.fromisoformat(cert["data_validade"])
                        dias = (val - hoje).days
                        label, _ = classificar_status(val)
                    except Exception:
                        val, dias, label = None, None, "?"

                    if dias is not None and dias < 0:
                        cor = "🔴"
                    elif dias is not None and dias <= 7:
                        cor = "🟠"
                    elif dias is not None and dias <= 15:
                        cor = "🟡"
                    else:
                        cor = "🔵"

                    with st.expander(
                        f"{cor} {razao} ({cnpj}) — {cert['tipo']} — {label}"
                    ):
                        col_a, col_b, col_c = st.columns(3)
                        col_a.write(f"**Tipo:** {cert['tipo']}")
                        col_b.write(f"**Validade:** {val.strftime('%d/%m/%Y') if val else '—'}")
                        col_c.write(f"**Dias restantes:** {dias if dias is not None else '—'}")
                        if cert.get("arquivo_url"):
                            st.link_button("📄 Abrir certidão", cert["arquivo_url"])
            else:
                st.success("Todas as certidões estão regulares (validade > 30 dias).")

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2 — Adicionar certidão
    # ──────────────────────────────────────────────────────────────────────────
    with tab_add:
        st.subheader("Nova certidão")

        # — Busca empresa pelo CNPJ ————————————————————————————————————————————
        cnpj_input = st.text_input("CNPJ da empresa", placeholder="00.000.000/0000-00")
        dados_cnpj = {}
        uf = None
        municipio = None

        if cnpj_input and len("".join(c for c in cnpj_input if c.isdigit())) == 14:
            with st.spinner("Consultando CNPJ…"):
                dados_cnpj = consultar_cnpj(cnpj_input)

            if dados_cnpj:
                razao = dados_cnpj.get("razao_social", "")
                uf    = dados_cnpj.get("uf", "")
                municipio = dados_cnpj.get("municipio", "")
                st.success(f"**{razao}** — {municipio}/{uf}")
            else:
                st.warning("CNPJ não encontrado na Receita Federal.")

        # — Links de portais ——————————————————————————————————————————————————
        if dados_cnpj:
            links = links_para_empresa(uf, municipio)
            st.subheader("Portais para emissão")
            st.caption("Acesse o portal, emita a certidão e faça o upload abaixo.")
            cols = st.columns(min(len(links), 3))
            for i, (nome_cert, (descricao, url)) in enumerate(links.items()):
                with cols[i % 3]:
                    st.link_button(f"🌐 {nome_cert}", url, use_container_width=True)
                    st.caption(descricao)

            st.divider()

        # — Formulário de upload ———————————————————————————————————————————————
        with st.form("form_certidao", clear_on_submit=True):
            tipo = st.selectbox("Tipo de certidão", TIPOS_CERTIDAO)

            arquivo = st.file_uploader(
                "PDF da certidão",
                type=["pdf"],
                help="O sistema tentará extrair a data de validade automaticamente.",
            )

            # Tenta extrair data do PDF automaticamente
            data_validade_auto = None
            if arquivo is not None:
                pdf_bytes = arquivo.read()
                arquivo.seek(0)  # reset para upload posterior
                data_validade_auto = extrair_data_validade(pdf_bytes)
                if data_validade_auto:
                    st.info(f"Data de validade detectada no PDF: **{data_validade_auto.strftime('%d/%m/%Y')}**")

            col1, col2 = st.columns(2)
            with col1:
                data_emissao = st.date_input("Data de emissão", value=date.today())
            with col2:
                data_validade = st.date_input(
                    "Data de validade",
                    value=data_validade_auto or date.today(),
                )

            numero = st.text_input("Número da certidão (opcional)")

            enviado = st.form_submit_button("Salvar certidão", type="primary")

        if enviado:
            digits = "".join(c for c in cnpj_input if c.isdigit()) if cnpj_input else ""
            if not digits or len(digits) != 14:
                st.error("Informe um CNPJ válido antes de salvar.")
            elif arquivo is None:
                st.error("Anexe o PDF da certidão.")
            else:
                empresa_id = db.obter_empresa_id(digits)
                if not empresa_id:
                    # Cadastra empresa automaticamente se não existir
                    razao = dados_cnpj.get("razao_social", "Empresa") if dados_cnpj else "Empresa"
                    emp = db.add_empresa(digits, razao)
                    empresa_id = emp["id"] if emp else None

                if empresa_id:
                    ok = db.adicionar_certidao(
                        empresa_id=empresa_id,
                        tipo=tipo,
                        data_emissao=data_emissao,
                        data_validade=data_validade,
                        numero_certidao=numero or None,
                        arquivo=arquivo,
                    )
                    if ok:
                        st.success("Certidão salva com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar — verifique o bucket 'certidoes' no Supabase.")
                else:
                    st.error("Não foi possível identificar/cadastrar a empresa.")

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 3 — Listar e gerenciar
    # ──────────────────────────────────────────────────────────────────────────
    with tab_list:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_status = st.selectbox(
                "Status",
                ["Todas", "Vencidas", "A vencer em 30 dias", "Regulares"],
                key="list_status",
            )
        with col_f2:
            filtro_tipo = st.selectbox(
                "Tipo",
                ["Todas"] + TIPOS_CERTIDAO,
                key="list_tipo",
            )

        certidoes = db.listar_certidoes(status=filtro_status, tipo=filtro_tipo)

        if not certidoes:
            st.info("Nenhuma certidão encontrada com esses filtros.")
        else:
            hoje = date.today()
            for empresa in certidoes:
                with st.expander(
                    f"{empresa['razao_social']} — {empresa['cnpj']}"
                    f" ({len(empresa['certidoes'])} certidão/ões)"
                ):
                    for cert in empresa["certidoes"]:
                        try:
                            val  = date.fromisoformat(cert["data_validade"])
                            dias = (val - hoje).days
                            label, _ = classificar_status(val)
                            cor = "🔴" if dias < 0 else ("🟠" if dias <= 7 else ("🟡" if dias <= 15 else ("🔵" if dias <= 30 else "🟢")))
                        except Exception:
                            val, dias, label, cor = None, None, "?", "⚪"

                        c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                        c1.write(f"**{cert['tipo']}**")
                        c2.write(f"Validade: {val.strftime('%d/%m/%Y') if val else '—'}")
                        c3.write(f"{cor} {label}")
                        with c4:
                            if cert.get("arquivo_url"):
                                st.link_button("📄", cert["arquivo_url"], use_container_width=True)
                            if st.button("🗑️", key=f"del_{cert['id']}", help="Excluir"):
                                if db.excluir_certidao(cert["id"]):
                                    st.rerun()
