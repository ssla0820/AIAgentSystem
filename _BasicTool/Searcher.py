import json
import faiss
import os
from sentence_transformers import SentenceTransformer

class SearchBase:
    def __init__(self, json_path, faiss_path, force_update=False):
        self.json_path = json_path
        self.faiss_path = faiss_path
        self.data = self._load_data()
        self.index, self.model, self.descriptions = self._load_or_build_faiss_index(force_update)

    def _load_data(self, filtered_path=None):
        """Load data from JSON file."""
        if filtered_path: # for filtered page functions
            json_path = filtered_path
        else:
            json_path = self.json_path

        with open(json_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def _load_or_build_faiss_index(self, force_update):
        """Load FAISS index from file if exists, otherwise build and save."""
        model = SentenceTransformer('all-MiniLM-L6-v2')
        descriptions = self._get_descriptions()
        descriptions = [" ".join(desc) if isinstance(desc, list) else desc for desc in descriptions]
        
        if not descriptions:
            raise ValueError("No valid descriptions found!")
        
        if os.path.exists(self.faiss_path) and not force_update:
            print(f"[INFO] Loading FAISS index from {self.faiss_path}")
            index = faiss.read_index(self.faiss_path)
        else:
            print(f"[INFO] Building FAISS index and saving to {self.faiss_path}")
            embeddings = model.encode(descriptions, convert_to_numpy=True)
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatIP(dimension)
            faiss.normalize_L2(embeddings)
            index.add(embeddings)
            faiss.write_index(index, self.faiss_path)
        
        return index, model, descriptions

    def _get_descriptions(self):
        """Extract descriptions from data, implemented in subclasses."""
        raise NotImplementedError

    def _determine_top_k(self, max_similarity, descriptions=None, is_page_function=False):
        """Dynamically adjust top_k based on the highest similarity score and description content."""
        top_k = 3
        
        # 如果是 page function，並且 description 中包含 "and" or ">"，則 top_k+2
        if is_page_function and descriptions and any("and" in desc.lower() or ">" in desc.lower() for desc in descriptions):
            top_k = 1 if max_similarity > 0.6 else 3 if max_similarity > 0.4 else 5 if max_similarity > 0.2 else 7 if max_similarity > 0.1 else 10
            top_k += 2
        
        return top_k

    def extract_relevant_items(self, query, top_k=10, debug_mode=False, is_page_function=False):
        """Find relevant items using FAISS with cosine similarity filtering."""
        relevant_items = []
        seen_items = set()

        query_embedding = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_embedding)
        distances, indices = self.index.search(query_embedding, top_k)

        max_similarity = max(distances[0]) if len(distances[0]) > 0 else 0
        descriptions = [self.descriptions[i] for i in indices[0] if i >= 0 and i < len(self.data)]
        top_k = self._determine_top_k(max_similarity, descriptions, is_page_function)
        distances, indices = self.index.search(query_embedding, top_k)

        if is_page_function:
            similarity_threshold = 0.4
        else:
            similarity_threshold = 0.0

        if debug_mode:
            print(f"\n[DEBUG] Query: {query}, Adjusted top_k: {top_k}")
            for i, dist in zip(indices[0], distances[0]):
                if i >= 0 and i < len(self.data):
                    print(f"  - {self.data[i]['name']} (Similarity: {dist:.4f})")
            return []

        for i, dist in zip(indices[0], distances[0]):
            if dist < similarity_threshold:
                continue
            if i >= 0 and i < len(self.data):
                item_data = self.data[i]
                if item_data["name"] not in seen_items:
                    seen_items.add(item_data["name"])
                    if is_page_function:
                        relevant_items.append({
                            "name": item_data["name"], 
                            "description": item_data.get("description", []),
                        })
                    else:
                        relevant_items.append({
                            "name": item_data["name"], 
                            "tags": item_data.get("tags", []),
                            "marked_name": item_data.get("marked_name", ""),
                            "description": item_data.get("description", []),
                            "full_code": item_data.get("full_code", "")
                    })
        return relevant_items if relevant_items else None