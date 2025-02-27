from selenium.webdriver.chrome.options import Options

def get_chrome_options():
    """Retorna opções padrão do Chrome para web scraping"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    return options 