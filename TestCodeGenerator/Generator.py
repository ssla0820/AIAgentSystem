import sys
import os
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)
import re
from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector
# from TestCasePageFunctionExtractor.Extractor import TestCase_PageFunction_Extractor
from TestCodeGenerator.Searcher import SearchTestCases



class GenerateCase():
    def __init__(self, relevant_functions, path_settings, force_update=False):
        self.relevant_functions = relevant_functions
        self.force_update = force_update
        self.page_functions_json = path_settings['page_functions_json']
        self.page_functions_faiss = path_settings['page_functions_faiss']
        self.test_case_json = path_settings['test_case_json']
        self.test_case_faiss = path_settings['test_case_faiss']
        self.force_update = force_update
        self.pytest_entire_file_path = os.path.join(path_settings['pytest_file_path'], path_settings['pytest_file_name'])
        self.chat_api_connector = ChatAPIConnector()
        
    # def _extract_page_functions(self):
    #     if os.path.exists(self.page_functions_json) and not self.force_update:
    #         print(f"✅ `{self.page_functions_json}` 存在，直接載入...")
    #     else:
    #         print(f"❌ `{self.page_functions_json}` 不存在，重新解析並儲存...")
    #         self.page_functions = self.extract_obj.extracted_all_data("page_function", self.page_function_files, self.page_functions_json)

    # def _extract_test_cases(self):
    #     if os.path.exists(self.test_case_json) and not self.force_update:
    #         print(f"✅ `{self.test_case_json}` 存在，直接載入...")
    #     else:
    #         print(f"❌ `{self.test_case_json}` 不存在，重新解析並儲存...")
    #         self.test_cases = self.extract_obj.extracted_all_data("test_case", self.test_case_files, self.test_case_json)


    def _search_similar_functions(self, test_steps):
        relevant_functions = self.search_page_functions_obj.extract_relevant_functions_step_by_step(test_steps)
        return relevant_functions
    
    def _search_similar_test_cases(self, test_steps):
        relevant_test_cases = self.search_test_cases_obj.extract_relevant_test_cases(test_steps)
        return relevant_test_cases
    
    def _generate_prompts(self, test_name, test_steps):
        # # extract page functions and test cases from python files, if json files are not existed
        # self._extract_page_functions()
        # self._extract_test_cases()

        # self.search_page_functions_obj = SearchPageFunctions(self.page_functions_json, self.page_functions_faiss, force_update=self.force_update)
        self.search_test_cases_obj = SearchTestCases(self.test_case_json, self.test_case_faiss, force_update=self.force_update)

        # search similar test cases and page functions
        similar_tests = self._search_similar_test_cases(test_steps)
        # self.relevant_functions = self._search_similar_functions(test_steps)


        if not similar_tests or not self.relevant_functions:
            return "❌ 沒有找到足夠的參考測試案例或 Page Functions，請提供更詳細的測試步驟！"

        prompt = f"""
Generate a complete pytest test function using the given test steps.
- Include pytest.mark decorators and @exception_screenshot.
- Wrap steps in a with step() block.
- Assert True at the end of the test function.
- Not Comment #Step X: in the test steps.
- Not import any modules.
- In step description, wrap values as (value) and functions as [function].
- Not change any in Test Steps. Keep Test Steps as docstring.
- If main_page.compare(), assert with comment metions similarity should > or < value.
- Refer to these test cases: {similar_tests}.
- Use these Page Functions: {self.relevant_functions}.
- Test Name: {test_name}
- Test Steps: {test_steps}
"""
        return prompt
    
    def _ask_llm(self, prompt):
        system_role_msg = "You are a helpful AI that generates pytest test functions based on provided instructions."
        code = self.chat_api_connector.generate_chat_response(prompt, system_role_msg)
        # print(code)
#         code = """
# ```python
# @pytest.mark.agent_func
# @pytest.mark.name('[test_agent_func_21_1] Start APP')
# @exception_screenshot
# def test_agent_func_21_1(self):
#     '''
#     1. Start APP
#     '''
#     with step('[Action] Start APP'):
#         if not main_page.start_app() or not main_page.is_app_exist():
#             assert False, "Start APP failed!"

#     assert True
# ```"""
        # reorg the generated result, start from @pytest, and end before ```
        org_code = re.search(r"(@pytest.*?)(?=```\n)", code, re.DOTALL)
        # Check if a match is found
        if org_code:
            # If match is found, process the result
            result = org_code.group(1)
            print(result)
        else:
            # Handle the case where no match is found
            print("No match found!")
            
    def _write_generated_test(self, code):
        import textwrap
        # Add the generated test case to the end of the test case file
        # and add @pytest.mark.generated_testing_case
        try:
            print('Start to write test case')

            # Define the prefix to add to each line
            prefix = '    '  # Four spaces

            # Indent each line of the code with the defined prefix
            indented_code = textwrap.indent(code, prefix)

            # Open the file in append mode and write the indented code
            with open(self.pytest_entire_file_path, 'a') as f:
                f.write('\n\n    @pytest.mark.generated_testing_case\n')
                f.write(indented_code)

            return True
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False
        
    def generate_process(self, test_name, test_steps):
        prompt = self._generate_prompts(test_name, test_steps)
        print(f'Generated Prompt is:\n {prompt}')
        # generated_code = self._ask_llm(prompt)
        # print(f'Generated code is:\n {generated_code}')
        # return self._write_generated_test(generated_code)


if __name__ == '__main__':
    path_settings = {
    'page_functions_dir': "/Users/qadf_at/Desktop/AT/PDRMac_BFT_reportportal/pages", # Can provide None if page_functions_json is existed
    'test_case_dir': "/Users/qadf_at/Desktop/AT/PDRMac_BFT_reportportal/Debby_agent_test", # Can provide None if test_case_json is existed
    'page_functions_json': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page_functions_temp.json'),
    'test_case_json': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases_temp.json'),
    'page_functions_faiss': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'page_functions_temp.faiss'),
    'test_case_faiss': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_cases_temp.faiss'),
    'pytest_file_path': '/Users/qadf_at/Desktop/AT/PDRMac_BFT_reportportal/SFT',
    'pytest_file_name': 'test_BFT_PDR23_stage1_reportportal.py'
}
    
    force_update = False

    test_name = "test_bbbbb_21_1"
    test_steps = '''
1. Start the app
2. Open packed project ('Packed_Project/test_bbbbb_21_1.pdk', 'Extracted_Folder/test_bbbbb_21_1')
3. Set timecode to ('00_00_57_07')
4. Enter Room (Particle) (5) and screenshot (locator=L.base.Area.preview.only_mtk_view)
5. Search component ('Comic Style 06') in library
6. Select component ('Comic Style 06') in library icon view > Drag media ('Comic Style 06') to timeline track 1
7. Check Preview is updated (Similarity=0.98)
'''
    gen = GenerateCase(path_settings, force_update=force_update)
    prompt = gen.generate_process(test_name, test_steps)

