import os
from dotenv import load_dotenv
import logging

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Configurações de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configurações do Selenium
CHROME_OPTIONS = {
    "headless": True,
    "no_sandbox": True,
    "disable_dev_shm": True,
    "window_size": "1920,1080"
}

# Configurações da API
API_KEY = os.getenv("API_KEY")
API_BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"

# Tipos de verificação
TIPOS_VERIFICACAO = {
    'CADIN': 'Cadastro de Inadimplentes',
    'CFIL': 'Cadastro de Fornecedores Impedidos de Licitar',
    'CEIS': 'Cadastro de Empresas Inidôneas e Suspensas',
    'CNEP': 'Cadastro Nacional de Empresas Punidas'
}

# Configurações de cache
CACHE_TTL = 3600  # 1 hora em segundos 