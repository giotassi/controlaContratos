"""
Serviço de certidões negativas.

Responsabilidades:
  - Lookup de dados do CNPJ via BrasilAPI (UF, município)
  - Links diretos para portais de emissão por UF
  - Extração de data de validade de PDFs (pdfplumber + regex)
  - Classificação de status por vencimento
"""
import io
import logging
import re
import requests
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Portais de emissão
# ──────────────────────────────────────────────────────────────────────────────

PORTAIS_FEDERAIS = {
    "CND Federal": (
        "Certidão Conjunta Receita Federal + PGFN",
        "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/CertidaoNegativa.asp",
    ),
    "FGTS": (
        "Certificado de Regularidade do FGTS — Caixa",
        "https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregadorCrf.jsf",
    ),
    "CNDT": (
        "Certidão Negativa de Débitos Trabalhistas — TST",
        "https://cndt-certidao.tst.jus.br/",
    ),
}

PORTAIS_ESTADUAIS = {
    "RS": ("SEFAZ/RS",   "https://www.sefaz.rs.gov.br/sat/CertidaoSitFiscalSolic.aspx"),
    "SP": ("Fazenda SP", "https://www10.fazenda.sp.gov.br/CertidaoNegativaDeb/Pages/EmissaoCertidaoNegativa.aspx"),
    "SC": ("SEF/SC",     "https://sat.sef.sc.gov.br/tax.NET/Sat.CtaCte.Web/SolicitacaoCnd.aspx"),
    "PR": ("SEFAZ/PR",   "https://www.fazenda.pr.gov.br/servicos/Mais-buscados/Certidoes/Emitir-Certidao-Negativa-Receita-Estadual-kZrX5gol"),
}

# Tipos de certidão para o formulário
TIPOS_CERTIDAO = [
    "CND Federal",
    "FGTS",
    "CNDT",
    "Estadual",
    "Municipal",
]

# Limites de alerta em dias
ALERTAS_DIAS = [7, 15, 30]


# ──────────────────────────────────────────────────────────────────────────────
# Lookup CNPJ
# ──────────────────────────────────────────────────────────────────────────────

def consultar_cnpj(cnpj: str) -> dict:
    """Retorna dados cadastrais do CNPJ via BrasilAPI. Retorna {} em caso de erro."""
    digits = "".join(c for c in cnpj if c.isdigit())
    try:
        resp = requests.get(
            f"https://brasilapi.com.br/api/cnpj/v1/{digits}",
            timeout=10,
            headers={"User-Agent": "MonitorContratos/1.0"},
        )
        if resp.ok:
            return resp.json()
    except Exception as e:
        logger.warning("Falha ao consultar BrasilAPI para %s: %s", cnpj, e)
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Links de portais
# ──────────────────────────────────────────────────────────────────────────────

def links_para_empresa(uf: str | None, municipio: str | None) -> dict:
    """
    Retorna dict {nome_certidao: (descricao, url)} com os portais relevantes
    para a UF e município informados.
    """
    links = dict(PORTAIS_FEDERAIS)

    if uf:
        uf_upper = uf.upper()
        if uf_upper in PORTAIS_ESTADUAIS:
            nome, url = PORTAIS_ESTADUAIS[uf_upper]
            links[f"Estadual {uf_upper}"] = (f"Certidão Estadual — {nome}", url)
        else:
            # Estado sem integração: link de busca genérico
            links[f"Estadual {uf_upper}"] = (
                f"Certidão Estadual — {uf_upper} (sem integração direta)",
                f"https://www.google.com/search?q=certidao+negativa+estadual+{uf_upper}",
            )

    if municipio:
        mun_slug = municipio.lower().replace(" ", "+")
        links["Municipal"] = (
            f"Certidão Municipal — {municipio}",
            f"https://www.google.com/search?q=certidao+negativa+municipal+{mun_slug}",
        )

    return links


# ──────────────────────────────────────────────────────────────────────────────
# Extração de data de validade do PDF
# ──────────────────────────────────────────────────────────────────────────────

# Padrões mais comuns nas certidões brasileiras
_PADROES_DATA = [
    r"v[áa]lid[ao]?\s+at[eé]\s+(\d{2}/\d{2}/\d{4})",
    r"validade[:\s]+(\d{2}/\d{2}/\d{4})",
    r"prazo\s+de\s+validade[:\s]+(\d{2}/\d{2}/\d{4})",
    r"vencimento[:\s]+(\d{2}/\d{2}/\d{4})",
    r"v[áa]lida?\s+at[eé]\s+(\d{2}/\d{2}/\d{4})",
    r"expira[çc][aã]o[:\s]+(\d{2}/\d{2}/\d{4})",
    # CND Federal usa formato "dd/mm/aaaa"
    r"v[áa]lid[ao]?\s+at[eé]\s+(\d{2}/\d{2}/\d{4})",
    # FGTS: "período de validade: DD/MM/AAAA a DD/MM/AAAA" — pega a segunda data
    r"at[eé]\s+(\d{2}/\d{2}/\d{4})",
]


def extrair_data_validade(pdf_bytes: bytes) -> date | None:
    """
    Tenta extrair a data de validade de um PDF de certidão.
    Retorna date ou None se não encontrar.
    """
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            texto = "\n".join(
                (page.extract_text() or "") for page in pdf.pages
            )
    except Exception as e:
        logger.warning("Erro ao ler PDF: %s", e)
        return None

    for padrao in _PADROES_DATA:
        matches = re.findall(padrao, texto, re.IGNORECASE)
        if matches:
            # Pega a última ocorrência (geralmente é a data de validade)
            data_str = matches[-1]
            try:
                dia, mes, ano = data_str.split("/")
                return date(int(ano), int(mes), int(dia))
            except ValueError:
                continue
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Classificação de status
# ──────────────────────────────────────────────────────────────────────────────

def classificar_status(data_validade: date) -> tuple[str, int]:
    """Retorna (status_label, dias_restantes)."""
    hoje = date.today()
    dias = (data_validade - hoje).days
    if dias < 0:
        return "Vencida", dias
    elif dias <= 7:
        return "Vence em 7 dias", dias
    elif dias <= 15:
        return "Vence em 15 dias", dias
    elif dias <= 30:
        return "Vence em 30 dias", dias
    else:
        return "Regular", dias


def resumo_alertas(certidoes: list) -> dict:
    """
    Dado o resultado de db.listar_certidoes(), retorna contagens por categoria.
    """
    hoje = date.today()
    vencidas = a7 = a15 = a30 = regulares = 0
    for emp in certidoes:
        for cert in emp.get("certidoes", []):
            try:
                val = date.fromisoformat(cert["data_validade"])
                dias = (val - hoje).days
                if dias < 0:
                    vencidas += 1
                elif dias <= 7:
                    a7 += 1
                elif dias <= 15:
                    a15 += 1
                elif dias <= 30:
                    a30 += 1
                else:
                    regulares += 1
            except Exception:
                pass
    return {
        "vencidas": vencidas,
        "a7": a7,
        "a15": a15,
        "a30": a30,
        "regulares": regulares,
    }
