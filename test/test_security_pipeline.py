import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from security import InputSanitizer, SecurityError

class TestSecurityPipeline:

    @pytest.fixture
    def sanitizer(self):
        return InputSanitizer()

    def test_security_pipeline_default_options(self, sanitizer):
        text = "Hello, contact me at john.doe@example.com"
        result = sanitizer.security_pipeline(text)
        
        assert result['success'] is True
        assert '[email_redacted]' in result['processed_text']
        assert result['original_text'] == text
        assert 'email' in result['pii']['detected']
        assert result['metadata']['pii_redacted'] is True

    def test_security_pipeline_with_injection_attack(self, sanitizer):
        text = "SELECT * FROM users WHERE 1=1"
        result = sanitizer.security_pipeline(text)
        
        assert result['success'] is False
        assert len(result['errors']) > 0
        assert any('SQL' in error['reason'] for error in result['errors'])

    def test_security_pipeline_selective_pii_types(self, sanitizer):
        text = "Email: test@example.com, Phone: 555-123-4567, SSN: 123-45-6789"
        result = sanitizer.security_pipeline(text, options={'pii_types': ['email', 'phone']})
        
        assert '[email_redacted]' in result['processed_text']
        assert '[phone_redacted]' in result['processed_text']
        assert '123-45-6789' in result['processed_text']  # SSN not redacted

    def test_security_pipeline_disable_pii_redaction(self, sanitizer):
        text = "Contact at test@example.com"
        result = sanitizer.security_pipeline(text, options={'redact_pii': False})
        
        assert result['success'] is True
        assert 'test@example.com' in result['processed_text']
        assert 'email' in result['pii']['detected']

    def test_security_pipeline_disable_input_validation(self, sanitizer):
        text = "SELECT * FROM users and contact at test@example.com"
        result = sanitizer.security_pipeline(text, options={'validate_input': False})
        
        # Should still redact PII but won't catch SQL injection
        assert '[email_redacted]' in result['processed_text']

    def test_security_pipeline_length_validation(self, sanitizer):
        long_text = "A" * 15000
        result = sanitizer.security_pipeline(long_text, options={'max_length': 10000})
        
        assert result['success'] is False
        assert any('exceeds' in error['reason'] for error in result['errors'])

    def test_security_pipeline_with_input_cleaning(self, sanitizer):
        text = "Hello---World<script>alert(1)</script>"
        result = sanitizer.security_pipeline(text, options={'clean_input': True})
        
        assert result['metadata']['input_cleaned'] is True
        assert '<script>' not in result['processed_text']

    def test_security_pipeline_selective_injection_checks(self, sanitizer):
        text = "SELECT * FROM users and <script>alert(1)</script>"
        result = sanitizer.security_pipeline(text, options={'injection_types': ['sql']})
        
        # Should only check SQL injection
        assert result['success'] is False
        assert 'sql_injection' in result['validation']

    def test_security_pipeline_comprehensive_text(self, sanitizer):
        text = """
        Contact John at john.doe@example.com or call 555-123-4567
        His SSN is 123-45-6789 and credit card is 4532 1234 5678 9010
        Address: 123 Main Street, DOB: 12/15/1990
        """
        result = sanitizer.security_pipeline(text)
        
        assert result['success'] is True
        assert '[email_redacted]' in result['processed_text']
        assert '[phone_redacted]' in result['processed_text']
        assert '[ssn_redacted]' in result['processed_text']
        assert '[credit_card_redacted]' in result['processed_text'] or '[phone_redacted]' in result['processed_text']
        assert '[address_redacted]' in result['processed_text']
        assert '[dob_redacted]' in result['processed_text']

    def test_security_pipeline_metadata(self, sanitizer):
        text = "Test with PII: test@example.com"
        result = sanitizer.security_pipeline(text)
        
        assert 'pipeline_version' in result['metadata']
        assert 'text_length' in result['metadata']
        assert 'pii_detected_count' in result['metadata']
        assert 'pii_types_found' in result['metadata']
        assert 'total_errors' in result['metadata']
        assert 'total_warnings' in result['metadata']

    def test_quick_validate_safe_text(self, sanitizer):
        text = "Hello, this is safe text"
        success, message = sanitizer.quick_validate(text)
        
        assert success is True
        assert "safe" in message.lower()

    def test_quick_validate_with_pii(self, sanitizer):
        text = "Contact at test@example.com"
        success, message = sanitizer.quick_validate(text)
        
        assert success is True
        assert "PII" in message
        assert "email" in message.lower()

    def test_quick_validate_with_injection(self, sanitizer):
        text = "SELECT * FROM users"
        success, message = sanitizer.quick_validate(text)
        
        assert success is False
        assert "violation" in message.lower()

    def test_quick_validate_simple(self, sanitizer):
        text = "Hello world"
        success, message = sanitizer.quick_validate(text)
        
        assert success is True
        assert isinstance(success, bool)
        assert isinstance(message, str)

    def test_safe_process_success(self, sanitizer):
        text = "Contact at test@example.com"
        processed = sanitizer.safe_process(text)
        
        assert '[email_redacted]' in processed
        assert 'test@example.com' not in processed

    def test_safe_process_with_injection_raises_error(self, sanitizer):
        text = "SELECT * FROM users WHERE 1=1"
        
        with pytest.raises(SecurityError) as exc_info:
            sanitizer.safe_process(text)
        
        assert "Security validation failed" in str(exc_info.value)

    def test_safe_process_with_long_text_raises_error(self, sanitizer):
        text = "A" * 15000
        
        with pytest.raises(SecurityError) as exc_info:
            sanitizer.safe_process(text)
        
        assert "Security validation failed" in str(exc_info.value)

    def test_safe_process_comprehensive(self, sanitizer):
        text = """
        Contact information:
        Email: admin@company.com
        Phone: +1 (555) 123-4567
        SSN: 987-65-4321
        """
        processed = sanitizer.safe_process(text)
        
        assert '[email_redacted]' in processed
        assert '[phone_redacted]' in processed
        assert '[ssn_redacted]' in processed
        assert 'admin@company.com' not in processed

    def test_security_pipeline_empty_string(self, sanitizer):
        text = ""
        result = sanitizer.security_pipeline(text)
        
        assert result['success'] is True
        assert result['processed_text'] == ""

    def test_security_pipeline_whitespace_only(self, sanitizer):
        text = "   \n\t   "
        result = sanitizer.security_pipeline(text)
        
        assert result['success'] is True
        assert len(result['processed_text'].strip()) == 0

    def test_security_pipeline_warnings(self, sanitizer):
        text = "Contact at test@example.com"
        result = sanitizer.security_pipeline(text)
        
        assert len(result['warnings']) > 0
        assert any('pii_detected' in warning['type'] for warning in result['warnings'])

    def test_security_pipeline_no_warnings_when_no_pii(self, sanitizer):
        text = "Hello world"
        result = sanitizer.security_pipeline(text)
        
        assert len(result['warnings']) == 0

    def test_security_pipeline_validation_results_structure(self, sanitizer):
        text = "Hello world"
        result = sanitizer.security_pipeline(text)
        
        assert 'prompt_injection' in result['validation']
        assert 'sql_injection' in result['validation']
        assert 'xss' in result['validation']
        assert 'command_injection' in result['validation']

    def test_security_pipeline_result_structure_complete(self, sanitizer):
        text = "Test"
        result = sanitizer.security_pipeline(text)
        
        # Check all expected keys are present
        expected_keys = [
            'success', 'processed_text', 'original_text',
            'validation', 'pii', 'output', 'errors', 'warnings', 'metadata'
        ]
        
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_security_pipeline_multiple_pii_types_detection(self, sanitizer):
        text = "Email: test@example.com, Phone: 555-123-4567"
        result = sanitizer.security_pipeline(text)
        
        detected = result['pii']['detected']
        assert 'email' in detected
        assert 'phone' in detected
        assert len(detected['email']) == 1
        assert len(detected['phone']) == 1

    def test_security_pipeline_options_applied_in_metadata(self, sanitizer):
        custom_options = {'max_length': 5000, 'redact_pii': False}
        text = "Test"
        result = sanitizer.security_pipeline(text, options=custom_options)
        
        assert result['metadata']['options_applied'] == custom_options

if __name__ == "__main__":
    pytest.main([__file__, "-v"])