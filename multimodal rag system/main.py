import streamlit as st
import sqlite3
import hashlib
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
# from langchain.embeddings import SentenceTransformerEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
import google.generativeai as genai
import os
from dotenv import load_dotenv
from streamlit_option_menu import option_menu
from PyPDF2 import PdfReader

load_dotenv()
genai.configure(api_key = os.getenv('GOOGLE_API_KEY'))

gemini = genai.GenerativeModel("gemini-2.0-flash")

DB_NAME = "multimodal.db"
# Use an absolute path for uploads to avoid working-directory issues
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "user_uploaded_files")

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL                                         
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS files(
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """) 

    print("Database and Tables initialized")  


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def sign_up(first_name, last_name, email, password):
    with sqlite3.connect(DB_NAME) as conn:
        try:
            conn.execute("""
            INSERT INTO users (first_name, last_name,  email, password)
            VALUES (?, ?, ?, ?)                    
            """, (first_name, last_name,  email, hash_password(password)))
            conn.commit()
            return True, "Account created Successfully, Now you can login"
        
        except sqlite3.IntegrityError:
            return False, "This email is already registered, Try logging in."
        

def login(email, password):
    with sqlite3.connect(DB_NAME) as conn:
        user = conn.execute("""
        SELECT user_id, first_name, last_name FROM users WHERE email = ? AND password = ?                            
        """, (email, hash_password(password))).fetchone()
        return user if user else None
    

def save_file(user_id, file_name, file_path):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        INSERT INTO files (user_id, file_name, file_path)
        VALUES (?, ?, ?)
        """, (user_id, file_name, file_path))
        conn.commit()


