# EntropyShield: Intelligent Policy Compliance & Enforcement

> **A Solution for Bridging Unstructured Policy Documents with Structured Operational Data.**

## 🎯 The Challenge: The Compliance Gap

In modern enterprises, compliance requirements and business policies are often locked in **unstructured documents** (PDFs, contracts), while the operational data they govern lives in dynamic **structured databases**.

This disconnect forces organizations to rely on manual audits to enforce rules like:
*   *"No dinner expenses over $50."*
*   *"Vendor contracts must be renewed every 365 days."*
*   *"Employees in Tier 2 cities cannot book Business Class."*

Manual verification is slow, error-prone, and cannot scale with data velocity.

---

## 💡 The Solution: EntropyShield

**EntropyShield** is a software-only platform that automates the entire lifecycle of policy enforcement.

It **Ingests** free-text policy documents, **Connects** to company databases, **Flags** violations in real-time, and **Monitors** data continuously—ensuring that your business rules are always enforced.

### 1. Ingest & Interpret (The Policy Engine)
*   **Action:** Drag & drop any unstructured PDF policy (e.g., "Global Travel Policy 2024").
*   **Intelligence:** The system uses NLP to parse the text and extract actionable logic.
*   **Result:** Static text is converted into executable rules (e.g., `IF Expense_Type == 'Dinner' AND Amount > 50 THEN Flag`).

### 2. Connect & Scan (The Compliance Monitor)
*   **Action:** Connects directly to your operational database (SQL/NoSQL).
*   **Intelligence:** A background monitor runs periodic scans, cross-referencing every new database record against the extracted policy rules.
*   **Result:** 100% coverage of all transactions, 24/7.

### 3. Flag & Explain (Mission Control)
*   **Action:** Violations are pushed instantly to a **Live Compliance Dashboard**.
*   **Intelligence:** Every flag includes a clear, explainable justification derived from the original policy text, reducing "false positive" fatigue.
*   **Result:** Auditors focus on high-risk exceptions, not data entry.

---

## 🛡️ Document Integrity (Powered by VeriDoc)

To ensure the policies being enforced are legitimate, EntropyShield incorporates a **Forensic Integrity Module** powered by the **VeriDoc Engine**.

Before any policy is ingested, it undergoes a deep forensic scan to ensure it hasn't been tampered with by unauthorized actors.

*   **Structural DNA Analysis:** Scans for incremental updates and hidden payloads to detect if clauses were surreptitiously changed.
*   **Visual Physics (TruFor):** Uses advanced deep learning to generate heatmaps that reveal pixel-level splicing or editing in scanned policy documents.
*   **Cryptographic Verification:** Validates the digital chain of trust for signed contracts.

---

## 💻 Technical Architecture

| Layer | Component | Function |
| :--- | :--- | :--- |
| **Ingestion** | **Policy Uploader** | Cinematic dropzone for unstructured PDF ingestion and Rule Extraction. |
| **Logic** | **Policy Engine** | Python-based NLP service that converts text to logic. |
| **Monitoring** | **Compliance Monitor** | Background service connecting to `company_data.db` for continuous scanning. |
| **Interface** | **Compliance Dashboard** | React 19 Frontend with Bento Grid layout for real-time violation tracking. |
| **Forensics** | **VeriDoc Engine** | Dual-modality engine (Structural + Visual) ensuring input integrity. |

---

## 🚀 deployment

### Prerequisites
*   Python 3.12+
*   Node.js 20+
*   Google Cloud Project (Vertex AI API enabled)

### Backend

```bash
git clone https://github.com/Start-Impulse/VeriDoc-EntropyShield.git
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/setup_trufor.py  # Download VeriDoc Forensic Models
uvicorn main:app --reload
```

### Frontend

```bash
cd ../frontend
npm install
npm run dev
```

---

**EntropyShield** turns your static policy documents into dynamic, automated data guards.
