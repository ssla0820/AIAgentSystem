import sys
import os
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)
import re
import textwrap
import json
from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector
from TestCasePageFunctionExtractor.Extractor import TestCase_PageFunction_Extractor
from TestCodeGenerator.TestCaseSearcher import SearchTestCases



class GenerateCase():
    def __init__(self, relevant_functions, path_settings):
        self.relevant_functions = relevant_functions
        self.test_case_json = path_settings['test_case_json']
        self.test_case_faiss = path_settings['test_case_faiss']
        self.test_case_json_content = self._load_data()
        self.pytest_entire_file_path = os.path.join(path_settings['pytest_file_path'], path_settings['pytest_file_name'])
        self.template_content = self._load_template(os.path.join(path_settings['pytest_file_path'], path_settings['pytest_template_name']))
        self.chat_api_connector = ChatAPIConnector()

    def _load_data(self):
        """Load data from JSON file."""
        with open(self.test_case_json, 'r', encoding='utf-8') as file:
            return json.load(file)
        
    def _load_template(self, template_path):
        """Load template from python file """
        with open(template_path, 'r', encoding='utf-8') as file:
            return file.read()

    def _search_similar_test_cases(self, test_steps):
        relevant_test_cases = self.search_test_cases_obj.extract_relevant_test_cases(test_steps)
        return relevant_test_cases
    
    def _generate_prompts(self, test_name, test_steps):

        # self.search_page_functions_obj = SearchPageFunctions(self.page_functions_json, self.page_functions_faiss, force_update=self.force_update)
        self.search_test_cases_obj = SearchTestCases(self.test_case_json, self.test_case_faiss)

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
- In step description, Wrap values as (value) and functions as [function] exactly as shown in Test Steps.
- Not change any in Test Steps. Keep Test Steps as docstring.
- If main_page.compare(), assert with comment metions similarity should > or < value.
- In test code, only use "Page Functions" and assign a lower priority to main_page.exist() and main_page.click().
- Refer to these test cases: {similar_tests}.
- Use these Page Functions: {self.relevant_functions}.
- Test Name: {test_name}
- Test Steps: {test_steps}
"""
        return prompt
    
    def _ask_llm(self, prompt):
        system_role_msg = "You are a helpful AI that generates pytest test functions based on provided instructions."
        code = self.chat_api_connector.generate_chat_response(prompt, system_role_msg)

        pattern = r'@pytest(.*?)```'
        result = re.search(pattern, code, re.DOTALL)

        if result:
            extracted_content = '@pytest' + result.group(1)
        
        return extracted_content


    def _write_generated_test(self, test_name, code):
        try:
            # get mark list
            new_gen_mark_list = []
            for mark in re.findall(r'@pytest\.mark\.(.*?)\n', code):
                if "name(" in mark: continue
                new_gen_mark_list.append(mark)

            # Save the generated code to test case code json file
            prefix = '    '  # Four spaces

            # Indent each line of the code with the defined prefix
            indented_code = f'\n\n    @pytest.mark.generated_testing_case\n{textwrap.indent(code, prefix)}'

            print(f"Mark list: {new_gen_mark_list}")
            for test_case_content in self.test_case_json_content:
                if test_name == test_case_content['name']:
                    old_mark_list = test_case_content['tags']
                    diff_mark_list = [mark for mark in old_mark_list if mark not in new_gen_mark_list]
                    full_mark_list = list(dict.fromkeys(old_mark_list + new_gen_mark_list))

                    if diff_mark_list:
                        # Update the mark list
                        test_case_content['tags'] = full_mark_list
                        new_mark_string = "\n    ".join([
                            f"@pytest.mark.{mark}" for mark in diff_mark_list
                        ])
                        indented_code = f'\n\n    @pytest.mark.generated_testing_case\n    {new_mark_string}\n{textwrap.indent(code, prefix)}'
                    else:
                        indented_code = f'\n\n    @pytest.mark.generated_testing_case\n{textwrap.indent(code, prefix)}'

                    test_case_content['full_code'] = indented_code

                    # write back to json file
                    with open(self.test_case_json, 'w', encoding='utf-8') as file:
                        json.dump(self.test_case_json_content, file, indent=4, ensure_ascii=False)

                    break

            # write json file to python file
            with open(self.pytest_entire_file_path, 'w', encoding='utf-8') as f:
                f.write(self.template_content)
                for test_case_content in self.test_case_json_content:
                    f.write(test_case_content['full_code'])

            return True
        
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False
        
    def generate_process(self, test_name, test_steps):
        prompt = self._generate_prompts(test_name, test_steps)
        # print(f'Generated Prompt is:\n {prompt}')
        generated_code = self._ask_llm(prompt)
        # print(f'Generated code is:\n {generated_code}')
        return self._write_generated_test(test_name, generated_code)