def get_user_files(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        files = conn.execute("""
        SELECT file_name, file_path FROM files where user_id = ?
        """, (user_id,)).fetchall()
        return files
    

def delete_file(user_id, file_name):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        DELETE FROM files WHERE (user_id, file_name) = (?, ?)
        """, (user_id, file_name))
        conn.commit()

init_db()

#embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
# embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2") 
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def get_chunks(text):
    splitter = RecursiveCharacterTextSplitter(chunk_size = 10000, chunk_overlap = 200)
    chunks = splitter.split_text(text)
    return chunks

def get_vector_store(chunks):
    db = FAISS.from_texts(chunks, embeddings)
    return db

def get_rel_text(user_query, db):
    rel_text = db.similarity_search(user_query, k=1)
    return rel_text[0].page_content if rel_text else "No relevant information found."

def bot_response(model, query, relevant_texts, history):
    context = " ".join(relevant_texts)
    prompt = f"""

    This is the context of the document
    Context : {context}
    And this is the User Query
    User : {query}
    And this is the history of the conversation
    History : {history}

    Please generate a response to the user query based on the context and the history of the conversation.
    The questions might be asked related to the provided context.
    Answer the question with respect to the context provided, you can also use your additional knowledge too.
    Answer the following queries like a professional , having a lot of knowledge on the basis of file context.

    Bot :

    """

    response = model.generate_content(
        prompt,
        generation_config = genai.GenerationConfig(
            temperature = 0.68
        )
    )

    return response.text


model = genai.GenerativeModel(model_name="gemini-2.0-flash")

# -------- PDF Utilities --------
def extract_pdf_text(file_path):
    """Read a PDF safely. Attempts to open encrypted PDFs with blank password.
    Returns a tuple: (text, error_message). If error_message is not None, text may be empty.
    """
    try:
        reader = PdfReader(file_path)
    except Exception:
        return "", "Failed to open PDF. It may be corrupted or unsupported."

    # Handle encrypted PDFs where possible
    try:
        if getattr(reader, "is_encrypted", False):
            try:
                # Try empty password
                result = reader.decrypt("") if hasattr(reader, "decrypt") else None
                # If still encrypted after attempt, ask user for a different PDF
                if getattr(reader, "is_encrypted", False):
                    return "", "PDF appears to be encrypted. Please provide an unprotected PDF."
            except Exception:
                return "", "PDF is encrypted and could not be opened."
    except Exception:
        # If checking encryption raises, continue with best-effort
        pass

    if not hasattr(reader, "pages") or len(reader.pages) == 0:
        return "", "PDF has no pages."

    accumulated_text = ""
    for page in reader.pages:
        try:
            extracted = page.extract_text() or ""
            accumulated_text += extracted
        except Exception:
            # Skip problematic pages, continue extracting
            continue

    if not accumulated_text.strip():
        return "", "No extractable text found in the PDF."

    return accumulated_text, None

st.set_page_config(page_title="multipdfbot", page_icon="📄", layout="wide")

if 'messages' not in st.session_state:
    st.session_state.messages = {}

with st.sidebar:
    selected = option_menu(
        "Menu", ["Landing Page", "Login/Signup", "MultiPdfBot"],
        icons = ["house", "person", "chat-dots"],
        menu_icon = "cast", default_index=0
    )

if selected == "Login/Signup":
    st.header("Login/ Signup")

    if "user_id" in st.session_state:
        st.info(f"You are logged in as {st.session_state['first_name']} {st.session_state['last_name']}")
        if st.button("Logout"):
            st.session_state.clear()
            st.success("Logged Out Successfully!")

    else:
        action = st.selectbox("Select an action", ['Login', 'Sign Up'])

        if action == "Sign Up":
            st.subheader("Sign Up")
            first_name = st.text_input("First Name")
            last_name = st.text_input("Last Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type='password')

            if st.button("Sign Up"):
                success, msg = sign_up(first_name, last_name, email, password)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

        
        elif action == "Login":
            st.subheader("Login")
            email = st.text_input("Email")
            password = st.text_input("Password", type='password')
            
            if st.button("Login"):
                user = login(email, password)
                if user:
                    st.session_state['user_id'], st.session_state['first_name'], st.session_state['last_name'] = user
                    st.success(f"Logged in as: {user[1]} {user[2]}!")
                    st.session_state.messages[st.session_state['user_id']] = []

                else:
                    st.error("Invalid Email or Password")

if selected == "MultiPdfBot":
    st.subheader("pdf Reader")

    if 'user_id' not in st.session_state:
        st.warning("Please login to access the MultiPdfBot")

    else:
        with st.expander("Select the feature ", expanded = True):
            choice = st.radio(
                label = "Select an option",
                options = ["Upload file", "Chat with MultiPdfBot"]
            )

        st.info(f"Welcome {st.session_state['first_name']} !!")

        if choice == "Upload file":
            files_uploaded = st.file_uploader(label = "Upload your PDF(s)", type = 'pdf', accept_multiple_files=True)

            if files_uploaded:
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                for uploaded in files_uploaded:
                    file_name = uploaded.name
                    file_path = os.path.join(UPLOAD_DIR, f"{st.session_state['user_id']}_{file_name}")

                    # Always write the uploaded file to avoid stale or zero-byte remnants
                    with open(file_path, 'wb') as f:
                        f.write(uploaded.read())

                    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                        st.error(f"{file_name}: Uploaded file appears to be empty. Skipped.")
                        continue

                    save_file(st.session_state['user_id'], file_name, file_path)
                    st.success(f"{file_name}: saved successfully!")


            st.subheader("Your Uploaded Files")
            files = get_user_files(st.session_state['user_id'])
            
            if files:
                for file_name, file_path in files:
                    st.markdown(f"- {file_name}")
                    if st.button(f"Delete {file_name}"):
                        delete_file(st.session_state['user_id'], file_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        st.success(f"File {file_name} deleted successfully!")

                st.subheader("File Content Viewer")
                s_files = st.multiselect(label = "Select files", options = [i for i,v in files])

                def get_value(i, lst):
                    for pair in lst:
                        if pair[0] == i:
                            return pair[1]
                    return None
                
                if s_files:
                    if st.button("View Content"):
                        with st.spinner("Giving the details"):
                            combined_text = ""
                            for s_file in s_files:
                                file_path = get_value(s_file, files)
                                text, err = extract_pdf_text(file_path)
                                if err:
                                    st.warning(f"{s_file}: {err}")
                                combined_text += f"\n\n===== {s_file} =====\n" + text

                            st.subheader("Combined content of selected files")
                            st.write(combined_text.strip() if combined_text.strip() else "No extractable text found in selected PDFs.")

            else:
                st.info("No files uploaded yet.")

        if choice == "Chat with MultiPdfBot":
            st.subheader("Chat with MultiPdfBot")
            def get_value(i, lst):
                    for pair in lst:
                        if pair[0] == i:
                            return pair[1]
                    return None
            user_files = get_user_files(st.session_state['user_id'])
            if not user_files:
                st.warning("Please upload files to chat with MultiPdfBot")
            else:
                selected_files = st.multiselect("Select files to chat with", [i for i,v in user_files])

                if selected_files:
                    if st.button("Start Chatting"):
                        with st.spinner("Preparing selected file(s) for chat..."):
                            combined_text = ""
                            for name in selected_files:
                                fp = get_value(name, user_files)
                                if not fp or not os.path.exists(fp) or os.path.getsize(fp) == 0:
                                    st.warning(f"{name}: file missing or empty. Skipped.")
                                    continue
                                text, err = extract_pdf_text(fp)
                                if err:
                                    st.warning(f"{name}: {err}")
                                combined_text += f"\n\n===== {name} =====\n" + text

                            if not combined_text.strip():
                                st.error("No extractable text found in selected PDFs.")
                            else:
                                chunks = get_chunks(combined_text)
                                db = get_vector_store(chunks)
                                st.session_state['db'] = db
                                st.success("File(s) are ready for chat!")

                if 'db' in st.session_state:
                    user_query = st.text_input("Enter your query here")
                    if st.button("Get Answer"):
                        if user_query:
                            with st.spinner("Getting the answer..."):
                                db = st.session_state['db']
                                relevant_text = get_rel_text(user_query, db)
                                history = "\n".join([f"User: {msg['user']}\nBot: {msg['bot']}" for msg in st.session_state.messages[st.session_state['user_id']]])
                                response = bot_response(model, user_query, [relevant_text], history)
                                st.session_state.messages[st.session_state['user_id']].append({"user": user_query, "bot": response})
                                st.success("Answer generated!")

                    if st.session_state.messages[st.session_state['user_id']]:
                        for msg in st.session_state.messages[st.session_state['user_id']]:
                            st.markdown(f"**User:** {msg['user']}")
                            st.markdown(f"**Bot:** {msg['bot']}")
                            st.markdown("---")

        

