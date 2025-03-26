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

                    # write json file to python file
                    with open(self.pytest_entire_file_path, 'w', encoding='utf-8') as f:
                        f.write(self.template_content)
                        for test_case_content in self.test_case_json_content:
                            f.write(f"\n\n    {test_case_content['full_code']}")
                    return True
            
            # for the case is not in the json file
            test_patterns = re.findall(
                r"((?:\s*@pytest\.mark\.[^\n]+\n\s*)+)(?:@[\w_]+\n\s*)*def (\w+)\(.*?\):\s+[\"']{3}([\s\S]+?)[\"']{3}\s*([\s\S]+?)(?=\n\s*@pytest\.mark|\Z)",
                indented_code, re.DOTALL
            )
            if not test_patterns:
                print("❌ No test cases found. Please check file format.")
                return []
            
            for full_markers, test_name, description, test_content in test_patterns:
                tags = re.findall(r"@pytest\.mark\.(\w+)", full_markers)
                marked_name_match = re.search(r"@pytest\.mark\.name\('([^']+)'\)", full_markers)
                marked_name = marked_name_match.group(1) if marked_name_match else test_name
                if "name" in tags:
                    tags.remove("name")
                description_list = [step.strip() for step in description.split("\n") if step.strip()]
                test_content_cleaned = test_content.strip()
                full_code = full_markers + f"def {test_name}(self):\n    '''{description}'''\n        " + test_content_cleaned
                self.test_case_json_content.append({
                    "name": test_name,
                    "tags": tags,
                    "marked_name": marked_name,
                    "description": description_list,
                    "full_code": indented_code
                })

            with open(self.test_case_json, 'w', encoding='utf-8') as file:
                json.dump(self.test_case_json_content, file, indent=4, ensure_ascii=False)

            # write json file to python file
            with open(self.pytest_entire_file_path, 'w', encoding='utf-8') as f:
                f.write(self.template_content)
                for test_case_content in self.test_case_json_content:
                    f.write(f"\n\n    {test_case_content['full_code']}")

            return True
        
        except Exception as e:
            print(f"Error writing to file: {e}")
            return False
        
    def generate_process(self, test_name, test_steps):
        prompt = self._generate_prompts(test_name, test_steps)
        # print(f'Generated Prompt is:\n {prompt}')
        # return prompt
        generated_code = self._ask_llm(prompt)
        # print(f'Generated code is:\n {generated_code}')
        return self._write_generated_test(test_name, generated_code)



if __name__ == "__main__":
    code = """ @pytest.mark.stock_media_func
@pytest.mark.media_room
@pytest.mark.stock_media
@pytest.mark.name('[test_sss_func_30_4] Click [Stock Media] button in the Media Room and perform actions')
@exception_screenshot
def test_sss_func_30_4(self):
    '''
    1. [Action] Click [Stock Media] button in the Media Room.
    2. [Verify] Check if the Stock Media window is opened.
    3. [Action] Select the first media in the Stock Media window.
    4. [Action] Click [Import] to add the media to the Media Room.
    5. [Verify] Confirm the media is now listed in the Media Room.
    6. [Action] Drag the imported media from the Media Room to the timeline.
    7. [Verify] Ensure the media appears on the timeline.
    '''
    # Ensure the dependency test is run and passed
    dependency_test = "test_stock_media_func_11_2"
    if not self.ensure_dependency(dependency_test):
        with step('[Initial] Launch APP and Enter Media Room'):
            if not main_page.start_app() or not main_page.is_app_exist():
                assert False, "Launch APP failed!"
            main_page.enter_room(0)

    with step('[Action] Click [Stock Media] button in the Media Room'):
        main_page.click(L.media_room.btn_stock_media)

    with step('[Verify] Check if the Stock Media window is opened'):
        assert main_page.is_exist(L.download_from_shutterstock.window, timeout=15), "Stock Media window is not opened!"

    with step('[Action] Select the first media in the Stock Media window'):
        photo.select_thumbnail_then_download(0)

    with step('[Action] Click [Import] to add the media to the Media Room'):
        main_page.click(L.stock_media.btn_import)

    with step('[Verify] Confirm the media is now listed in the Media Room'):
        assert main_page.exist(L.media_room.imported_media), "Imported media is not listed in the Media Room!"

    with step('[Action] Drag the imported media from the Media Room to the timeline'):
        main_page.drag_and_drop(L.media_room.imported_media, L.timeline.track_area)

    with step('[Verify] Ensure the media appears on the timeline'):
        assert main_page.exist(L.timeline.media_on_track), "Media does not appear on the timeline!"

    assert True"""
    
    path_settings = {
        'test_case_json': r"E:\Debby\9_Scripts\AIAgentSystem\_Database\test_cases_code.json",
        'test_case_faiss': r"E:\Debby\9_Scripts\AIAgentSystem\_Database\test_cases_code.faiss",
        'pytest_file_path': r"E:\Debby\5_ATCases\230721_Organize\PDRMac_BFT_reportportal\SFT",
        'pytest_file_name': "test_BFT_PDR23_stage1_reportportal_aiagent_testing.py",
        'pytest_template_name': "test_BFT_PDR23_stage1_template.py"
    }



    test_name = "test_sss_func_30_4"
    gen = GenerateCase([], path_settings=path_settings)
    gen._write_generated_test(test_name, code)