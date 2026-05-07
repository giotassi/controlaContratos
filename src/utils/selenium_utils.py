import platform
import shutil
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


def get_chrome_options() -> Options:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    # Linux (Streamlit Cloud): usa o Chromium do sistema
    if platform.system() == "Linux":
        chromium = (
            shutil.which("chromium")
            or shutil.which("chromium-browser")
        )
        if chromium:
            options.binary_location = chromium

    return options


def get_chrome_service() -> Service:
    """Retorna o Service correto para o ambiente atual."""
    if platform.system() == "Linux":
        chromedriver = (
            shutil.which("chromedriver")
            or shutil.which("chromium-driver")
            or shutil.which("chromium.chromedriver")
        )
        if chromedriver:
            return Service(chromedriver)

    from webdriver_manager.chrome import ChromeDriverManager
    return Service(ChromeDriverManager().install())
