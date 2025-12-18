"""Schema Validator Guard.

Validates LLM outputs against JSON schemas.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    ValidationError = Exception  # Fallback

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA_DIR = Path("ops/schemas")


@dataclass
class ValidationResult:
    """Result of schema validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    schema_name: str | None
    metadata: dict[str, Any]


class SchemaValidator:
    """Validates data against JSON schemas."""

    def __init__(self, schema_dir: Path | None = None):
        self.schema_dir = schema_dir or DEFAULT_SCHEMA_DIR
        self.schemas: dict[str, dict] = {}
        self.validators: dict[str, Any] = {}

    def load_schema(
        self, schema_name: str, schema_path: Path | None = None
    ) -> dict | None:
        """Load a JSON schema.

        Args:
            schema_name: Name/identifier for the schema
            schema_path: Optional explicit path to schema file

        Returns:
            Schema dict if successful, None otherwise
        """
        if schema_name in self.schemas:
            return self.schemas[schema_name]

        if schema_path is None:
            schema_path = self.schema_dir / f"{schema_name}.json"

        if not schema_path.exists():
            logger.warning(f"Schema file not found: {schema_path}")
            return None

        try:
            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)

            self.schemas[schema_name] = schema

            if JSONSCHEMA_AVAILABLE:
                self.validators[schema_name] = Draft7Validator(schema)

            logger.info(f"Loaded schema '{schema_name}' from {schema_path}")
            return schema

        except Exception as e:
            logger.exception(f"Error loading schema: {e}")
            return None

    def validate_data(
        self,
        data: Any,
        schema_name: str | None = None,
        schema: dict | None = None,
    ) -> ValidationResult:
        """Validate data against a schema.

        Args:
            data: Data to validate
            schema_name: Name of loaded schema
            schema: Explicit schema dict (alternative to schema_name)

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        metadata = {}

        if not JSONSCHEMA_AVAILABLE:
            warnings.append(
                "jsonschema library not installed, validation skipped"
            )
            return ValidationResult(
                valid=True,
                errors=errors,
                warnings=warnings,
                schema_name=schema_name,
                metadata=metadata,
            )

        # Get schema
        if schema_name:
            if schema_name not in self.schemas:
                self.load_schema(schema_name)
            schema = self.schemas.get(schema_name)
            validator = self.validators.get(schema_name)
        elif schema:
            validator = Draft7Validator(schema)
        else:
            errors.append("No schema provided for validation")
            return ValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                schema_name=None,
                metadata=metadata,
            )

        if not schema or not validator:
            errors.append(f"Schema '{schema_name}' not available")
            return ValidationResult(
                valid=False,
                errors=errors,
                warnings=warnings,
                schema_name=schema_name,
                metadata=metadata,
            )

        # Perform validation
        try:
            # Collect all validation errors
            validation_errors = list(validator.iter_errors(data))

            for error in validation_errors:
                path = (
                    ".".join(str(p) for p in error.path)
                    if error.path
                    else "root"
                )
                errors.append(f"{path}: {error.message}")

            metadata["error_count"] = len(validation_errors)
            valid = len(validation_errors) == 0

        except Exception as e:
            errors.append(f"Validation exception: {str(e)}")
            valid = False

        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            schema_name=schema_name,
            metadata=metadata,
        )

    def validate_llm_output(
        self, output: dict, schema_name: str = "llm_output"
    ) -> ValidationResult:
        """Validate LLM output against standard schema.

        Args:
            output: LLM output dictionary
            schema_name: Schema to validate against

        Returns:
            ValidationResult
        """
        return self.validate_data(output, schema_name=schema_name)

    def validate_required_fields(
        self, data: dict, required_fields: list[str]
    ) -> ValidationResult:
        """Simple validation for required fields.

        Args:
            data: Data dictionary
            required_fields: List of required field names

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif data[field] is None:
                warnings.append(f"Field '{field}' is None")
            elif isinstance(data[field], str) and not data[field].strip():
                warnings.append(f"Field '{field}' is empty string")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            schema_name=None,
            metadata={"required_fields": required_fields},
        )


# Global validator instance
_validator: SchemaValidator | None = None


def get_validator() -> SchemaValidator:
    """Get or create global schema validator.

    Returns:
        SchemaValidator instance
    """
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator


def validate(output: dict, schema_name: str | None = None) -> bool:
    """Legacy function for backward compatibility.

    Args:
        output: Output to validate
        schema_name: Optional schema name

    Returns:
        True if valid, False otherwise
    """
    validator = get_validator()

    if schema_name:
        result = validator.validate_llm_output(output, schema_name=schema_name)
    else:
        # Basic validation: check for common required fields
        required = (
            ["text"]
            if "text" in output
            else ["content"] if "content" in output else ["response"]
        )
        result = validator.validate_required_fields(output, required)

    if not result.valid:
        logger.warning(f"Validation failed: {len(result.errors)} errors")

    return result.valid
