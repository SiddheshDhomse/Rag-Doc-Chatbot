import requests
import json

def generate_response_stream(context, question):
    if not context or not context.strip():
        yield "No relevant context was found for this question."
        return

    prompt = f"""
    Answer ONLY from the provided context.
    If the question asks for all records/items/students, return all relevant rows present in the context and do not arbitrarily limit to a few entries.
    If data is missing in context, say it clearly.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """
    try:
        with requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": True
            },
            stream=True,
            timeout=120
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    payload = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                if "response" in payload:
                    yield payload["response"]
    except requests.RequestException:
        yield "The local LLM service is unavailable right now. Please make sure Ollama is running and try again."
