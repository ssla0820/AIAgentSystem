import sys
import os
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector
from Extractor_v3 import ExtractorClass
from Searcher import SearchPageFunctions, SearchTestCases



class GenerateCase():
    def __init__(self, path_settings, force_update=False):
        self.force_update = force_update
        self.page_functions_json = path_settings['page_functions_json']
        self.test_case_json = path_settings['test_case_json']
        self.pytest_entire_file_path = os.path.join(path_settings['pytest_file_path'], path_settings['pytest_file_name'])
        self.extract_obj = ExtractorClass()
        self.chat_api_connector = ChatAPIConnector()
        

        if path_settings['page_functions_dir']:
            self.page_function_files = [
                os.path.join(path_settings['page_functions_dir'], f)
                for f in os.listdir(path_settings['page_functions_dir'])
                if os.path.isfile(os.path.join(path_settings['page_functions_dir'], f))
            ]

        if path_settings['test_case_dir']:
            self.test_case_files = [
                os.path.join(path_settings['test_case_dir'], f)
                for f in os.listdir(path_settings['test_case_dir'])
                if os.path.isfile(os.path.join(path_settings['test_case_dir'], f))
            ]
        
    def _extract_page_functions(self):
        if os.path.exists(self.page_functions_json) and not self.force_update:
            print(f"✅ `{self.page_functions_json}` 存在，直接載入...")
        else:
            print(f"❌ `{self.page_functions_json}` 不存在，重新解析並儲存...")
            self.page_functions = self.extract_obj.extracted_all_data("page_function", self.page_function_files, self.page_functions_json)

    def _extract_test_cases(self):
        if os.path.exists(self.test_case_json) and not self.force_update:
            print(f"✅ `{self.test_case_json}` 存在，直接載入...")
        else:
            print(f"❌ `{self.test_case_json}` 不存在，重新解析並儲存...")
            self.test_cases = self.extract_obj.extracted_all_data("test_case", self.test_case_files, self.test_case_json)

    def _search_similar_functions(self, test_steps):
        relevant_functions = self.search_page_functions_obj.extract_relevant_functions_step_by_step(test_steps)
        return relevant_functions
    
    def _search_similar_test_cases(self, test_steps):
        relevant_test_cases = self.search_test_cases_obj.extract_relevant_test_cases(test_steps)
        return relevant_test_cases
    
    def _generate_prompts(self, test_name, test_steps):
        # extract page functions and test cases from python files, if json files are not existed
        self._extract_page_functions()
        self._extract_test_cases()

        self.search_page_functions_obj = SearchPageFunctions(path_settings['page_functions_json'], path_settings['page_functions_faiss'], force_update=force_update)
        self.search_test_cases_obj = SearchTestCases(path_settings['test_case_json'], path_settings['test_case_faiss'], force_update=force_update)

        # search similar test cases and page functions
        similar_tests = self._search_similar_test_cases(test_steps)
        relevant_functions = self._search_similar_functions(test_steps)


        if not similar_tests or not relevant_functions:
            return "❌ 沒有找到足夠的參考測試案例或 Page Functions，請提供更詳細的測試步驟！"

        prompt = f"""
Generate a complete pytest test function using the given test steps.
- Include pytest.mark decorators and @exception_screenshot.
- Wrap steps in a with step() block.
- Assert True at the end of the test function.
- Not Comment #Step X: in the test steps.
- Not import any modules.
- If main_page.compare(), assert with comment metions similarity should > or < value.
- Refer to these test cases: {similar_tests}.
- Use these Page Functions: {relevant_functions}.
- Test Name: {test_name}
- Test Steps: {test_steps}
"""
        return prompt
    
    def _ask_llm(self, prompt):
        system_role_msg = "You are a helpful AI that generates pytest test functions based on provided instructions."
        return self.chat_api_connector.generate_chat_response(prompt, system_role_msg)
            
    def _generate_test(self, code):
        # add the generated test case to the end of the test case file and add @pytest.mark.generated_testing_case
        try:
            with open(self.pytest_entire_file_path, 'a') as f:
                f.write('\n\n@pytest.mark.generated_testing_case\n')
                f.write(code)
            return True
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False
        
    def generate_process(self, test_name, test_steps):
        prompt = self._generate_prompts(test_name, test_steps)
        print(f'Generated Prompt is:\n {prompt}')
        code = self._ask_llm(prompt)
        print(f'Generated code is:\n {code}')
        return self._generate_test(code)



if __name__ == '__main__':
    path_settings = {
    'page_functions_dir': r"E:\Debby\9_Scripts\AIAgentSystem\GenTestCaseCode\refer_data\page_function", # Can provide None if page_functions_json is existed
    'test_case_dir': r"E:\Debby\9_Scripts\AIAgentSystem\GenTestCaseCode\refer_data\test_case", # Can provide None if test_case_json is existed
    'page_functions_json': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page_functions_temp.json'),
    'test_case_json': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases_temp.json'),
    'page_functions_faiss': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page_functions_temp.faiss'),
    'test_case_faiss': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases_temp.faiss'),
}
    
    force_update = False

    test_name = "test_aaaaa_func_20_9"
    test_steps = """
0. Ensure the dependency test is run and passed
1. Click [Undo] button on main page > Click [Cancel] button on search library
2. Search component ('Disturbance') in library > Drag Transition ('Disturbance') to timeline clip ('Mood Stickers 07')
3. Set timecode ('00_00_00_27')
4. Check preview (locator=L.base.Area.preview.only_mtk_view, file_name=Auto_Ground_Truth_Folder + 'L66_disturbance.png')
matches GT (Ground_Truth_Folder + 'L66_disturbance.png') with similarity 0.95
"""
    gen = GenerateCase(path_settings, force_update=force_update)
    prompt = gen.generate_process(test_name, test_steps)

