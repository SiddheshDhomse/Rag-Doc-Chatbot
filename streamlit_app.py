from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests
import streamlit as st


API_BASE_URL = os.getenv("RAG_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 120


def get_documents() -> list[dict[str, Any]]:
    response = requests.get(f"{API_BASE_URL}/documents/", timeout=15)
    response.raise_for_status()
    documents = response.json()
    if isinstance(documents, list):
        return documents
    return []


def upload_document(uploaded_file) -> dict[str, Any]:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    response = requests.post(f"{API_BASE_URL}/upload/", files=files, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def delete_document(filename: str) -> None:
    response = requests.delete(f"{API_BASE_URL}/documents/{quote(filename)}", timeout=30)
    response.raise_for_status()


def stream_answer(question: str, filename: str | None):
    params = {"question": question}
    if filename:
        params["filename"] = filename

    with requests.post(
        f"{API_BASE_URL}/query/",
        params=params,
        stream=True,
        timeout=REQUEST_TIMEOUT,
    ) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                yield chunk


def ensure_session_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("selected_filename", "All documents")


def render_document_manager(documents: list[dict[str, Any]]) -> None:
    st.subheader("Documents")
    uploaded_file = st.file_uploader(
        "Upload PDF or Excel",
        type=["pdf", "xlsx", "xls"],
        help="Large files are indexed in the background, so they may take a moment to become ready.",
    )

    if uploaded_file is not None and st.button("Start indexing", use_container_width=True):
        try:
            result = upload_document(uploaded_file)
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}")
        else:
            st.success(result.get("message", "Document accepted for processing."))
            st.rerun()

    processed_options = ["All documents"] + [
        doc["filename"] for doc in documents if doc.get("status") == "processed"
    ]

    if st.session_state.selected_filename not in processed_options:
        st.session_state.selected_filename = "All documents"

    st.selectbox(
        "Answer scope",
        processed_options,
        key="selected_filename",
        help="Use a single file when you want a narrower answer.",
    )

    if st.button("Refresh document status", use_container_width=True):
        st.rerun()

    if not documents:
        st.info("No documents uploaded yet.")
        return

    for doc in documents:
        filename = doc.get("filename", "unknown")
        status = doc.get("status", "unknown")
        chunks = doc.get("chunks", 0)
        label = f"{filename}  |  {status}  |  {chunks} chunks"
        with st.container(border=True):
            st.write(label)
            if st.button("Remove", key=f"remove-{filename}", use_container_width=True):
                try:
                    delete_document(filename)
                except requests.RequestException as exc:
                    st.error(f"Delete failed: {exc}")
                else:
                    if st.session_state.selected_filename == filename:
                        st.session_state.selected_filename = "All documents"
                    st.rerun()


def render_chat(documents: list[dict[str, Any]]) -> None:
    processed_count = sum(1 for doc in documents if doc.get("status") == "processed")
    processing_count = sum(1 for doc in documents if doc.get("status") == "processing")

    st.subheader("Chat")
    col1, col2, col3 = st.columns([1, 1, 1])
    col1.metric("Ready files", processed_count)
    col2.metric("Processing", processing_count)
    if col3.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    disabled = processed_count == 0
    placeholder = (
        "Upload a document first..."
        if disabled
        else "Ask about the uploaded PDFs or spreadsheets..."
    )

    prompt = st.chat_input(placeholder, disabled=disabled)
    if not prompt:
        return

    scope = st.session_state.selected_filename
    selected_filename = None if scope == "All documents" else scope

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    assistant_text = ""
    st.session_state.messages.append({"role": "assistant", "content": ""})

    with st.chat_message("assistant"):
        placeholder_container = st.empty()
        try:
            for piece in stream_answer(prompt, selected_filename):
                assistant_text += piece
                placeholder_container.markdown(assistant_text + "...")
        except requests.HTTPError as exc:
            try:
                detail = exc.response.json().get("detail", str(exc))
            except Exception:
                detail = str(exc)
            assistant_text = f"Request failed: {detail}"
        except requests.RequestException as exc:
            assistant_text = f"Backend is unavailable: {exc}"

        placeholder_container.markdown(assistant_text or "No response received.")

    st.session_state.messages[-1]["content"] = assistant_text or "No response received."


def main() -> None:
    st.set_page_config(
        page_title="Enterprise RAG Chatbot",
        layout="wide",
    )
    ensure_session_state()

    st.title("Enterprise RAG Chatbot")
    st.caption(
        "FastAPI handles ingestion and retrieval. Streamlit provides a lighter chat UI with direct streaming."
    )

    try:
        documents = get_documents()
    except requests.RequestException as exc:
        st.error(
            "Could not reach the FastAPI backend. Start `uvicorn main:app --reload` in `backend/` "
            f"and confirm `{API_BASE_URL}` is reachable. Details: {exc}"
        )
        return

    left_col, right_col = st.columns([1, 2], gap="large")
    with left_col:
        render_document_manager(documents)
    with right_col:
        render_chat(documents)


if __name__ == "__main__":
    main()
