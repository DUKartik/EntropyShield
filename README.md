# VeriDoc: EntropyShield

![Veridoc Header](readme/header.png)

> **A "Hybrid Intelligence" Forensic Engine on Google Cloud Platform**

## 📖 Overview

**VeriDoc: EntropyShield** is a next-generation document forgery detection system that bridges the gap between deterministic software engineering and adaptive artificial intelligence.

In an era where "deepfakes" and pixel-perfect editing tools have democratized fraud, traditional metadata checks are no longer sufficient. VeriDoc introduces a **Dual-Modality Forensic Engine** that interrogates a document from two distinct perspectives:

1.  **Structural DNA (The "Code"):** Analyzing the raw binary structure, file entropy, and metadata consistency.
2.  **Visual Physics (The "Signal"):** Examining camera sensor noise, compression artifacts, and pixel-level inconsistencies using deep learning.

This system, powered by **Hybrid Intelligence**, fuses these technical signals with the semantic reasoning of **Google Gemini 2.5 Flash** to provide a legally defensible "Proof of Authenticity."

---

## 💻 Frontend: Cinematic Enterprise

The user interface is built on the **"Cinematic Enterprise"** design philosophy—a fusion of high-performance utility and immersive visual storytelling.

*   **Glassmorphism & Texture:** A sophisticated dark mode aesthetic using backdrop blurs, grain textures, and localized lighting effects to create depth.
*   **Typography:** A carefully curated stack using **Inter** for high-density data readability and **Outfit** for modern, impactful headers.
*   **Micro-Interactions:** Physics-based animations (Framer Motion) provide immediate, tactile feedback for every user action.

### Core Components

| Component | Description |
| :--- | :--- |
| **Compliance Dashboard** | A "Mission Control" interface featuring a **Bento Grid** layout, live violation feeds, and real-time velocity charts. |
| **Policy Uploader** | A cinematic dropzone that ingests corporate policy PDFs, using AI to extract rules and check for tampering before storage. |
| **Data Viewer** | A high-performance forensic table (TanStack Table) offering fuzzy search, column visibility controls, and deep metadata inspection. |

---

## 🏗 System Architecture

The core of VeriDoc is a **Conditional Logic Orchestrator** (Python/FastAPI) that routes files to specialized pipelines based on their file type and content.

### 🕵️‍♂️ Pipeline A: Digital Structural Analysis
**Target:** Native PDFs (System-generated invoices, contracts).

*   **Incremental Update Detection:** Scans for multiple `%%EOF` markers to detect if a file was modified after its initial creation.
*   **Deep Image Inspection:** Automatically extracts embedded images from PDFs and routes them to the Visual Lab for deeper analysis (checking for pasted signatures).
*   **Hidden Payload Detection:** Identifies "orphaned" objects, embedded files, and JavaScript that could indicate malicious intent.
*   **Metadata Forensics:** Flags suspicious producer tools often used by fraudsters (e.g., "Phantom", "GPL Ghostscript").

### 👁️ Pipeline B: Visual Statistical Analysis
**Target:** Scanned Documents, JPEGs, Screenshots, & Extracted Assets.

*   **TruFor (True Forensics):** Integrates the state-of-the-art **TruFor** engine (Noiseprint++ / CMX) to generate high-fidelity anomaly heatmaps, detecting splicing by analyzing camera sensor noise.
*   **Semantic Segmentation:** Uses a **SegFormer-B0** model to perform pixel-level tampering detection, trained specifically on document layouts.
*   **Error Level Analysis (ELA):** visualizes compression artifacts to highlight regions that have been saved at different quality levels (a hallmark of splicing).
*   **Double Quantization:** Detects histogram periodicity artifacts that occur when an image is saved twice (original -> edit -> save).

### 🔐 Pipeline C: Cryptographic Verification
**Target:** Digitally Signed PDFs.

*   **Chain of Trust:** Validates the cryptographic chain from the document signature to a trusted root CA.
*   **Integrity Hash:** Ensuring the document byte-stream has not been altered by even a single bit since signing.
*   **Revocation Checks:** Verifies that the signing certificate was valid at the time of signing and has not been revoked.

---

## 🧠 Universal Layer: Unified Forensic Reasoning

When pipelines return complex or ambiguous technical data, the **Universal Reasoning Layer** acts as the final judge.

*   **Engine:** **Google Vertex AI (Gemini 2.5 Flash)**.
*   **Methodology:** The system constructs a detailed "Forensic Context" JSON object containing all technical findings (ELA scores, metadata flags, TruFor heatmaps) and prompts the model to act as an **"Expert Forensic Auditor"**.
*   **Output:** A structured, human-readable verdict explaining *why* a document is suspicious, moving beyond simple probability scores.

---

## 🛡️ Compliance Automation

Beyond individual document checking, VeriDoc offers enterprise-grade compliance monitoring.

*   **Policy Engine:** Upload corporate policy documents (e.g., "Expense Policy 2024"). The system uses NLP to extract rules (e.g., "Max dinner expense $50") and stores them.
*   **Mock Database:** A simulated "Company Database" (SQLite) containing employee and expense records.
*   **Automated Audits:** The Compliance Monitor runs periodic checks, cross-referencing database records against extracted policy rules effectively acting as an automated internal auditor.

---

## 🚀 Setup Instructions

### Prerequisites
*   Python 3.12+
*   Node.js 20+
*   Google Cloud Project (with Vertex AI API enabled)

### Backend (FastAPI)

1.  **Clone & Navigate:**
    ```bash
    git clone https://github.com/Start-Impulse/VeriDoc-EntropyShield.git
    cd backend
    ```

2.  **Environment Setup:**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    
    pip install -r requirements.txt
    ```

3.  **Model Setup (Critical):**
    Download the TruFor weights (~250MB):
    ```bash
    python scripts/setup_trufor.py
    ```

4.  **Configuration:**
    Create a `.env` file with your Google Cloud credentials:
    ```env
    GOOGLE_APPLICATION_CREDENTIALS="path/to/key.json"
    Project_ID="your-gcp-project-id"
    LOCATION="us-central1"
    ```

5.  **Run Server:**
    ```bash
    uvicorn main:app --reload
    ```

### Frontend (React/Vite)

1.  **Navigate:**
    ```bash
    cd ../frontend
    ```

2.  **Install:**
    ```bash
    npm install
    ```

3.  **Run:**
    ```bash
    npm run dev
    ```

---

## 💻 Tech Stack

| Domain | Technologies |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, **TailwindCSS**, Framer Motion, Recharts, TanStack Query/Table, Lucide React |
| **Backend** | Python 3.12, **FastAPI**, Uvicorn, Pydantic |
| **AI / ML** | **PyTorch** (SegFormer), **Transformers**, **TruFor** (Noiseprint++), OpenCV, Scikit-Learn |
| **Reasoning** | **Google Vertex AI**, Gemini 2.5 Flash |
| **Infrastructure**| Google Cloud Run (Serverless), GCS (Secure Storage), Docker |
