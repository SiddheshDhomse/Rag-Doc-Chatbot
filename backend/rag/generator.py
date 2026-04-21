import requests
import json

def generate_response_stream(context, question):
    if not context or not context.strip():
        yield "No relevant context was found for this question."
        return

    prompt = f"""
You are an enterprise document assistant.
Answer only from the provided context.
If the answer is not in the context, say that clearly.
If the user asks for a list, table, all rows, or all matching records, include every relevant item found in the context.
Keep the answer concise, but preserve important values and names exactly.

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
