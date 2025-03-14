import json
from _BasicTool.Searcher import SearchBase

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
