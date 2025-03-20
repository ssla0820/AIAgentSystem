from _BasicTool.Searcher import SearchBase

class SearchTestCases(SearchBase):
    def _get_descriptions(self):
        """Get descriptions for test cases."""
        return [" ".join(tc["description"]) if isinstance(tc["description"], list) else tc["description"] for tc in self.data]

    def extract_relevant_test_cases(self, test_steps, debug_mode=False):
        """Find relevant test cases using FAISS with cosine similarity filtering."""
        return self.extract_relevant_items(test_steps, debug_mode=debug_mode)

