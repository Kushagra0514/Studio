import json
import os

from groq import Groq

from .storage import VectorStorage


class RetrievalPipeline:
    def __init__(self, storage: VectorStorage):
        self.storage = storage

    def answer_question(
        self, question: str, chat_history: list = None, groq_api_key: str = None
    ) -> dict:
        if chat_history is None:
            chat_history = []

        # Use the header key if provided, otherwise let Groq() read GROQ_API_KEY from env
        api_key = groq_api_key.strip() if groq_api_key else None
        llm_client = Groq(api_key=api_key) if api_key else Groq()

        # 1. Router / Rewriter (Milestone 6)
        history_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in chat_history[-5:]]
        )

        router_prompt = (
            "You are an AI assistant orchestrating a RAG system.\n"
            "Analyze the user's latest query given the conversation history.\n"
            "Determine the intent:\n"
            "- 'CONVERSATIONAL' if it's a greeting, casual chat, or doesn't require looking up information.\n"
            "- 'LOCAL_SEARCH' if the user is asking about their uploaded documents, PDFs, or private data.\n"
            "- 'WEB_SEARCH' if the user is asking about real-time news, current events, or general world knowledge not in their documents.\n"
            "If the intent is 'LOCAL_SEARCH' or 'WEB_SEARCH', rewrite the query into a standalone search query.\n"
            "Return a JSON object with exactly two keys: 'intent' and 'query'.\n"
        )

        user_msg = f"History:\n{history_text}\n\nLatest Query: {question}"

        print("Calling LLM Router (openai/gpt-oss-20b)...")
        try:
            router_response = llm_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": router_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            route_data = json.loads(router_response.choices[0].message.content)
            intent = route_data.get("intent", "LOCAL_SEARCH")
            search_query = route_data.get("query", question)
            # Normalization fallback
            if intent not in ["CONVERSATIONAL", "LOCAL_SEARCH", "WEB_SEARCH"]:
                intent = "LOCAL_SEARCH"
        except Exception as e:
            print(f"Router failed: {e}")
            intent = "LOCAL_SEARCH"
            search_query = question

        if intent == "CONVERSATIONAL":
            print("Intent is CONVERSATIONAL. Bypassing search.")
            conv_msgs = [
                {
                    "role": "system",
                    "content": "You are a helpful, friendly AI assistant.",
                }
            ]
            for msg in chat_history[-5:]:
                conv_msgs.append(msg)
            conv_msgs.append({"role": "user", "content": question})

            conv_response = llm_client.chat.completions.create(
                model="openai/gpt-oss-20b", messages=conv_msgs, temperature=0.7
            )
            return {"answer": conv_response.choices[0].message.content, "sources": []}

        # 2. Search Execution (Web vs Local)
        if not search_query or search_query.strip() == "":
            search_query = question

        from qdrant_client.models import ScoredPoint

        results = []

        if intent == "WEB_SEARCH":
            print(f"Intent is WEB_SEARCH. Searching the web for: '{search_query}'")
            try:
                from firecrawl import FirecrawlApp

                api_key = os.getenv("FIRECRAWL_API_KEY", "local_dummy_key")
                api_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")
                app = FirecrawlApp(api_key=api_key, api_url=api_url)

                fc_results = app.search(search_query)
                web_results = getattr(fc_results, "web", []) or []

                for i, r in enumerate(web_results[:10]):
                    results.append(
                        ScoredPoint(
                            id=f"web-{i}",
                            version=0,
                            score=1.0,
                            payload={
                                "text": f"Title: {r.title}\nSnippet: {r.description}",
                                "source": r.url,
                            },
                        )
                    )

                if not results:
                    raise ValueError("No web results found.")
            except Exception as e:
                print(f"Web search failed ({e}). Falling back to LOCAL_SEARCH.")
                intent = "LOCAL_SEARCH"

        if intent == "LOCAL_SEARCH":
            print(f"Intent is LOCAL_SEARCH. Searching Qdrant for: '{search_query}'")
            results = self.storage.search(search_query, limit=10)

        # 3. Lost-in-the-middle reordering (Milestone 6)
        reordered_results = []
        left = []
        right = []
        for i, res in enumerate(results):
            if i % 2 == 0:
                left.append(res)
            else:
                right.insert(0, res)
        reordered_results = left + right

        # Keep track of original 1-based index for correct citation rendering
        citation_mapping = {id(res): idx + 1 for idx, res in enumerate(results)}

        # 4. Context Builder
        context_parts = []
        for res in reordered_results:
            payload = res.payload or {}
            text = payload.get("text", "")
            source = payload.get("source", "Unknown Source")
            pages = payload.get("pages", [])
            page_str = f' page="{pages}"' if pages else ""

            citation_id = citation_mapping[id(res)]

            # XML Structure for better citation
            context_part = f'<document id="{citation_id}" source="{source}"{page_str}>\n{text}\n</document>'
            context_parts.append(context_part)

        context_str = "\n\n".join(context_parts)

        system_prompt = (
            "You are a precise, helpful assistant. Answer the user's question using ONLY the provided context.\n"
            "You must cite your sources using bracketed document ids inline (e.g., [1], [2]).\n"
            "At the end of your response, you MUST include a 'References' section that lists the full document source and page number for each citation.\n"
            "Example format:\n"
            "The cost of attendance is $10,000 [1].\n\n"
            "References:\n"
            "[1] Cost_of_Attendance.pdf - Page 42"
        )

        user_message = f"Context information is below.\n\n{context_str}\n\nQuestion: {search_query}"

        print("Calling LLM (openai/gpt-oss-120b)...")
        response = llm_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
        )

        return {"answer": response.choices[0].message.content, "sources": results}
