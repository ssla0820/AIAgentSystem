import json
from sentence_transformers import SentenceTransformer, util

import sys
import os
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)
from _BasicTool.Searcher import SearchBase


class SearchPageFunctions(SearchBase):
    def __init__(self, json_path, faiss_path, filtered_path, force_update=False):
        super().__init__(json_path, faiss_path, force_update=force_update)
        self.filtered_path = filtered_path
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

        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def _get_descriptions(self, data=None):
        """Get descriptions for page functions."""
        if data is None:
            data = self.data
        return [func["description"] for func in data]
    
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

    def _get_related_pages_from_step(self, step, similarity_threshold=0.4):
        # Load JSON file containing page descriptions.
        with open(self.json_path, 'r', encoding='utf-8') as f:
            try:
                pages = json.load(f)
            except json.decoder.JSONDecodeError as e:
                print("Error decoding JSON:", e)
                return []
        
        related_pages = []
        
        # Get embedding for the step
        step_embedding = self.model.encode(step, convert_to_tensor=True)
        
        # Handle pages as a list of dictionaries
        for page_info in pages:
            # Assuming each page_info has a 'page' key and a 'description' key
            page = page_info.get("page", "")
            description = page_info.get("description", "")
            
            if not description:
                continue
            
            # Compute embedding for the page description
            desc_embedding = self.model.encode(description, convert_to_tensor=True)
            similarity = util.pytorch_cos_sim(step_embedding, desc_embedding).item()
            
            if similarity >= similarity_threshold:
                if page not in related_pages:
                    # This is a bug in your original code: 
                    # related_pages.append[page] should be related_pages.append(page)
                    related_pages.append(page)
        
        return related_pages
    
    def _reload_filtered_data_to_extract_relevant(self, related_pages):
        if 'main_page' not in related_pages:
            related_pages.append('main_page')

        # Load the functions from the JSON file
        with open(self.json_path, "r", encoding="utf-8") as f:
            functions = json.load(f)

        # Filter functions whose name starts with any of the related pages
        related_functions = [
            func for func in functions
            if any(func["name"].startswith(page) for page in related_pages)
        ]

        # Dump the filtered functions to a new JSON file
        with open(self.filtered_path, "w", encoding="utf-8") as f:
            json.dump(related_functions, f, indent=4)

        self._load_data(filtered_path=self.filtered_path)
        self._load_or_build_faiss_index(True)


    def extract_relevant_functions_step_by_step(self, step, debug_mode=False):
        """Extract relevant functions step by step, applying whitelist filtering."""
        relevant_functions = self.default_functions
        seen_functions = set()

        # for step in test_steps.split("\n"):
            # print(step)
        step = self._regular_step(step)

        if not step:
            # print(f"[INFO] Skipping step due to whitelist exclusion.")
            return []
        
        related_pages = self._get_related_pages_from_step(step)
        if not related_pages:
            # print(f"[INFO] No related pages found for step: {step}")
            return None
        
        self._reload_filtered_data_to_extract_relevant(related_pages)

        relevant_items = self.extract_relevant_items(step, debug_mode=debug_mode, is_page_function=True)
        if not relevant_items:
            # print(f"[INFO] No relevant functions found for step: {step}")
            return None
        
        for item in relevant_items:
            func_tuple = (item["name"], item["description"])
            if func_tuple not in seen_functions:
                seen_functions.add(func_tuple)
                relevant_functions.append(item)

        return relevant_functions if relevant_functions else None
    


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

    # Directory for page functions, containing related scripts or resources
    PAGE_FUNCTIONS_PATH = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\refer_data\page_function"
    # Path to store the JSON file with formatted page functions information
    PAGE_FUNCTIONS_JSON_PATH = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\page_functions.json"
    # Path to store the JSON file with the filtered page functions information
    PAGE_FUNCTIONS_FILTERED_JSON_PATH = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\page_functions_filtered.json"
    # Path to the FAISS index file for page functions vectors
    PAGE_FUNCTIONS_FAISS_PATH = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\page_functions_filtered.faiss"

    # 測試 Page Functions
    page_function_search = SearchPageFunctions(PAGE_FUNCTIONS_JSON_PATH, PAGE_FUNCTIONS_FAISS_PATH, PAGE_FUNCTIONS_FILTERED_JSON_PATH)
    matched_functions = page_function_search.extract_relevant_functions_step_by_step(test_steps)

    # 測試 Test Cases

    # 顯示結果
    print("\nRelevant Page Functions:")
    print(matched_functions)
    print(len(matched_functions))

    # print("\nRelevant Test Cases:")
    # print(json.dumps(matched_test_cases, indent=2, ensure_ascii=False))
