import sys
import types

mock_module = types.ModuleType('openpilot.common.params_pyx')
class _Params:  # pragma: no cover
    pass
mock_module.Params = _Params
mock_module.ParamKeyFlag = object
mock_module.ParamKeyType = object
mock_module.UnknownKeyName = Exception
sys.modules.setdefault('openpilot.common.params_pyx', mock_module)
