import os
import json

class CaseRefactor:
    def __init__(self, test_name: str, error_reason: str, path_settings: dict) -> str:
        self.test_name = test_name
        self.error_reason = error_reason
        self.test_case_json = path_settings['test_case_json']
        self.save_path = path_settings['save_path']
        self.test_code = self._get_case_content()

    def _get_case_content(self):
        with open(self.test_case_json, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)

        # Replace 'test_launch_process_1_1' with the name of your desired test case
        test_case = next((tc for tc in test_cases if tc['name'] == self.test_name), None)

        if test_case:
            return test_case['full_code']
        else:
            raise ValueError(f"Test case '{self.test_name}' not found in '{self.test_case_json}'")
            

    def _generate_prompt(self):
        prompt = F'''Given the following code snippet:
{self.test_code}

It is not functioning correctly due to:
{self.error_reason}
Modify the code to resolve the error and output only the updated code.
'''
        return prompt

    def _ask_llm(self, prompt):
        pass

    def _modify_code(self):
        pass

    def refactor_process(self):
        self._generate_prompt()


if __name__ == '__main__':
    path_settings = {
        'test_case_json': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test_cases_temp.json'),
        'save_path': os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'refactored_code.py')
    }

    refactor = CaseRefactor('test_launch_process_1_1', 'AssertionError', path_settings)
    refactor.refactor_process()
