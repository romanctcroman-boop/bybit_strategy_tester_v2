"""
Тест совместимости двух версий DataManager

Проверяет что:
1. backend.core.data_manager.DataManager (новая версия)
2. backend.services.data_manager.DataManager (старая DEPRECATED версия)

Имеют одинаковый публичный API для миграции без поломки существующего кода.
"""

import pytest
import warnings
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime

# Import both versions
from backend.core.data_manager import DataManager as CoreDataManager
from backend.services.data_manager import DataManager as ServicesDataManager


def test_both_datamanagers_exist():
    """Проверка что оба DataManager импортируются"""
    assert CoreDataManager is not None
    assert ServicesDataManager is not None


def test_services_datamanager_shows_deprecation_warning():
    """Проверка что старый DataManager показывает deprecation warning"""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # Re-import to trigger warning
        import importlib
        import backend.services.data_manager
        importlib.reload(backend.services.data_manager)
        
        # Check that warning was issued
        assert len(w) > 0
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)
        assert any("DEPRECATED" in str(warning.message) for warning in w)


def test_core_datamanager_has_required_methods():
    """Проверка что новый DataManager имеет все необходимые методы"""
    dm = CoreDataManager(symbol='BTCUSDT')
    
    # Check methods exist
    assert hasattr(dm, 'load_historical')
    assert hasattr(dm, 'get_multi_timeframe')
    assert hasattr(dm, 'update_cache')
    
    # Check callable
    assert callable(dm.load_historical)
    assert callable(dm.get_multi_timeframe)
    assert callable(dm.update_cache)


def test_services_datamanager_has_required_methods():
    """Проверка что старый DataManager имеет все необходимые методы"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        dm = ServicesDataManager(symbol='BTCUSDT', timeframe='15')
        
        # Check methods exist
        assert hasattr(dm, 'load_historical')
        assert hasattr(dm, 'get_multi_timeframe')
        assert hasattr(dm, 'update_cache')
        
        # Check callable
        assert callable(dm.load_historical)
        assert callable(dm.get_multi_timeframe)
        assert callable(dm.update_cache)


def test_both_accept_symbol_parameter():
    """Проверка что оба принимают symbol в конструкторе"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        # Core version
        dm_core = CoreDataManager(symbol='ETHUSDT')
        assert dm_core.symbol == 'ETHUSDT'
        
        # Services version
        dm_services = ServicesDataManager(symbol='ETHUSDT', timeframe='15')
        assert dm_services.symbol == 'ETHUSDT'


def test_load_historical_signature_compatibility():
    """Проверка что load_historical имеет совместимый интерфейс"""
    import inspect
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        # Get signatures
        core_sig = inspect.signature(CoreDataManager.load_historical)
        services_sig = inspect.signature(ServicesDataManager.load_historical)
        
        # Both should accept 'limit' parameter
        assert 'limit' in core_sig.parameters
        assert 'limit' in services_sig.parameters
        
        # Check defaults
        assert core_sig.parameters['limit'].default == 1000
        assert services_sig.parameters['limit'].default == 1000


def test_get_multi_timeframe_signature_compatibility():
    """Проверка что get_multi_timeframe имеет совместимый интерфейс"""
    import inspect
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        # Get signatures
        core_sig = inspect.signature(CoreDataManager.get_multi_timeframe)
        services_sig = inspect.signature(ServicesDataManager.get_multi_timeframe)
        
        # Both should accept 'timeframes' parameter
        assert 'timeframes' in core_sig.parameters
        assert 'timeframes' in services_sig.parameters


def test_both_return_dataframes():
    """Проверка что оба возвращают DataFrame"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        with patch('backend.core.data_manager.HTTP') as mock_http_core:
            # Mock API response
            mock_response = {
                'retCode': 0,
                'result': {
                    'list': [
                        ['1704067200000', '42000', '42100', '41900', '42050', '100', '4205000']
                    ]
                }
            }
            mock_http_core.return_value.get_kline.return_value = mock_response
            
            dm_core = CoreDataManager(symbol='BTCUSDT')
            # Clear cache to force API call
            dm_core.update_cache()
            
            result_core = dm_core.load_historical(limit=10)
            assert isinstance(result_core, pd.DataFrame)


def test_migration_path_documentation():
    """Проверка что документация содержит информацию о миграции"""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        # Check docstring has migration info
        doc = ServicesDataManager.__doc__
        assert 'DEPRECATED' in doc or 'DEPRECATION' in doc
        assert 'backend.core.data_manager' in doc


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
