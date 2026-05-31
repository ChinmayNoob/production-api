import re
import html
from typing import Optional, List, Tuple

try:
    from langsmith import traceable
except ImportError:
    def traceable(func):
        return func

@traceable
class InputSanitizer:

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"new\s+instructions\s*:\s*",
        r"delete\s+all\s+previous\s+instructions",
        r"---\s*end\s+(of)?\s*prompt",
        r"pretend\s+you\s+are",
        r"act\s+as\s+if\s+you\s+are",
        r"bypass\s+(all\s+)?restrictions",
        r"reveals\s+(your|the)\s+(system|instructions|prompt)",
        r"you\s+are\s+now\s+(DAN|jailbroken)",
    ]
    
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|UNION|EXEC|EXECUTE)\b)",
        r"(\-\-|\#|\/\*|\*\/)",
        r"(\bor\s+1\s*=\s*1\b)",
        r"(\band\s+1\s*=\s*1\b)",
        r"(\bor\s+true\b)",
        r"(\band\s+true\b)",
        r"(\bor\s+[0-9]+\s*=\s*[0-9]+\b)",
        r"(\band\s+[0-9]+\s*=\s*[0-9]+\b)",
        r"(\bwaitfor\s+delay\b)",
        r"(\bsleep\s*\()",
        r"(\bpg_sleep\s*\()",
        r"(\bbenchmark\s*\()",
        r"(\bxp_cmdshell\b)",
        r"(\bsp_oacreate\b)",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"<iframe[^>]*>.*?</iframe>",
        r"<object[^>]*>.*?</object>",
        r"<embed[^>]*>.*?</embed>",
        r"<form[^>]*>.*?</form>",
        r"javascript:",
        r"on\w+\s*=",
        r"onerror\s*=",
        r"onload\s*=",
        r"onclick\s*=",
        r"data:text/html",
        r"fromCharCode",
        r"document\.cookie",
        r"document\.location",
        r"window\.location",
        r"eval\s*\(",
        r"innerHTML\s*=",
        r"outerHTML\s*=",
    ]
    
    COMMAND_INJECTION_PATTERNS = [
        r";\s*\w+",
        r"&&\s*\w+",
        r"\|\|\s*\w+",
        r"\|\s*\w+",
        r"`[^`]*`",
        r"\$\([^)]*\)",
        r"\b(curl|wget|nc|netcat|telnet|ssh)\b",
        r"\b(rm|del|mv|cp)\s+-rf\b",
        r"\b(chmod|chown)\s+777\b",
        r"\b(ping|nslookup|dig)\s+",
        r">\s*/dev/",
        r"<\s*/dev/",
    ]

    PII_PATTERNS = {
        'email': [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ],
        'phone': [
            r'\b\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            r'\b\+?[0-9]{1,3}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,6}\b',
        ],
        'ssn': [
            r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b',
            r'\b[0-9]{3}\s+[0-9]{2}\s+[0-9]{4}\b',
        ],
        'credit_card': [
            r'\b[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}[-\s]?[0-9]{4}\b',
            r'\b[0-9]{13,19}\b',
        ],
        'ip_address': [
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
        ],
        'date_of_birth': [
            r'\b(0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])[-/](19|20)\d{2}\b',
            r'\b(19|20)\d{2}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])\b',
        ],
        'address': [
            r'\b\d+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way)\b',
        ],
        'passport': [
            r'\b[A-Z]{2}[0-9]{6,9}\b',
        ],
        'license_plate': [
            r'\b[A-Z]{2,3}[0-9]{2,4}\b',
        ],
    }

    def __init__(self):
        self.prompt_injection_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
        self.sql_injection_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS
        ]
        self.xss_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS
        ]
        self.command_injection_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.COMMAND_INJECTION_PATTERNS
        ]
        self.pii_patterns = {
            'email': [re.compile(p) for p in self.PII_PATTERNS['email']],
            'phone': [re.compile(p) for p in self.PII_PATTERNS['phone']],
            'ssn': [re.compile(p) for p in self.PII_PATTERNS['ssn']],
            'credit_card': [re.compile(p) for p in self.PII_PATTERNS['credit_card']],
            'ip_address': [re.compile(p) for p in self.PII_PATTERNS['ip_address']],
            'date_of_birth': [re.compile(p) for p in self.PII_PATTERNS['date_of_birth']],
            'address': [re.compile(p) for p in self.PII_PATTERNS['address']],
            'passport': [re.compile(p) for p in self.PII_PATTERNS['passport']],
            'license_plate': [re.compile(p) for p in self.PII_PATTERNS['license_plate']],
        }
    
    def check(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check if the input is safe from all injection types"""
        
        for pattern in self.prompt_injection_patterns:
            if pattern.search(text):
                return False, "Blocked: Prompt injection detected"
        
        for pattern in self.sql_injection_patterns:
            if pattern.search(text):
                return False, "Blocked: SQL injection detected"
        
        for pattern in self.xss_patterns:
            if pattern.search(text):
                return False, "Blocked: XSS attack detected"
        
        for pattern in self.command_injection_patterns:
            if pattern.search(text):
                return False, "Blocked: Command injection detected"
        
        return True, None
    
    def check_sql(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check specifically for SQL injection patterns"""
        for pattern in self.sql_injection_patterns:
            if pattern.search(text):
                return False, "Blocked: SQL injection detected"
        return True, None
    
    def check_xss(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check specifically for XSS patterns"""
        for pattern in self.xss_patterns:
            if pattern.search(text):
                return False, "Blocked: XSS attack detected"
        return True, None
    
    def check_command(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check specifically for command injection patterns"""
        for pattern in self.command_injection_patterns:
            if pattern.search(text):
                return False, "Blocked: Command injection detected"
        return True, None
    
    def clean(self, text: str) -> str:
        """Clean the input by removing potential injection patterns"""
        
        text = re.sub(r'[-]{3,}', '', text)
        text = re.sub(r'[=]{3,}', ' ', text)
        text = text.replace('{{', '').replace('}}', '')
        
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<object[^>]*>.*?</object>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<embed[^>]*>.*?</embed>', '', text, flags=re.IGNORECASE)
        
        text = html.escape(text)
        
        return text.strip()
    
    def sanitize_sql(self, text: str) -> str:
        """Sanitize text for safe SQL usage"""
        text = text.replace("'", "''")
        text = text.replace("\\", "\\\\")
        text = re.sub(r'[-]{2,}', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text.strip()
    
    def sanitize_html(self, text: str) -> str:
        """Sanitize text to prevent XSS attacks"""
        text = html.escape(text)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
        return text.strip()
    
    def validate_length(self, text: str, max_length: int = 10000) -> Tuple[bool, Optional[str]]:
        """Validate input length to prevent buffer overflow attacks"""
        if len(text) > max_length:
            return False, f"Blocked: Input exceeds maximum length of {max_length} characters"
        return True, None
    
    def detect_encoding(self, text: str) -> Tuple[bool, Optional[str]]:
        """Detect potentially malicious encoding attempts"""
        import base64
        
        try:
            decoded = base64.b64decode(text).decode('utf-8')
            is_safe, _ = self.check(decoded)
            if not is_safe:
                return False, "Blocked: Malicious base64 encoded content detected"
        except:
            pass
        
        if '%20' in text or '%3C' in text or '%3E' in text:
            return False, "Blocked: URL encoding detected in input"
        
        return True, None
    
    def redact_pii(self, text: str, pii_types: Optional[List[str]] = None) -> str:
        """Redact PII from text with specific patterns replaced by placeholder text"""
        if pii_types is None:
            pii_types = list(self.PII_PATTERNS.keys())
        
        for pii_type in pii_types:
            if pii_type not in self.PII_PATTERNS:
                continue
            
            patterns = self.pii_patterns[pii_type]
            placeholder = self._get_placeholder(pii_type)
            
            for pattern in patterns:
                text = pattern.sub(placeholder, text)
        
        return text
    
    def detect_pii(self, text: str, pii_types: Optional[List[str]] = None) -> dict:
        """Detect PII in text and return information about what was found"""
        if pii_types is None:
            pii_types = list(self.PII_PATTERNS.keys())
        
        detected = {}
        
        for pii_type in pii_types:
            if pii_type not in self.PII_PATTERNS:
                continue
            
            patterns = self.pii_patterns[pii_type]
            matches = []
            
            for pattern in patterns:
                found = pattern.findall(text)
                if found:
                    matches.extend(found)
            
            if matches:
                detected[pii_type] = matches
        
        return detected
    
    def _get_placeholder(self, pii_type: str) -> str:
        """Get placeholder text for a specific PII type"""
        placeholders = {
            'email': '[email_redacted]',
            'phone': '[phone_redacted]',
            'ssn': '[ssn_redacted]',
            'credit_card': '[credit_card_redacted]',
            'ip_address': '[ip_redacted]',
            'date_of_birth': '[dob_redacted]',
            'address': '[address_redacted]',
            'passport': '[passport_redacted]',
            'license_plate': '[license_plate_redacted]',
        }
        return placeholders.get(pii_type, f'[{pii_type}_redacted]')
    
    def validate_output(self, text: str, options: Optional[dict] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Validate and sanitize output text.
        
        Args:
            text: The output text to validate
            options: Dict with validation options:
                - redact_pii: bool (default: True)
                - pii_types: list of PII types to redact (default: all)
                - check_injections: bool (default: True)
                - max_length: int (default: 10000)
        
        Returns:
            Tuple of (is_valid, sanitized_text, error_message)
        """
        if options is None:
            options = {}
        
        redact_pii = options.get('redact_pii', True)
        check_injections = options.get('check_injections', True)
        max_length = options.get('max_length', 10000)
        pii_types = options.get('pii_types', None)
        
        sanitized_text = text
        
        if check_injections:
            is_safe, reason = self.check(text)
            if not is_safe:
                return False, sanitized_text, reason
            
            sanitized_text = self.clean(text)
        
        if redact_pii:
            sanitized_text = self.redact_pii(sanitized_text, pii_types)
        
        is_valid, reason = self.validate_length(sanitized_text, max_length)
        if not is_valid:
            return False, sanitized_text, reason
        
        return True, sanitized_text, None
    
    def security_pipeline(self, text: str, options: Optional[dict] = None) -> dict:
        """
        Unified security pipeline that applies all security checks and transformations.
        
        This is the main API method that combines input validation, PII detection/redaction,
        and output validation into a single, comprehensive security check.
        
        Args:
            text: The text to process through the security pipeline
            options: Dict with security pipeline options:
                - validate_input: bool (default: True) - Check for injection attacks
                - detect_pii: bool (default: True) - Detect PII in text
                - redact_pii: bool (default: True) - Redact detected PII
                - validate_output: bool (default: True) - Validate final output
                - pii_types: list of PII types to process (default: all)
                - injection_types: list of injection types to check (default: all)
                - max_length: int (default: 10000) - Maximum allowed text length
                - clean_input: bool (default: False) - Clean dangerous patterns from input
                - return_details: bool (default: True) - Return detailed security information
        
        Returns:
            Dictionary with comprehensive security results:
            - success: bool - Overall security check result
            - processed_text: str - The processed/validated text
            - original_text: str - The original input text
            - validation: dict - Input validation results
            - pii: dict - PII detection and redaction results
            - output: dict - Output validation results
            - errors: list - Any security violations or errors
            - warnings: list - Any security warnings
            - metadata: dict - Additional security metadata
        
        Example:
            >>> sanitizer = InputSanitizer()
            >>> result = sanitizer.security_pipeline("Contact me at john@example.com")
            >>> print(result['success'])
            True
            >>> print(result['processed_text'])
            'Contact me at [email_redacted]'
            >>> print(result['pii']['detected'])
            {'email': ['john@example.com']}
        """
        if options is None:
            options = {}
        
        # Default pipeline options
        validate_input = options.get('validate_input', True)
        detect_pii = options.get('detect_pii', True)
        redact_pii = options.get('redact_pii', True)
        validate_output = options.get('validate_output', True)
        clean_input = options.get('clean_input', False)
        return_details = options.get('return_details', True)
        
        pii_types = options.get('pii_types', list(self.PII_PATTERNS.keys()))
        injection_types = options.get('injection_types', ['prompt', 'sql', 'xss', 'command'])
        max_length = options.get('max_length', 10000)
        
        # Initialize result structure
        result = {
            'success': True,
            'processed_text': text,
            'original_text': text,
            'validation': {},
            'pii': {},
            'output': {},
            'errors': [],
            'warnings': [],
            'metadata': {
                'pipeline_version': '1.0',
                'options_applied': options,
                'text_length': len(text)
            }
        }
        
        current_text = text
        
        # Step 1: Input Validation (Injection Detection)
        if validate_input:
            validation_results = {}
            
            for injection_type in injection_types:
                if injection_type == 'prompt':
                    is_safe, reason = self.check(current_text)
                    validation_results['prompt_injection'] = {
                        'safe': is_safe,
                        'reason': reason
                    }
                elif injection_type == 'sql':
                    is_safe, reason = self.check_sql(current_text)
                    validation_results['sql_injection'] = {
                        'safe': is_safe,
                        'reason': reason
                    }
                elif injection_type == 'xss':
                    is_safe, reason = self.check_xss(current_text)
                    validation_results['xss'] = {
                        'safe': is_safe,
                        'reason': reason
                    }
                elif injection_type == 'command':
                    is_safe, reason = self.check_command(current_text)
                    validation_results['command_injection'] = {
                        'safe': is_safe,
                        'reason': reason
                    }
            
            # Check if any injection was detected
            for check_name, check_result in validation_results.items():
                if not check_result['safe']:
                    result['success'] = False
                    result['errors'].append({
                        'type': 'injection_detected',
                        'category': check_name,
                        'reason': check_result['reason']
                    })
            
            result['validation'] = validation_results
        
        # Step 2: Input Cleaning (if requested)
        if clean_input:
            current_text = self.clean(current_text)
            result['metadata']['input_cleaned'] = True
        
        # Step 3: PII Detection
        if detect_pii:
            detected_pii = self.detect_pii(current_text, pii_types)
            result['pii']['detected'] = detected_pii
            
            if detected_pii:
                total_pii_count = sum(len(matches) for matches in detected_pii.values())
                result['metadata']['pii_detected_count'] = total_pii_count
                result['metadata']['pii_types_found'] = list(detected_pii.keys())
        else:
            result['pii']['detected'] = {}
        
        # Step 4: PII Redaction
        if redact_pii:
            redacted_text = self.redact_pii(current_text, pii_types)
            current_text = redacted_text
            result['metadata']['pii_redacted'] = True
        
        # Step 5: Length Validation
        is_length_valid, length_reason = self.validate_length(current_text, max_length)
        if not is_length_valid:
            result['success'] = False
            result['errors'].append({
                'type': 'length_validation_failed',
                'reason': length_reason
            })
        
        # Step 6: Output Validation
        if validate_output:
            output_options = {
                'redact_pii': redact_pii,
                'pii_types': pii_types,
                'check_injections': validate_input,
                'max_length': max_length
            }
            
            is_valid, validated_text, error = self.validate_output(current_text, output_options)
            
            result['output']['valid'] = is_valid
            result['output']['error'] = error
            
            if not is_valid and error:
                result['success'] = False
                result['errors'].append({
                    'type': 'output_validation_failed',
                    'reason': error
                })
            
            current_text = validated_text
        
        # Final processed text
        result['processed_text'] = current_text
        
        # Generate warnings for non-critical issues
        if result['pii'].get('detected'):
            result['warnings'].append({
                'type': 'pii_detected',
                'message': f"PII detected in input: {list(result['pii']['detected'].keys())}"
            })
        
        # Add summary statistics
        result['metadata']['total_errors'] = len(result['errors'])
        result['metadata']['total_warnings'] = len(result['warnings'])
        result['metadata']['processing_time_ms'] = 0  # Placeholder for timing
        
        return result
    
    def quick_validate(self, text: str) -> Tuple[bool, str]:
        """
        Quick validation method for simple use cases.
        
        This is a simplified API that performs basic security checks and returns
        a simple success/failure result with a message.
        
        Args:
            text: The text to validate
        
        Returns:
            Tuple of (success, message)
        
        Example:
            >>> sanitizer = InputSanitizer()
            >>> success, message = sanitizer.quick_validate("Hello world")
            >>> print(success)
            True
            >>> print(message)
            "Text is safe to process"
        """
        result = self.security_pipeline(text, {
            'validate_input': True,
            'detect_pii': True,
            'redact_pii': False,  # Don't modify the text
            'validate_output': False,
            'return_details': False
        })
        
        if result['success']:
            if result['pii'].get('detected'):
                return True, f"Text is safe but contains PII: {list(result['pii']['detected'].keys())}"
            return True, "Text is safe to process"
        else:
            errors = [error['reason'] for error in result['errors']]
            return False, f"Security violation: {', '.join(errors)}"
    
    def safe_process(self, text: str) -> str:
        """
        Safe processing method that returns cleaned text or raises an exception.
        
        This method processes text through the security pipeline and returns the
        cleaned, safe version. Raises an exception if security violations are found.
        
        Args:
            text: The text to process
        
        Returns:
            The processed, safe text
        
        Raises:
            SecurityError: If security violations are detected
        
        Example:
            >>> sanitizer = InputSanitizer()
            >>> try:
            ...     safe_text = sanitizer.safe_process("Contact at test@example.com")
            ...     print(safe_text)  # "Contact at [email_redacted]"
            ... except SecurityError as e:
            ...     print(f"Security violation: {e}")
        """
        result = self.security_pipeline(text)
        
        if not result['success']:
            errors = [error['reason'] for error in result['errors']]
            raise SecurityError(f"Security validation failed: {', '.join(errors)}")
        
        return result['processed_text']


class SecurityError(Exception):
    """Exception raised for security violations in the security pipeline."""
    pass
    
    def process_output(self, text: str, options: Optional[dict] = None) -> str:
        """
        Process output text with validation and sanitization.
        Returns sanitized text or raises exception if invalid.
        
        Args:
            text: The output text to process
            options: Dict with validation options
        
        Returns:
            Sanitized output text
        
        Raises:
            ValueError: If validation fails
        """
        is_valid, sanitized_text, error = self.validate_output(text, options)
        
        if not is_valid:
            raise ValueError(f"Output validation failed: {error}")
        
        return sanitized_text
    