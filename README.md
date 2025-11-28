# 📘 Local RAG + Image Captioning Assistant  
### *A Hybrid Retrieval-Augmented Generation + Vision AI System*  
### **Created & Built by _AMBIGAPATHY. S_ — AI & ML Engineer | Data Scientist**

---

## 🎥 Demo Video  
👉 **Watch the full project demo:**  
https://drive.google.com/file/d/1PjkU1pYwZsILEGmUO28R4XK6GmaT1j2U/view?usp=sharing 


---

# 📌 1. Project Overview

This project is a **hybrid AI assistant** that integrates:

### ✅ Retrieval-Augmented Generation (Mini-RAG)  
- Uses **3 PDFs** (AI, ML, and Statistics)  
- Splits them into **700-character chunks** with **150-character overlap**  
- Generates local embeddings using **all-MiniLM-L6-v2**  
- Stores everything in **SQLite vector DB (rag.db)**  
- Performs **semantic search (cosine similarity)**  
- Sends top_k chunks to **Gemini 2.5 Flash** for grounded answers  

### ✅ Image Captioning (Vision Model)  
- Users can upload images  
- Gemini 2.5 Vision generates:  
  - A **short caption**  
  - **3 keyword tags**  
  - In **strict JSON format**  
- Image preview shown inside chat  
- Metadata stored in DB  

### ⭐ Bonus Features  
- Multi-chat support  
- Auto chat naming  
- Dark-themed UI (Dash + Bootstrap)  
- Persistent chat history  
- Efficient backend caching  
- Local model storage (MiniLM)

---

# 🧱 2. System Architecture

```
                 ┌───────────────────────────────┐
                 │             Dash UI            │
                 │  (Chat, Image Upload, History) │
                 └─────────────────┬─────────────┘
                                   │
                              Callbacks
                                   │
                     ┌────────────────────────┐
                     │      RAG Backend       │
                     │   (rag_backend.py)     │
                     └───────────┬────────────┘
                                 │
               ┌──────────────────────────────────────┐
               │  SentenceTransformer: MiniLM-L6-v2    │
               └──────────────────────────────────────┘

               ┌──────────────────────────────────────┐
               │       SQLite Vector Databases        │
               │   rag.db + chat_history.db           │
               └──────────────────────────────────────┘

               ┌──────────────────────────────────────┐
               │             Gemini API               │
               │       2.5 Flash (text + vision)      │
               └──────────────────────────────────────┘
```

---

# 📁 3. Folder Structure

```
project/
│
├── app_dash.py
├── rag_backend.py
├── chat_db.py
├── requirements.txt
├── .env
│
├── assets/
│   ├── data/pdfs/
│   ├── db/
│   │   ├── rag.db
│   │   └── chat_history.db
│   └── models/all-MiniLM-L6-v2/
│
├── scripts/
│   └── build_index.py
│
└── callbacks/
    └── chat_callbacks.py
```

---

# ⚙️ 4. Installation & Setup

### **Step 1: Clone Repo**
```bash
git clone https://github.com/your-repo/project.git
cd project
```

### **Step 2: Create Virtual Environment**
```bash
python -m venv vvenv            # USE: Python 3.10.+ and I was using 3.10.9 for this
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### **Step 3: Install Requirements**
```bash
pip install -r requirements.txt
```

### **Step 4: Add Gemini API Key**
Create a `.env` file:

```
GEMINI_API_KEY=your-api-key-here
```

---

# 🔨 5. Build the Vector Database (RAG Index)

Run:

```bash
python scripts/build_index.py
```

This script will:

- Load the PDFs  
- Split into chunks  
- Embed using MiniLM-L6-v2  
- Store text + embeddings inside **rag.db**

---

# 🗃️ 6. chat_db.py — Automatic Database Handling

✔ `chat_db.py` is executed automatically when the app starts  
✔ It checks if `chat_history.db` already exists  
✔ **If DB exists → do nothing**  
✔ **If not → create required tables**

You **never need to manually run** this file.

---

# ▶️ 7. Run the Application

```bash
python app_dash.py
```

Open in browser:  
👉 http://127.0.0.1:8050/

---

# 🔍 8. How the RAG Pipeline Works

### **1. PDFs → Chunks (700 chars)**  
Chunks overlap by **150 chars** to avoid sentence breaks.

### **2. Chunk → Embedding**  
Using `all-MiniLM-L6-v2`.

### **3. Store in SQLite Vector DB**  
Each row = chunk_text + embedding + metadata.

### **4. User Query → Embedding**

### **5. Cosine Similarity Search**  
Retrieve `top_k` most relevant chunks.

### **6. LLM Answer**  
Send:
- System prompt  
- Query  
- Retrieved chunks  

to **Gemini 2.5 Flash**.

### **7. Display Answer in Chat**

---

# 🖼️ 9. Image Captioning Flow

1. User uploads an image  
2. Converted from base64 → PIL Image  
3. Sent to Gemini 2.5 Vision  
4. Returns **strict JSON**:

```json
{
  "caption": "A laptop on a wooden desk with coffee.",
  "tags": ["laptop", "workspace", "coffee"]
}
```

5. Image & tags saved in chat history  

---

# 💬 10. Chat History Features

- Multi-chat system  
- Rename chats  
- Delete chats  
- Auto-title based on first message  
- Image preview in chat history  
- Fully persistent using SQLite  

---

# 🧪 11. Assignment Requirement Mapping

| Requirement | Status |
|------------|--------|
| RAG over 3 PDFs | ✔ Done |
| 700-char chunks + overlap | ✔ Implemented |
| Local embeddings | ✔ MiniLM-L6-v2 |
| SQLite vector DB | ✔ rag.db |
| Image captioning (JSON) | ✔ Done |
| History awareness | ✔ Implemented |
| Efficient cosine similarity | ✔ Yes |
| Chat system | ✔ Advanced |
| Automatic DB handling | ✔ chat_db.py |
| UI | ✔ Beautiful Dash Interface |

---

# 📜 12. Future Enhancements

- Telegram / Discord bot interface  
- Source highlighting in responses  
- FAISS or sqlite-vec ANN search  
- Cloud deployment  

---

# 🏁 13. Conclusion

This project showcases a **fully functional AI assistant** combining:

- Local vector search  
- RAG over PDFs  
- Vision captioning  
- Persistent chat system  
- Gemini-powered LLM responses  
- Clean, dark-themed UI  

It fully satisfies the **Data Science Assignment** requirements and includes advanced features beyond the expected scope.

---

# ✨ Author

**Created & Built by  
_➡️ AMBIGAPATHY. S_  
AI & ML Engineer | Data Scientist**

---

# 📬 Contact
👉   https://www.linkedin.com/in/ambigapathy-s  
For improvements, suggestions, or collaborations — feel free to reach out!
