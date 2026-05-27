import pytest
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def monitor_service():
    with patch('services.database.DatabaseService.__init__', return_value=None), \
         patch('services.cadin.CADINService.__init__', return_value=None), \
         patch('services.transparencia.TransparenciaService.__init__', return_value=None):
        from services.monitor import MonitorService
        service = MonitorService.__new__(MonitorService)
        service.db = MagicMock()
        service.cadin = MagicMock()
        service.transparencia = MagicMock()
        return service


def test_verificar_empresa_cnpj_invalido(monitor_service):
    resultado = monitor_service.verificar_empresa('11111111111111')
    assert resultado.get('error') == 'CNPJ inválido'


def test_verificar_empresa_sucesso(monitor_service):
    monitor_service.transparencia.consultar.return_value = {
        'ceis': {'status': True, 'observacoes': 'Regular'},
        'cnep': {'status': True, 'observacoes': 'Regular'},
        'empresa_id': 1,
    }
    monitor_service.cadin.consultar.return_value = {
        'cadin': {'status': True, 'observacoes': 'Regular'},
        'cfil': {'status': True, 'observacoes': 'Regular'},
    }

    resultado = monitor_service.verificar_empresa('11222333000181')
    assert resultado['cadin']['status'] == True
    assert resultado['cfil']['status'] == True
    assert resultado['status'] == True 
