"""
Handbook retrieval module (RAG) for the Student Support Agent.
Uses TF-IDF for lightweight document retrieval.
Loads, chunks, and indexes the student handbook for semantic search.
"""

import os
import re
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from config import HANDBOOK_PATH

logger = logging.getLogger(__name__)


def load_and_chunk_handbook(path=None):
    """Load the student handbook and split into retrieval chunks.
    
    Splits by markdown sections (## headers), preserving section metadata.
    
    Args:
        path: Path to the handbook file. Defaults to HANDBOOK_PATH.
        
    Returns:
        list[dict]: List of chunks with 'text', 'section', 'chunk_id'.
    """
    handbook_path = path or HANDBOOK_PATH
    
    if not os.path.exists(handbook_path):
        logger.error(f"Handbook not found at: {handbook_path}")
        return []
    
    with open(handbook_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split by section headers (## level)
    sections = re.split(r'\n(?=## )', content)
    
    chunks = []
    chunk_id = 0
    
    for section in sections:
        # Extract section title
        lines = section.strip().split('\n')
        title = lines[0].strip().lstrip('#').strip() if lines else "Unknown Section"
        text = section.strip()
        
        # Skip very short sections (likely just headers)
        if len(text) < 50:
            continue
        
        # For large sections, split by subsections (### level)
        subsections = re.split(r'\n(?=### )', text)
        
        if len(subsections) > 1:
            for subsection in subsections:
                sub_lines = subsection.strip().split('\n')
                sub_title = sub_lines[0].strip().lstrip('#').strip() if sub_lines else title
                sub_text = subsection.strip()
                
                if len(sub_text) < 30:
                    continue
                
                chunks.append({
                    "text": sub_text,
                    "section": f"{title} > {sub_title}" if sub_title != title else title,
                    "chunk_id": f"chunk_{chunk_id}"
                })
                chunk_id += 1
        else:
            chunks.append({
                "text": text,
                "section": title,
                "chunk_id": f"chunk_{chunk_id}"
            })
            chunk_id += 1
    
    logger.info(f"Loaded handbook: {len(chunks)} chunks from {handbook_path}")
    return chunks


class HandbookRetriever:
    """TF-IDF based retriever for the student handbook.
    
    Indexes handbook chunks and retrieves the most relevant ones
    for a given query using cosine similarity.
    """
    
    def __init__(self, chunks=None, handbook_path=None):
        """Initialize the retriever with handbook chunks.
        
        Args:
            chunks: Pre-loaded chunks. If None, loads from file.
            handbook_path: Path to handbook file.
        """
        self.chunks = chunks or load_and_chunk_handbook(handbook_path)
        self.vectorizer = None
        self.tfidf_matrix = None
        
        if self.chunks:
            self._build_index()
    
    def _build_index(self):
        """Build the TF-IDF index from chunks."""
        texts = [chunk["text"] for chunk in self.chunks]
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=5000,
            ngram_range=(1, 2)
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(texts)
        logger.info(f"TF-IDF index built: {self.tfidf_matrix.shape}")
    
    def retrieve(self, query, top_k=3):
        """Retrieve the most relevant chunks for a query.
        
        Args:
            query: The search query.
            top_k: Number of top results to return.
            
        Returns:
            list[dict]: Relevant chunks with 'text', 'section', 'score', 'chunk_id'.
                       Empty list if no relevant results.
        """
        if not self.chunks or self.vectorizer is None:
            logger.warning("No handbook index available for retrieval.")
            return []
        
        if not query or not query.strip():
            return []
        
        try:
            query_vector = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
            
            # Get top-k indices sorted by similarity
            top_indices = similarities.argsort()[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                score = float(similarities[idx])
                # Only include results with meaningful similarity
                if score > 0.01:
                    chunk = self.chunks[idx].copy()
                    chunk["score"] = round(score, 4)
                    results.append(chunk)
            
            logger.info(f"Retrieved {len(results)} chunks for query: '{query[:50]}...'")
            return results
            
        except Exception as e:
            logger.error(f"Retrieval error: {e}")
            return []
