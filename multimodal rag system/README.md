## Multimodal RAG System (Multi-PDF Chatbot)

This Streamlit app lets you upload one or more PDFs, view their content, and chat with an LLM grounded on the text extracted from those PDFs. It stores user accounts and file metadata in a local SQLite database.

### Features
- Login/Signup with SQLite persistence (`multimodal.db`).
- Upload multiple PDFs; files are stored under `user_uploaded_files/` with user-specific prefixes.
- View combined content of selected PDFs.
- Chat over one or many PDFs at once. The app builds a vector store from extracted text and retrieves relevant context for each question.
- Handles common PDF issues: empty files, missing pages, encrypted PDFs (best-effort blank-password attempt), and pages that fail to extract.

### Tech Stack
- UI: Streamlit
- LLM: Google Gemini via `google-generativeai`
- Embeddings: `HuggingFaceEmbeddings` (sentence-transformers)
- Vector Store: FAISS (via `langchain_community`) by default
- DB: SQLite

---

## Getting Started

### 1) Prerequisites
- Python 3.10–3.13 (64-bit recommended)
- pip, venv (recommended)

Windows/OneDrive users: the app already saves uploads using an absolute path to avoid working-directory issues.

### 2) Environment Variables
Create a `.env` file in the project root containing:

```bash
GOOGLE_API_KEY=your_gemini_api_key
```

You can obtain an API key from Google AI Studio.

### 3) Install Dependencies

```bash
pip install -r requirements.txt
```

#### FAISS on Windows/Python 3.13
If `faiss-cpu` fails to install from PyPI on your platform, install a prebuilt wheel that matches your Python version and CPU architecture. One common source is Christoph Gohlke’s Windows wheels. After downloading the correct `.whl` (e.g., `faiss_cpu‑<ver>‑cp313‑cp313‑win_amd64.whl`), run:

```bash
pip uninstall faiss faiss-cpu -y
pip install <path-to-downloaded-wheel>.whl
```

Then ensure LangChain packages are current:

```bash
pip install -U langchain-community
```

If FAISS remains problematic on your environment, you can temporarily switch to Chroma:
- In `main.py`, replace `from langchain_community.vectorstores import FAISS` with `from langchain_community.vectorstores import Chroma`.
- Replace `FAISS.from_texts(...)` with `Chroma.from_texts(...)`.

### 4) Run the App

```bash
streamlit run main.py
```

Open the provided local URL in your browser.

---

## Usage

1. Navigate to “Login/Signup” to create an account or log in.
2. Go to “MultiPdfBot” → “Upload file” to upload one or more PDFs.
3. Use “Your Uploaded Files” → “Select files” and “View Content” to preview combined text.
4. Switch to “Chat with MultiPdfBot”, select one or many PDFs, click “Start Chatting”, then ask questions.

Notes:
- The app will warn you if a PDF is encrypted, corrupted, empty, or has no extractable text.
- For image-only PDFs, text extraction may be empty without OCR. Consider adding OCR (e.g., `pytesseract`) if needed.

---

## Project Structure

```
multimodal rag system/
├─ main.py                 # Streamlit app
├─ multimodal.db           # SQLite database (created on first run)
├─ requirements.txt        # Python dependencies
├─ user_uploaded_files/    # Uploaded PDFs (created on demand)
└─ README.md               # This file
```

---

## Troubleshooting

- FAISS import/install error
  - Ensure 64-bit Python and matching wheel. Try prebuilt wheel for your Python version.
  - Upgrade tooling: `pip install -U pip setuptools wheel`.
  - Update LangChain community: `pip install -U langchain-community`.
  - If blocked, temporarily switch to Chroma (see above) to proceed.

- “Selected file is empty or missing”
  - The file path may be wrong or the file is 0 bytes. Re-upload and save; the app writes using an absolute path to avoid working-directory issues.

- “Failed to read the PDF. It may be corrupted or password-protected.”
  - The app attempts a blank-password decrypt. If it remains encrypted, provide an unprotected copy.

- No text appears from a valid-looking PDF
  - It may be image-only/scanned. Add OCR to extract text.

---

## Notes for Development

- Embeddings backend is set to `HuggingFaceEmbeddings` with `sentence-transformers/all-MiniLM-L6-v2`.
- Chunking uses `RecursiveCharacterTextSplitter.split_text` with large chunk size to keep context coherent.
- Vector store is FAISS by default; you can swap to Chroma if needed for portability.

---

## License

This project is provided as-is for educational purposes. Add your preferred license terms here.


