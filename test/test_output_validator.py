import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from security import InputSanitizer

class TestOutputValidator:

    @pytest.fixture
    def sanitizer(self):
        return InputSanitizer()

    def test_validate_output_redacts_pii_by_default(self, sanitizer):
        output = "Contact me at john.doe@example.com"
        is_valid, sanitized, error = sanitizer.validate_output(output)
        assert is_valid is True
        assert error is None
        assert "[email_redacted]" in sanitized
        assert "john.doe@example.com" not in sanitized

    def test_validate_output_with_specific_pii_types(self, sanitizer):
        output = "Email: john.doe@example.com, Phone: 555-123-4567"
        is_valid, sanitized, error = sanitizer.validate_output(
            output, 
            options={'pii_types': ['email']}
        )
        assert is_valid is True
        assert "[email_redacted]" in sanitized
        assert "555-123-4567" in sanitized

    def test_validate_output_can_disable_pii_redaction(self, sanitizer):
        output = "Email: john.doe@example.com"
        is_valid, sanitized, error = sanitizer.validate_output(
            output, 
            options={'redact_pii': False}
        )
        assert is_valid is True
        assert "john.doe@example.com" in sanitized

    def test_validate_output_enforces_max_length(self, sanitizer):
        long_output = "A" * 15000
        is_valid, sanitized, error = sanitizer.validate_output(
            long_output, 
            options={'max_length': 10000}
        )
        assert is_valid is False
        assert error is not None
        assert "exceeds maximum length" in error

    def test_validate_output_custom_max_length(self, sanitizer):
        output = "Hello world"
        is_valid, sanitized, error = sanitizer.validate_output(
            output, 
            options={'max_length': 5}
        )
        assert is_valid is False

    def test_validate_output_safe_output_passes(self, sanitizer):
        output = "Hello, this is safe output with no sensitive information"
        is_valid, sanitized, error = sanitizer.validate_output(output)
        assert is_valid is True
        assert error is None
        assert sanitized == output

    def test_process_output_returns_sanitized_text(self, sanitizer):
        output = "Contact at test@example.com"
        is_valid, sanitized, error = sanitizer.validate_output(output)
        assert "[email_redacted]" in sanitized
        assert "test@example.com" not in sanitized

    def test_process_output_raises_on_invalid(self, sanitizer):
        long_output = "A" * 15000
        is_valid, sanitized, error = sanitizer.validate_output(long_output, options={'max_length': 10000})
        assert is_valid is False
        assert error is not None

    def test_process_output_empty_string(self, sanitizer):
        is_valid, sanitized, error = sanitizer.validate_output("")
        assert is_valid is True
        assert sanitized == ""

    def test_validate_output_whitespace_only(self, sanitizer):
        result = sanitizer.validate_output("   \n\t   ")
        assert result[0] is True

    def test_output_validator_handles_special_characters(self, sanitizer):
        output = "Contact: special+user@example.com"
        is_valid, sanitized, error = sanitizer.validate_output(output)
        assert is_valid is True
        assert "[email_redacted]" in sanitized

if __name__ == "__main__":
    pytest.main([__file__, "-v"])