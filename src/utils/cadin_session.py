"""
Gerencia sessão autenticada do portal CADIN/RS.

Estratégia:
  1. O usuário faz login no CADIN no seu Chrome habitual (manualmente).
  2. confirmar_login() lê os cookies do Chrome com browser_cookie3
     e os injeta num Selenium headless para as consultas.

Nenhum browser fake é aberto para o login.  O Gov.Br e o CADIN veem
apenas o Chrome real do usuário.
"""
import logging
import time
import threading

from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)

CADIN_URL = "https://cadin.sefaz.rs.gov.br/"

_driver = None
_lock   = threading.Lock()


# ──────────────────────────────────────────────────────────────────────────────
# Estado da sessão
# ──────────────────────────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    global _driver
    if _driver is None:
        return False
    try:
        _ = _driver.current_url
        btn = _driver.find_element(
            By.XPATH, "//button[contains(text(),'Consultar')]"
        )
        return btn.get_attribute("disabled") is None
    except Exception:
        _driver = None
        return False


def has_valid_session() -> bool:
    return is_authenticated()


def fechar():
    global _driver
    with _lock:
        if _driver:
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None
    logger.info("Sessão CADIN encerrada.")


def invalidar_sessao():
    fechar()


# ──────────────────────────────────────────────────────────────────────────────
# Confirmar login — extrai cookies do Chrome real
# ──────────────────────────────────────────────────────────────────────────────

def confirmar_login() -> bool:
    """
    Lê os cookies de sessão do CADIN do Chrome instalado no sistema
    (browser_cookie3 + DPAPI) e os injeta num Selenium headless.
    O Chrome do usuário deve estar aberto e logado no CADIN.
    """
    global _driver

    try:
        import browser_cookie3
        cj = browser_cookie3.chrome(domain_name='sefaz.rs.gov.br')
        cookies = list(cj)
    except Exception as e:
        logger.error("Falha ao ler cookies do Chrome: %s", e)
        return False

    if not cookies:
        logger.warning("Nenhum cookie de sefaz.rs.gov.br encontrado no Chrome.")
        return False

    logger.info("Cookies encontrados: %d — injetando em sessão Selenium.",
                len(cookies))

    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from utils.selenium_utils import get_chrome_options

    options = get_chrome_options()
    options.add_argument("--window-size=1280,900")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    try:
        # Precisa navegar para o domínio antes de definir cookies
        driver.get(CADIN_URL)
        time.sleep(3)

        driver.delete_all_cookies()
        for c in cookies:
            try:
                cookie_dict = {
                    "name":   c.name,
                    "value":  c.value,
                    "domain": "cadin.sefaz.rs.gov.br",
                    "path":   getattr(c, "path", "/") or "/",
                    "secure": bool(getattr(c, "secure", False)),
                }
                driver.add_cookie(cookie_dict)
            except Exception:
                pass

        driver.refresh()
        time.sleep(4)

        btn = driver.find_element(
            By.XPATH, "//button[contains(text(),'Consultar')]"
        )
        if btn.get_attribute("disabled") is None:
            with _lock:
                _driver = driver
            logger.info("Sessão CADIN restaurada via cookies — driver salvo.")
            return True

        logger.warning("Botão Consultar ainda desabilitado após injeção de cookies.")
        driver.quit()
        return False

    except Exception as e:
        logger.error("Erro ao verificar sessão CADIN: %s", e)
        try:
            driver.quit()
        except Exception:
            pass
        return False


# mantém compat
def login_manual(timeout_segundos: int = 180) -> bool:
    return confirmar_login()


def abrir_browser() -> bool:
    """Não faz mais nada — o usuário usa seu próprio Chrome."""
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Consulta CADIN
# ──────────────────────────────────────────────────────────────────────────────

def consultar_cnpj(cnpj: str) -> dict:
    global _driver

    if not is_authenticated():
        return {
            "status": None,
            "observacoes": "CADIN: sessão não autenticada. "
                           "Clique em 'Autenticar CADIN' antes de consultar.",
        }

    with _lock:
        driver = _driver

    try:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        if "cadin.sefaz.rs.gov.br" not in driver.current_url.lower():
            driver.get(CADIN_URL)
            time.sleep(3)

        wait = WebDriverWait(driver, 15)

        campo = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Digite o CPF ou CNPJ']")
        ))
        campo.clear()
        campo.send_keys(cnpj)
        time.sleep(1)

        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Consultar') and not(@disabled)]")
        ))
        btn.click()
        time.sleep(5)

        resultado = _parsear_resultado(driver)

        driver.get(CADIN_URL)
        time.sleep(2)

        return resultado

    except Exception as e:
        logger.error("Erro ao consultar CADIN (%s): %s", cnpj, e, exc_info=True)
        try:
            driver.get(CADIN_URL)
            time.sleep(2)
        except Exception:
            with _lock:
                _driver = None
        return {"status": False, "observacoes": f"Erro na consulta CADIN: {e}"}


def _parsear_resultado(driver) -> dict:
    corpo = driver.find_element(By.TAG_NAME, "body").text.upper()

    REGULAR = [
        "NÃO FORAM ENCONTRADOS REGISTROS",
        "NÃO INSCRITO",
        "NENHUM REGISTRO",
        "SEM PENDÊNCIAS",
        "NOT FOUND",
        "NENHUM RESULTADO",
    ]
    if any(p in corpo for p in REGULAR):
        return {"status": True, "observacoes": "Regular — não inscrito no CADIN/RS"}

    try:
        el = driver.find_element(
            By.XPATH,
            "//*[contains(@class,'resultado') or contains(@class,'result') "
            "or contains(@class,'alert') or contains(@id,'resultado')]",
        )
        obs = el.text.strip()
    except Exception:
        obs = "Inscrito no CADIN/RS"

    return {"status": False, "observacoes": obs or "Inscrito no CADIN/RS"}
