# Trust Store for VeriDoc

This directory is used to store **Trusted Root Certificates** (Certificate Authorities) for Pipeline C (Cryptographic Analysis).

## How to use

1.  Obtain the **Root Certificate** (`.pem`, `.crt`, or `.cer`) of the authority you trust (e.g., your organization's internal CA, Adobe Root CA, Government Root).
2.  Place the file in this directory: `backend/resources/trust_store/`.
3.  The backend will (in a future update) load these certificates to validate PDF signatures against this trust list.

**Note:** Currently, the pipeline is configured to use the default system validation context (`ValidationContext`). Custom loading of these files can be enabled in `services/pipeline_orchestrator.py`.
