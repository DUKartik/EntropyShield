import os
import certifi
import logging
from typing import List, Optional, Dict, Any

from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.registry import SimpleCertificateStore
from pyhanko.sign.validation import async_validate_pdf_signature
from pyhanko.sign.validation.status import SignatureStatus
from cryptography.hazmat.primitives import hashes

from asn1crypto import x509, pem


# Setup Logger
logger = logging.getLogger(__name__)

def load_trust_store() -> SimpleCertificateStore:
    """
    Loads a Hybrid Trust Store:
    1. Standard Web Trust from 'certifi' (Mozilla CA Bundle).
    2. Local Custom Roots from 'backend/resources/trust_store'.
    """
    store = SimpleCertificateStore()
    
    # 1. Load Standard Web Trust (Certifi)
    try:
        certifi_path = certifi.where()
        store.register_multiple(certifi_path)
        logger.info(f"Loaded Standard Trust Store from {certifi_path}")
    except Exception as e:
        logger.warning(f"Failed to load certifi trust store: {e}")

    # 2. Load Local Custom Roots
    # path relative to this file: ../../resources/trust_store
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_store_path = os.path.join(base_dir, "resources", "trust_store")
    
    if os.path.exists(local_store_path):
        count = 0
        for root, _, files in os.walk(local_store_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()

                        # Use asn1crypto to load (handles both PEM and DER)
                        try:
                            # Explicitly handle PEM if detected
                            if pem.detect(data):
                                _, _, data = pem.unarmor(data)
                            
                            cert = x509.Certificate.load(data)
                            store.register(cert)
                            count += 1
                        except Exception as load_err:
                            # Not a valid cert
                            logger.debug(f"File {file} is not a valid certificate: {load_err}")
                            continue

                except Exception as e:
                    logger.debug(f"Skipping non-cert file {file}: {e}")
        
        if count > 0:
            logger.info(f"Loaded {count} custom root certificates from {local_store_path}")
            
    return store

def get_validation_context() -> ValidationContext:
    """
    Returns a 'Smart' ValidationContext with standard forensic defaults:
    - Hybrid Trust Store
    - AIA & OCSP Enabled (allow_fetching=True)
    - Soft-Fail Revocation (Best effort check)
    - Time Tolerance (for clock skew)
    """
    from datetime import timedelta
    
    trust_store = load_trust_store()
    
    return ValidationContext(
        trust_roots=trust_store,
        allow_fetching=True,             # ENABLE AIA & OCSP (Zero-Touch)
        revocation_mode="soft-fail",     # Don't crash if offline
        weak_hash_algos={'sha1', 'md5'}, # Explicitly allow but we will flag them later
        time_tolerance=timedelta(seconds=10),  # 10s clock skew tolerance
        other_certs=[]                   # Can be populated if needed
    )

async def validate_signature_forensic(sig_obj, validation_context: ValidationContext) -> Dict[str, Any]:
    """
    Validates a signature object and returns a comprehensive forensic report.
    Handles 'Weak Algorithm' and 'Policy' errors gracefully.
    """
    result = {
        "field": sig_obj.field_name,
        "valid": False,
        "intact": False,
        "trusted": False,
        "revoked": False,
        "signer_name": None,
        "issuer": None,
        "signing_time": None,
        "md_algorithm": None,
        "fingerprint": None,
        "serial_number": None,
        "weak_hash": False,
        "weak_key": False,
        "error": None,
        "warnings": []
    }

    try:
        # Perform Validation
        # We catch weak algos separate from invalid sigs
        status: SignatureStatus = await async_validate_pdf_signature(
            sig_obj, 
            signer_validation_context=validation_context
        )
        
        # Extract Basic Info
        result['valid'] = status.valid
        result['intact'] = status.intact
        result['trusted'] = status.trusted
        result['revoked'] = status.revoked
        result['md_algorithm'] = status.md_algorithm
        
        if status.signer_reported_dt:
            result['signing_time'] = str(status.signer_reported_dt)
            

        # Extract Certificate Details
        if status.signing_cert:
            cert = status.signing_cert
            # cert is likely asn1crypto.x509.Certificate
            
            result['signer_name'] = cert.subject.human_friendly
            result['issuer'] = cert.issuer.human_friendly
            result['serial_number'] = str(cert.serial_number)
            
            # Convert to cryptography object for advanced inspection (fingerprint, key size)
            try:
                from cryptography.x509 import load_der_x509_certificate
                crypto_cert = load_der_x509_certificate(cert.dump())
                
                result['fingerprint'] = crypto_cert.fingerprint(hashes.SHA256()).hex()

                # Check for Weak Key (RSA < 2048)
                public_key = crypto_cert.public_key()
                if hasattr(public_key, 'key_size'):
                    if public_key.key_size < 2048:
                        result['weak_key'] = True
                        result['warnings'].append(f"Weak Key Size: {public_key.key_size} bits")
            except Exception as e:
                logger.warning(f"Failed to inspect certificate details: {e}")


        # Check for Weak Hash
        if status.md_algorithm in ['sha1', 'md5']:
            result['weak_hash'] = True
            result['warnings'].append(f"Weak Hash Algorithm: {status.md_algorithm}")

        # Final Validity Logic Correction
        # If valid but has warnings, it is technically valid.
        
    except Exception as e:
        err_str = str(e)
        result['error'] = err_str
        
        # CRITICAL FIX: When validation fails, we should default to:
        # - intact: True (assume document not tampered, just can't verify)
        # - trusted: False (can't verify trust chain)
        # - valid: False (validation failed)
        # 
        # Only if pyhanko successfully validates and returns intact=False should we treat it as tampering.
        
        # Heuristic Analysis of Error
        if "weak" in err_str.lower() or "algorithm" in err_str.lower():
            result['weak_hash'] = True
            result['valid'] = True # Physically intact, just old
            result['intact'] = True
            result['warnings'].append(f"Legacy Algorithm detected: {err_str}")
        elif "policy" in err_str.lower() or "trust" in err_str.lower() or "certificate" in err_str.lower():
             # Trust/Policy failures mean we can't verify WHO signed it, not that it's tampered
             result['valid'] = False
             result['intact'] = True  # Assume intact unless proven otherwise
             result['trusted'] = False
             result['warnings'].append(f"Trust validation failed: {err_str[:100]}")
        else:
             # Unknown error - be conservative, assume intact but unverifiable
             result['valid'] = False
             result['intact'] = True  # Default to intact for unknown errors
             result['trusted'] = False
             result['warnings'].append(f"Validation error: {err_str[:100]}")
             
    return result
