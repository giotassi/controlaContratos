import logging
import os
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

from services.database import DatabaseService

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class TransparenciaService:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        if not self.api_key:
            try:
                self.api_key = st.secrets["transparencia"]["api_key"]
            except Exception:
                pass
        self.base_url = "https://api.portaldatransparencia.gov.br/api-de-dados"
        self.headers = {
            "Accept": "application/json",
            "chave-api-dados": self.api_key or "",
        }
        self.db = DatabaseService()

    def testar_api(self):
        try:
            response = requests.get(
                f"{self.base_url}/ceis",
                headers=self.headers,
                params={"pagina": 1, "codigoSancionado": "00000000000191"},
                timeout=15,
            )
            return response.status_code == 200
        except Exception:
            return False

    def consultar(self, cnpj: str, razao_social: str = None):
        if not self.api_key:
            return {
                sistema: {"status": None, "observacoes": "API não configurada"}
                for sistema in ("ceis", "cnep")
            }

        logging.info("Iniciando consulta Portal da Transparência para CNPJ %s", cnpj)
        empresa_id = self._garantir_empresa(cnpj, razao_social)
        resultados = {}
        sistemas = ("ceis", "cnep")

        for sistema in sistemas:
            try:
                response = self._consultar_sistema(sistema, cnpj)
                if response.status_code != 200:
                    resultados[sistema] = {
                        "status": False,
                        "observacoes": f"Erro HTTP {response.status_code}",
                    }
                    continue

                dados = response.json() if response.text.strip() else []
                status = len(dados) == 0
                observacoes = getattr(self, f"_formatar_{sistema}")(dados) if dados else "Regular"
                self._salvar_monitoramento(empresa_id, sistema, status, observacoes)
                resultados[sistema] = {"status": status, "observacoes": observacoes}
            except Exception as e:
                logging.error("Erro ao consultar %s: %s", sistema, e)
                resultados[sistema] = {
                    "status": False,
                    "observacoes": f"Erro na consulta: {e}",
                }

        if empresa_id is not None:
            resultados["empresa_id"] = empresa_id
        return resultados

    def _garantir_empresa(self, cnpj: str, razao_social: str = None) -> int | None:
        try:
            empresa = (
                self.db.supabase.table("empresas")
                .select("*")
                .eq("cnpj", cnpj)
                .execute()
            )
            if not empresa.data:
                empresa = (
                    self.db.supabase.table("empresas")
                    .insert({
                        "cnpj": cnpj,
                        "razao_social": razao_social or "Empresa em Consulta",
                        "objeto_contrato": "Consulta Individual",
                    })
                    .execute()
                )
            elif razao_social and empresa.data[0]["razao_social"] != razao_social:
                (
                    self.db.supabase.table("empresas")
                    .update({"razao_social": razao_social})
                    .eq("id", empresa.data[0]["id"])
                    .execute()
                )
            return empresa.data[0]["id"] if empresa.data else None
        except Exception as e:
            logging.error("Erro ao salvar/obter empresa no Supabase: %s", e)
            return None

    def _salvar_monitoramento(self, empresa_id: int | None, sistema: str, status: bool, observacoes: str):
        if empresa_id is None:
            return
        try:
            self.db.supabase.table("monitoramentos").insert({
                "empresa_id": empresa_id,
                "tipo_verificacao": sistema.upper(),
                "status": status,
                "observacoes": observacoes,
                "data_verificacao": datetime.now().isoformat(),
            }).execute()
        except Exception as e:
            logging.error("Erro ao salvar monitoramento %s: %s", sistema, e)

    def _consultar_sistema(self, sistema, cnpj):
        try:
            return requests.get(
                f"{self.base_url}/{sistema}",
                headers=self.headers,
                params={"pagina": 1, "codigoSancionado": cnpj},
                timeout=15,
            )
        except Exception as e:
            logging.error("Erro ao consultar %s: %s", sistema, e)
            raise

    def _formatar_ceis(self, dados):
        registros = []
        for item in dados:
            registros.append(
                f"Sanção: {item.get('descricaoResumida', 'N/A')}\n"
                f"Órgão: {item.get('orgaoSancionador', {}).get('nome', 'N/A')}\n"
                f"Início: {self._formatar_data(item.get('dataInicioSancao'))}\n"
                f"Fim: {self._formatar_data(item.get('dataFimSancao'))}"
            )
        return "\n\n".join(registros) if registros else "Registros encontrados no CEIS"

    def _formatar_cnep(self, dados):
        registros = []
        for item in dados:
            registros.append(
                f"Sanção: {item.get('tipoSancao', 'N/A')}\n"
                f"Órgão: {item.get('orgaoSancionador', {}).get('nome', 'N/A')}\n"
                f"Valor Multa: R$ {item.get('valorMulta', 'N/A')}"
            )
        return "\n\n".join(registros) if registros else "Regular"

    def _formatar_data(self, data_str):
        if not data_str:
            return "N/A"
        try:
            return datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return data_str
