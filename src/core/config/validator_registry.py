"""Registry for executing configured validators."""

from typing import Any, Dict, List

from .exceptions import ConfigValidationError
from .validator_base import Validator


class ValidatorRegistry:
    """Register and run validators by field name."""

    def __init__(self):
        self._validators: Dict[str, List[Validator]] = {}

    def register(self, field_name: str, validator: Validator) -> None:
        if field_name not in self._validators:
            self._validators[field_name] = []
        self._validators[field_name].append(validator)

    def validate_field(self, field_name: str, value: Any) -> List[str]:
        errors = []
        validators = self._validators.get(field_name, [])

        for validator in validators:
            try:
                validator.validate(field_name, value)
            except ConfigValidationError as e:
                errors.append(str(e))

        return errors

    def validate_all(self, config: Dict[str, Any]) -> Dict[str, List[str]]:
        all_errors = {}

        for field_name in self._validators.keys():
            value = config.get(field_name)
            errors = self.validate_field(field_name, value)
            if errors:
                all_errors[field_name] = errors

        return all_errors

    def clear(self) -> None:
        self._validators.clear()

    def get_validators(self, field_name: str) -> List[Validator]:
        return self._validators.get(field_name, []).copy()
