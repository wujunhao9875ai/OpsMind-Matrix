"""Compatibility shim for langchain_core.pydantic_v1"""
import sys
import types
from functools import wraps

# Create a fake langchain_core.pydantic_v1 module
from pydantic import (
    BaseModel, Field, SecretStr, validator,
    ValidationError, Extra, PrivateAttr, StrictBool, StrictFloat,
    StrictInt, StrictStr,
)

# Wrapped root_validator that adds skip_on_failure=True for pydantic v2 compat
from pydantic import root_validator as _root_validator

@wraps(_root_validator)
def root_validator(*args, **kwargs):
    if not args and 'skip_on_failure' not in kwargs and 'pre' not in kwargs:
        kwargs['skip_on_failure'] = True
    elif not args and 'skip_on_failure' not in kwargs and not kwargs.get('pre', False):
        kwargs['skip_on_failure'] = True
    return _root_validator(*args, **kwargs)

_pydantic_v1 = types.ModuleType("langchain_core.pydantic_v1")
_pydantic_v1.BaseModel = BaseModel
_pydantic_v1.Field = Field
_pydantic_v1.SecretStr = SecretStr
_pydantic_v1.root_validator = root_validator
_pydantic_v1.validator = validator
_pydantic_v1.ValidationError = ValidationError
_pydantic_v1.Extra = Extra
_pydantic_v1.PrivateAttr = PrivateAttr
_pydantic_v1.StrictBool = StrictBool
_pydantic_v1.StrictFloat = StrictFloat
_pydantic_v1.StrictInt = StrictInt
_pydantic_v1.StrictStr = StrictStr

sys.modules["langchain_core.pydantic_v1"] = _pydantic_v1