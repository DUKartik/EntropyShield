# EntropyShield: Intelligent Policy Compliance & Enforcement

> **Bridging unstructured policy documents with structured operational data — automatically, at scale.**

---

## 🎯 The Problem: The Compliance Gap

In modern enterprises, compliance requirements live in **unstructured documents** (PDFs, contracts, policy memos), while the operational data they govern lives in **structured databases**.

This disconnect forces organisations to rely on slow, error-prone manual audits to enforce rules like:

- *"No dinner expenses over ₹2,000."*
- *"Vendor contracts must be renewed every 365 days."*
- *"Employees in Tier-2 cities cannot book Business Class."*

Manual verification cannot scale with modern data velocity.

---

## 💡 The Solution: EntropyShield

EntropyShield automates the **full lifecycle of policy enforcement** in four steps:

### 1. Ingest & Interpret — Policy Engine
- Upload any unstructured PDF policy document via a drag-and-drop interface.
- **Gemini 1.5 Pro (Vertex AI)** extracts actionable rules from free text.
- Rules are normalised into executable logic (e.g., `IF expense_type == 'Dinner' AND amount > 2000 THEN Flag`).

### 2. Connect & Scan — Compliance Monitor
- Connects to the local `company_data.db` (SQLite via SQLAlchemy).
- A background monitor cross-references every record against extracted policy rules.
- **Persistent Rules**: Policies are stored in SQLite so they survive server restarts.
- Delivers **100% transaction coverage, 24/7**.

### 3. Flag, Triage & Explain — Live Dashboard
- Violations surface instantly on the **Compliance Dashboard**.
- Each flag includes a plain-language justification derived from the original policy text.
- **Human-in-the-Loop Triage**: Compliance officers can *Approve* or *Reject* violations directly from the dashboard.
- **Audit Trails**: Triaged violations are logged to an `audit_logs` table (including reviewer notes) and excluded from the active KPI count.
- Bento Grid layout with real-time violation feed and interactive charts.

### 4. Verify Integrity — VeriDoc Forensic Engine
- Every uploaded policy PDF is scanned **before** ingestion.
- **Structural DNA Analysis:** detects hidden payloads and incremental update tampering.
- **Visual Physics (TruFor + SegFormer):** deep-learning heatmaps reveal pixel-level image splicing in scanned documents.
- **Cryptographic Chain-of-Trust:** validates digital signatures via PyHanko.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         Frontend (React 19 + Vite)             │
│  PolicyUploader → DataViewer → ComplianceDashboard             │
└───────────────────────────┬────────────────────────────────────┘
                            │ REST / JSON
┌───────────────────────────▼────────────────────────────────────┐
│                  Backend (FastAPI + Uvicorn)                    │
│                                                                │
│  /api/forensics  →  Pipeline Orchestrator                      │
│    ├─ Pipeline A: Structural Analysis (pypdf, pyhanko)         │
│    ├─ Pipeline B: Visual Analysis    (SegFormer, ELA, SIFT)    │
│    └─ Pipeline C: Crypto Verification (cryptography, pyhanko)  │
│                                                                │
│  /api/compliance →  Policy Engine (Vertex AI / Gemini)         │
│    ├─ Compliance Monitor (SQLAlchemy → company_data.db)        │
│    └─ Audit Logger (Approvals / False Positive tracking)       │
│                                                                │
│  /api/admin      →  Dataset Loader / DB Admin                  │
└────────────────────────────────────────────────────────────────┘
```

### Performance Optimisations
- **Zero-Latency Forensic Uploads**: Integrates with GCS `gs://` URIs allowing Vertex AI to read document bytes directly without routing through the backend.
- **Fast Startup via Lazy Loading**: Heavy data science libraries (`torch`, `cv2`, `PIL`, `vertexai`) are rigorously deferred until first use. Server startup takes **~5 seconds** instead of 30+.
- **Query Chunking & Stratification**: Uses chunked SQLAlchemy queries (10k rows) and stratified DB sampling to maintain constant RAM usage regardless of dataset size (e.g., handles the 3GB AML dataset smoothly).

### Technology Stack

| Layer | Technology | Version |
|:---|:---|:---|
| **API Framework** | FastAPI + Uvicorn | 0.129.0 / 0.41.0 |
| **AI / LLM** | Google Vertex AI (Gemini) | `google-cloud-aiplatform` 1.138.0 |
| **Forensic Visual** | PyTorch + Transformers + timm | 2.10.0 / 5.2.0 / 1.0.24 |
| **PDF Processing** | pypdf + pyhanko + pdfminer.six | 6.7.1 / 0.33.0 |
| **Computer Vision** | OpenCV Headless + Pillow | 4.13.0 / 12.1.1 |
| **Database** | SQLAlchemy + SQLite | 2.0.46 |
| **Frontend** | React 19 + Vite + TypeScript | — |
| **Styling** | Tailwind CSS v4 | — |
| **Python** | CPython | **3.12.10** |
| **Node.js** | Node.js | 20+ |

---

## 🚀 Local Setup

### Prerequisites

- **Python 3.12.10** (via [python.org](https://www.python.org/downloads/) or `py -3.12`)
- **Node.js 20+**
- **Google Cloud Project** with Vertex AI API enabled
- A valid `backend/gcp-key.json` service-account key file

---

### Backend

```powershell
# 1. Clone the repository
git clone https://github.com/Start-Impulse/VeriDoc-EntropyShield.git
cd VeriDoc-EntropyShield\backend

# 2. Create and activate a Python 3.12 virtual environment
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env
# Edit .env with your GCP project ID, credentials path, etc.

# 5. (Optional) Download VeriDoc forensic model weights
python scripts/setup_trufor.py

# 6. Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

> **Linux / macOS:** replace `.\venv\Scripts\Activate.ps1` with `source venv/bin/activate`.

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

### Frontend

```bash
cd ../frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## 📁 Project Structure

```
EntropyShield/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── requirements.txt          # Pinned Python dependencies
│   ├── .env.example              # Environment variable template
│   ├── company_data.db           # SQLite operational database
│   ├── routers/
│   │   ├── forensics.py          # /api/forensics — document scanning
│   │   ├── compliance.py         # /api/compliance — rule checking
│   │   └── admin.py              # /api/admin — DB management
│   ├── services/
│   │   ├── policy_engine.py      # Gemini rule extraction
│   │   ├── compliance_monitor.py # Background scanning service
│   │   ├── database_connector.py # SQLAlchemy connection + seed
│   │   ├── dataset_loader.py     # CSV → SQLite ingestion
│   │   ├── image_analyzers.py    # ELA, SIFT, metadata analysis
│   │   └── forensic_reasoning.py # AI forensic report generation
│   ├── components/
│   │   ├── pipeline_orchestrator.py
│   │   ├── scoring_engine.py
│   │   ├── segformer/            # SegFormer forgery detection
│   │   └── trufor/               # TruFor deep-learning forensics
│   └── utils/
│       ├── debug_logger.py
│       └── crypto_utils.py
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── PolicyUploader.tsx
    │   │   ├── DataViewer.tsx
    │   │   └── ComplianceDashboard.tsx
    │   └── services/
    └── index.html
```

---

## 🔑 Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in:

| Variable | Description |
|:---|:---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to your `gcp-key.json` |
| `GCP_PROJECT_ID` | Your Google Cloud project ID |
| `GCP_LOCATION` | Vertex AI region (e.g. `asia-south1`) |
| `TRUFOR_REMOTE_URL` | (Optional) Remote TruFor inference endpoint |

---

**EntropyShield** — turn static policy documents into dynamic, automated data guards.
