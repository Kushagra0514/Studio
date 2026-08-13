import json
import csv
from datetime import datetime
from storage import VectorStorage
from retrieval import RetrievalPipeline
import os
from groq import Groq

def calculate_mrr(expected_source, results):
    """Mean Reciprocal Rank: 1/rank of the first relevant document."""
    for i, res in enumerate(results):
        payload = res.payload or {}
        # Simple substring match for the source filename
        if expected_source.lower() in payload.get("source", "").lower():
            return 1.0 / (i + 1)
    return 0.0

def llm_judge(client, question, expected, actual):
    """Uses the LLM to score the actual answer against the expected answer."""
    prompt = f"""You are an impartial judge evaluating a RAG system.
Question: {question}
Expected Answer (Golden Truth): {expected}
Actual System Answer: {actual}

Rate the Actual System Answer strictly from 1 to 5 based on how well it matches the facts in the Expected Answer.
1 = Completely incorrect or irrelevant
5 = Perfectly captures the required information

Output ONLY a single integer (1, 2, 3, 4, or 5). Do not output any other text or reasoning."""
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        score_text = response.choices[0].message.content.strip()
        # Extract just the first digit in case the LLM ignored instructions
        score = int(''.join(filter(str.isdigit, score_text))[0])
        return min(max(score, 1), 5)
    except Exception as e:
        print(f"[Judge Error: {e}] defaulting to 1")
        return 1

def main():
    # Automatically generate a sample dataset if one doesn't exist
    if not os.path.exists("dataset.json"):
        print("Creating a sample dataset.json...")
        sample_data = [
            {
                "question": "What is the cost of attending for undergrads?",
                "expected_answer": "The regular 8-week session is $6,868.00 and the July 4-week session is $3,477.00.",
                "expected_source": "Cost_of_Attendance.pdf"
            }
        ]
        with open("dataset.json", "w") as f:
            json.dump(sample_data, f, indent=4)
            
    with open("dataset.json", "r") as f:
        dataset = json.load(f)
        
    print(f"Loading system and starting evaluation on {len(dataset)} questions...\n")
    storage = VectorStorage()
    pipeline = RetrievalPipeline(storage)
    groq_client = Groq()
    
    total_mrr = 0.0
    hits = 0
    total_llm_score = 0.0
    
    for i, item in enumerate(dataset):
        q = item["question"]
        expected_ans = item["expected_answer"]
        expected_src = item["expected_source"]
        
        print(f"\n--- Evaluating Q{i+1}: '{q}' ---")
        
        # 1. Test Retrieval
        results = storage.search(q, limit=5)
        mrr = calculate_mrr(expected_src, results)
        total_mrr += mrr
        if mrr > 0:
            hits += 1
            
        # 2. Test Generation
        response = pipeline.answer_question(q)
        actual_ans = response.get("answer", "")
        
        # 3. LLM as a judge
        score = llm_judge(groq_client, q, expected_ans, actual_ans)
        total_llm_score += score
        
        print(f"> Retrieval Hit: {mrr>0} (MRR: {mrr:.2f}) | Judge Score: {score}/5")

    # Final calculations
    n = len(dataset)
    avg_hit_rate = hits / n
    avg_mrr = total_mrr / n
    avg_score = total_llm_score / n
    
    print("\n" + "="*30)
    print("=== EVALUATION RESULTS ===")
    print("="*30)
    print(f"Hit Rate:  {avg_hit_rate:.2%}")
    print(f"MRR:       {avg_mrr:.2f}")
    print(f"Avg Score: {avg_score:.2f} / 5.0")
    
    # Save to history CSV file
    history_file = "eval_history.csv"
    file_exists = os.path.exists(history_file)
    
    with open(history_file, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Total Questions", "Hit Rate", "MRR", "Avg LLM Score"])
        
        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
        writer.writerow([timestamp, n, round(avg_hit_rate, 4), round(avg_mrr, 4), round(avg_score, 4)])
        
    print(f"\n✅ Results appended to {history_file}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
