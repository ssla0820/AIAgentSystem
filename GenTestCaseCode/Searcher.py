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

    def _load_data(self):
        """Load data from JSON file."""
        with open(self.json_path, 'r', encoding='utf-8') as file:
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

        if debug_mode:
            print(f"\n[DEBUG] Query: {query}, Adjusted top_k: {top_k}")
            for i, dist in zip(indices[0], distances[0]):
                if i >= 0 and i < len(self.data):
                    print(f"  - {self.data[i]['name']} (Similarity: {dist:.4f})")
            return []

        for i, dist in zip(indices[0], distances[0]):
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
        return relevant_items

class SearchPageFunctions(SearchBase):
    def __init__(self, json_path, faiss_path, force_update=False):
        super().__init__(json_path, faiss_path, force_update=force_update)
        self.whitelist_exclusions = [" and check preview", "Check preview", " and screenshot", "screenshot"]
        self.default_functions = [
            {"name": "main_page.snapshot(locator, file_name=None)", "description": "[Action] Snapshot"},
            {"name": "main_page.compare(source_path, target_path, similarity=0.95, color=False)", "description": "[Action] Compare Images"},
            {"name": "self.ensure_dependency(dependency_test)", "description": "Ensure the dependency test is run and passed"},
            {"name": "main_page.right_click()", "description": "[Action] Right Click"},
            {"name": "main_page.select_right_click_menu(s*arg, return_elem=False, click_it=True, return_is_selected=False)", "description": "[Action] Select right click menu"},
            {"name": "main_page.click(locator, btn='left', times=1)", "description": "[Action] Click Element"},
            {"name": "main_page.Check_PreviewWindow_is_different(area=None, sec=1)", "description": "[Action][Base_page] Check if the preview window is different"},
            {"name": "self.open_packed_project(project_name, save_name)", "description": "[Action] Open packed project"},
            {"name": "self.open_recent_project(project_name, save_name)", "description": "[Action] Open Recent Project"},
        ]

    def _get_descriptions(self):
        """Get descriptions for page functions."""
        return [func["description"] for func in self.data]
    
    def _regular_step(self, step):
        step = step.strip()
        if not step:
            return ''
        
        # 移除步驟編號並去除白名單關鍵字及其後面的內容
        if ". " in step:
            step = step.split(". ", 1)[1].strip()
        
        for exclusion in self.whitelist_exclusions:
            if exclusion.lower() in step.lower():
                step = step.split(exclusion, 1)[0].strip()
        return step

    def extract_relevant_functions_step_by_step(self, test_steps, debug_mode=False):
        """Extract relevant functions step by step, applying whitelist filtering."""
        relevant_functions = self.default_functions
        seen_functions = set()

        for step in test_steps.split("\n"):
            print(step)
            step = self._regular_step(step)

            if not step:
                print(f"[INFO] Skipping step due to whitelist exclusion.")
                continue
            
            relevant_items = self.extract_relevant_items(step, debug_mode=debug_mode, is_page_function=True)
            
            for item in relevant_items:
                func_tuple = (item["name"], item["description"])
                if func_tuple not in seen_functions:
                    seen_functions.add(func_tuple)
                    relevant_functions.append(item)

        return relevant_functions

class SearchTestCases(SearchBase):
    def _get_descriptions(self):
        """Get descriptions for test cases."""
        return [" ".join(tc["description"]) if isinstance(tc["description"], list) else tc["description"] for tc in self.data]

    def extract_relevant_test_cases(self, test_steps, debug_mode=False):
        """Find relevant test cases using FAISS with cosine similarity filtering."""
        return self.extract_relevant_items(test_steps, debug_mode=debug_mode)

if __name__ == "__main__":
    test_steps = """1. Select Layout 10 and screenshot (locator=L.video_collage_designer.media_library)
    2. Check preview is changed after select layout 10
    3. Switch to Color Boards by select category (3) and screenshot (locator=L.video_collage_designer.media_library)
    4. Check preview is changed after switch to Color Boards
    5. Insert Blue Color Board and click auto fill
    6. Check preview is changed after insert Blue Color Board
    7. Switch to [Video Only] by select category (1)
    8. import media ('Skateboard 01.mp4') and click auto fill
    9. Check preview (locator=L.video_collage_designer.main_window) as GT (L244.png)"""

    # 測試 Page Functions
    page_function_search = SearchPageFunctions("page_functions_temp.json", "page_functions_temp.faiss")
    matched_functions = page_function_search.extract_relevant_functions_step_by_step(test_steps)

    # 測試 Test Cases
    test_case_search = SearchTestCases("test_cases_temp.json", "test_cases_temp.faiss")
    matched_test_cases = test_case_search.extract_relevant_test_cases(test_steps)

    # 顯示結果
    print("\nRelevant Page Functions:")
    print(matched_functions)
    print(len(matched_functions))

    print("\nRelevant Test Cases:")
    print(json.dumps(matched_test_cases, indent=2, ensure_ascii=False))
