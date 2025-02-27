import pytest
from services.monitor import MonitorService
from unittest.mock import Mock, patch

@pytest.fixture
def monitor_service():
    return MonitorService()

def test_verificar_empresa_cnpj_invalido(monitor_service):
    resultado = monitor_service.verificar_empresa('11111111111111')
    assert resultado.get('error') == 'CNPJ inválido'

@patch('services.cadin.CADINService.consultar')
def test_verificar_empresa_sucesso(mock_cadin, monitor_service):
    # Mock do resultado do CADIN
    mock_cadin.return_value = {
        'cadin': {'status': True, 'observacoes': 'Regular'},
        'cfil': {'status': True, 'observacoes': 'Regular'}
    }
    
    resultado = monitor_service.verificar_empresa('11222333000181')
    assert resultado['cadin']['status'] == True
    assert resultado['cfil']['status'] == True 