import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from backend.app.storage import VectorStorage

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = REPOSITORY_ROOT / "dataset.json"


def generate_qa_pairs(client, chunk_text, source_name):
    prompt = f"""You are a synthetic data generator. Your task is to generate 2 distinct Question and Answer pairs based ONLY on the provided text chunk.

Text Chunk:
{chunk_text}

Output the 2 Q&A pairs in the following exact format. Do not include any other text or reasoning.
Q1: [Question]
A1: [Answer]
Q2: [Question]
A2: [Answer]"""

    response = client.chat.completions.create(
        # We'll use the 120b model here as well for high-quality synthetic data
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,  # Slight randomness for variety
    )

    text = response.choices[0].message.content.strip()

    pairs = []
    # Parse the LLM output
    q_pattern = r"Q\d:\s*(.*)"
    a_pattern = r"A\d:\s*(.*)"

    questions = re.findall(q_pattern, text)
    answers = re.findall(a_pattern, text)

    for q, a in zip(questions, answers):
        pairs.append(
            {
                "question": q.strip(),
                "expected_answer": a.strip(),
                "expected_source": source_name,
            }
        )

    return pairs


def main():
    load_dotenv()
    storage = VectorStorage()
    groq_client = Groq()

    print("Fetching chunks from the local Qdrant database...")
    # Scroll to get chunks directly from the DB
    response = storage.client.scroll(
        collection_name=storage.collection_name,
        limit=10,  # Limit to 10 chunks so we don't blow up the API
        with_payload=True,
    )

    points = response[0]
    if not points:
        print(
            "No chunks found in the database. Please run 'python -m scripts.rag_cli ingest <pdf>' first."
        )
        return

    print(f"Generating synthetic questions from {len(points)} chunks...\n")

    dataset = []

    for i, point in enumerate(points):
        text = point.payload.get("text", "")
        source = point.payload.get("source", "Unknown Source")

        # Skip empty or very short chunks
        if len(text.strip()) < 50:
            continue

        print(f"Processing chunk {i + 1}/{len(points)} (Source: {source})...")

        try:
            qa_pairs = generate_qa_pairs(groq_client, text, source)
            dataset.extend(qa_pairs)
        except Exception as e:
            print(f"  Error generating QA for chunk {i + 1}: {e}")

    print(f"\nGenerated {len(dataset)} total Q&A pairs.")

    # Load existing dataset if it exists to append to it
    if os.path.exists(DATASET_PATH):
        try:
            with open(DATASET_PATH, "r") as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing = []
        # Filter out the hardcoded sample if it's in there
        existing = [
            item
            for item in existing
            if item.get("question") != "What is the cost of attending for undergrads?"
        ]
        dataset = existing + dataset

    with open(DATASET_PATH, "w") as f:
        json.dump(dataset, f, indent=4)

    print("✅ Synthetic dataset successfully saved to dataset.json!")


if __name__ == "__main__":
    main()
