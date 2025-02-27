import pytest
from utils.formatters import validate_cnpj, format_cnpj

def test_validate_cnpj():
    # CNPJs válidos
    assert validate_cnpj('11222333000181') == True
    assert validate_cnpj('11.222.333/0001-81') == True
    
    # CNPJs inválidos
    assert validate_cnpj('11111111111111') == False  # Dígitos iguais
    assert validate_cnpj('11222333000182') == False  # Dígito verificador errado
    assert validate_cnpj('1122233300018') == False   # Tamanho errado

def test_format_cnpj():
    assert format_cnpj('11222333000181') == '11.222.333/0001-81'
    assert format_cnpj('11.222.333/0001-81') == '11.222.333/0001-81' 