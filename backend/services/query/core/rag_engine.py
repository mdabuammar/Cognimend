# Universal RAG imports
import re
import os
import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None

# Initialize embeddings with OpenAI (uses OPENAI_API_KEY env var)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Connect to Qdrant vector store
if QDRANT_AVAILABLE:
    qdrant_client = QdrantClient(
        host=os.getenv("QDRANT_HOST", "localhost"),
        port=int(os.getenv("QDRANT_PORT", "6333"))
    )
else:
    qdrant_client = None


@dataclass
class Document:
    page_content: str
    metadata: Dict[str, Any] = None


class MaxConfidenceRAG:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300, chunk_overlap=75,
            separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""]
        )
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.05)
        self.rerank_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

    async def generate_query_variations(self, question: str) -> List[str]:
        """Generate 3 variations of the question for multi-query retrieval"""
        prompt = f"""Generate 3 different versions of this question to improve search:
Question: {question}

Return ONLY 3 variations, one per line, no numbering:"""
        
        response = await self.llm.ainvoke(prompt)
        variations = [q.strip() for q in response.content.strip().split('\n') if q.strip()]
        return [question] + variations[:3]  # Original + up to 3 variations

    async def retrieve_with_multi_query(self, question: str, top_k: int = 15) -> List[Document]:
        """Retrieve documents using multiple query variations"""
        if not qdrant_client:
            return []
        
        # Generate query variations
        queries = await self.generate_query_variations(question)
        
        all_docs = {}
        for q in queries:
            # Get embedding for query
            query_embedding = await embeddings.aembed_query(q)
            
            # Search Qdrant
            results = qdrant_client.search(
                collection_name="documents",
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=0.72
            )
            
            # Deduplicate by content
            for r in results:
                content = r.payload.get("text", "")
                if content not in all_docs:
                    all_docs[content] = Document(
                        page_content=content,
                        metadata={"score": r.score, **r.payload}
                    )
        
        return list(all_docs.values())

    async def ultimate_query(self, question: str):
        # 1. MULTI-QUERY RETRIEVAL (3 variations)
        docs = await self.retrieve_with_multi_query(question, top_k=15)

        if not docs:
            return {
                "answer": "No relevant documents found.",
                "confidence": 0,
                "sources": [],
                "status": "no_results"
            }

        # 2. RERANK with LLM
        reranked = await self.rerank_docs(docs, question)
        filtered = [d["doc"] for d in reranked if d["score"] > 0.72]

        if not filtered:
            filtered = [d["doc"] for d in reranked[:5]]  # Fallback to top 5

        # 3. CONFIDENCE-GENERATING PROMPT
        context = ' '.join([d.page_content for d in filtered[:5]])
        prompt = f"""CONTEXT (use ONLY this):
{context}

QUESTION: {question}

Answer precisely using ONLY the context above. 
If context insufficient, say "Insufficient context".
End with: "Confidence: XX%" where XX is your certainty (0-100)."""

        # 4. GENERATE WITH BEST MODEL
        response = await self.llm.ainvoke(prompt)

        confidence = self.extract_confidence(response.content)
        return {
            "answer": response.content,
            "confidence": confidence,
            "sources": [{"content": d.page_content, "metadata": d.metadata} for d in filtered[:5]],
            "status": "success"
        }

    async def rerank_docs(self, docs: List[Document], question: str) -> List[Dict]:
        """LLM re-ranks documents by relevance"""
        scored_docs = []
        
        for doc in docs:
            score_prompt = f"""Rate relevance 0.0 to 1.0:
Question: {question}
Document: {doc.page_content[:300]}

Return ONLY a number between 0.0 and 1.0:"""
            
            try:
                score_response = await self.rerank_llm.ainvoke(score_prompt)
                score_text = score_response.content.strip()
                # Extract float from response
                score_match = re.search(r"(\d+\.?\d*)", score_text)
                score = float(score_match.group(1)) if score_match else 0.5
                score = min(max(score, 0.0), 1.0)  # Clamp to [0,1]
            except Exception:
                score = 0.5
            
            scored_docs.append({"doc": doc, "score": score})

        return sorted(scored_docs, key=lambda x: x['score'], reverse=True)

    def extract_confidence(self, answer: str) -> float:
        """Extract confidence % from answer string"""
        match = re.search(r"Confidence:\s*(\d+)%", answer, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return 50.0  # Default confidence if not found
