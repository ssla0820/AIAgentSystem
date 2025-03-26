import sys
import os
import json
import re
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector
from _Database.fail_reason import fail_reasons

from sentence_transformers import SentenceTransformer, util

class ErrorAnalyzer:
    def __init__(self, flow_changed_func, path_settings):
        self.flow_changed_func = flow_changed_func
        self.fail_reasons = fail_reasons
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.chat_api_connector = ChatAPIConnector()
        with open(path_settings['test_case_json'], "r", encoding="utf-8") as f:
            self.test_code_json_content = json.load(f)

        with open(path_settings['pytest_log_json_path'], "r", encoding="utf-8") as f:
            self.test_log_json_content = json.load(f)

    def _get_error_screen_shot(self):
        for line in self.fail_case_content_dict["test_log"]:
            if "Exception screenshot:" in line:
                match = re.search(r'Exception screenshot:(.*)', line)
                if match:
                    return match.group(1).strip()

    def _get_fail_case_test_code(self):
        for test_case_content in self.test_code_json_content:
            if test_case_content["name"] == self.fail_case_content_dict["test_name"]:
                return test_case_content["full_code"]

    def _generate_prompt(self):
        """根據失敗測試案例生成詳細的 prompt。""" # 將多行 log 組合成一個字串（可根據需求進行格式調整） 
        error_log = "\n".join(self.fail_case_content_dict.get("test_log", [])) 
        fail_str = ''
        for key, value in self.fail_reasons.items():
            fail_str += f" - Error Message: [{key}]:\n"
            for sub_key, sub_value in value.items():
                for sub_sub_key, sub_sub_value in sub_value.items():
                    fail_str += f"    o [{sub_key}][{sub_sub_key}]  {sub_sub_value}\n"
               
        fail_test_code = self._get_fail_case_test_code()

        prompt = f'''
Analyze the provided error log, screenshot, and test case code to identify the single most likely error reason for the auto testing failure.

Steps to Follow:
 - Review the Error Log: Examine the details in the error log.
 - Examine the Screenshot: Check the provided screenshot for visual clues.
 - Analyze the Test Case Code: Look over the test case code for potential issues.
 - Verify UI Components:
    Ensure that all prerequisite UI elements are visible and active before any interactions occur.
 - Image Comparison (if needed):
    Compare the two provided images to support your analysis.
 - Cross-Check Error Messages:
    Because multiple issues can produce the same error messages, refer to the provided Error Categories to match the corresponding error messages and reasons, then carefully pinpoint the actual cause of the error.
Error Categories:
{fail_str}

Additional Information:
 - Affected Functions (UI flow change): {self.flow_changed_func}

Error Log:
{error_log}

Test Code:
    {fail_test_code}

Instruction:
 - Data Analysis
    o Review the current status of the UI components, the test code, and the error log.
    o Verify that the steps provided in the test case are executed as expected.
 - Error Identification
    o Identify the most likely error cause.
    o Return only one error reason.
    o Clearly state whether the error is an AT Fail (assume AT Fail at the beginning if not in Affected Functions) or an AP Fail.
 - Proposed Fix
    o Provide a one-sentence explanation that includes both the error reason and the fix plan.
'''
        return prompt

    def _ask_llm(self, prompt, image_path=None):
        system_role_msg = "You are an expert in analyzing auto testing failures. Your task is to examine error logs, test case code, and screenshots to determine the single most likely cause of failure. Categorize the error as either an AP Fail (application issue) or an AT Fail (automation script issue). Provide a concrete fix based on your analysis."
        return self.chat_api_connector.generate_chat_response(prompt, system_role_msg, image_path=image_path)

    def _get_fail_conditions(self):
        # Using set comprehension to avoid duplicates:
        unique_subkeys = {sub_key 
                        for outer in self.fail_reasons.values() 
                        for inner in outer.values() 
                        for sub_key in inner}

        # Convert the set to a list:
        unique_subkeys_list = list(unique_subkeys)
        return unique_subkeys_list
    
    def _reorganize_error_reason(self, error_reason):
        error_types = ["AP Fail", "AT Fail"]

        error_conditions = self._get_fail_conditions()

        # 產生嵌入
        error_msg_embedding = self.model.encode(error_reason, convert_to_tensor=True)
        condition_embeddings = self.model.encode(error_conditions, convert_to_tensor=True)
        type_embeddings = self.model.encode(error_types, convert_to_tensor=True)

        # 計算相似度
        cosine_scores_condition = util.cos_sim(error_msg_embedding, condition_embeddings)
        cosine_scores_type = util.cos_sim(error_msg_embedding, type_embeddings)

        # 找到相似度最高的條件與錯誤類型
        best_match_condition_idx = cosine_scores_condition.argmax()
        selected_condition = error_conditions[best_match_condition_idx]

        best_match_type_idx = cosine_scores_type.argmax()
        selected_error_type = error_types[best_match_type_idx]

        # 整理結果
        organized_error_reason = {
            "error_type": selected_error_type,
            "error_condition": selected_condition,
            "full_error_reason": error_reason
        }

        return organized_error_reason

    def _get_detail_log_content(self, case_name):
        for test_log in self.test_log_json_content:
            if test_log["test_name"] == case_name:
                return test_log


    def analysis_process(self, case_name, image_path=None):
        self.fail_case_content_dict = self._get_detail_log_content(case_name)
        image_path = self._get_error_screen_shot()
        prompt = self._generate_prompt()
        image_path = None
        error_reason = self._ask_llm(prompt, image_path)
        organized_error_reason = self._reorganize_error_reason(error_reason)

        return organized_error_reason

    

if __name__ == "__main__":
    fail_case = {
    "test_name": "test_media_room_func_2_25",
    "test_result": "FAIL",
    "test_log": [
      "DEBUG    reportportal_client.client:client.py:635 start_test_item - ID: ed609c90-7fb3-4265-baa6-c114242480f2",
      "DEBUG    my_package:__init__.py:122 [STEP]: [Initial] Check dependency test result",
      "DEBUG    reportportal_client.client:client.py:635 start_test_item - ID: d50cc3d4-a281-4848-95c2-5dd3a86fb343",
      "DEBUG    reportportal_client.client:client.py:690 finish_test_item - ID: d50cc3d4-a281-4848-95c2-5dd3a86fb343",
      "DEBUG    my_package:__init__.py:122 [STEP]: [Action] Add new tag with name ('auto_Testing')",
      "DEBUG    reportportal_client.client:client.py:635 start_test_item - ID: 4bcd9006-36fd-49ec-8d83-38a650913372",
      "DEBUG    my_package:__init__.py:122 [STEP]: [Action][Media Room] Add new tag with name",
      "DEBUG    reportportal_client.client:client.py:635 start_test_item - ID: c4d55c3a-ee81-449c-8942-842f3df41ee4",
      "DEBUG    ATFramework:log.py:80  Fail to find element.",
      "DEBUG    ATFramework:log.py:80  Exception occurs. log=Fail to find element.",
      "DEBUG    reportportal_client.client:client.py:690 finish_test_item - ID: c4d55c3a-ee81-449c-8942-842f3df41ee4",
      "DEBUG    reportportal_client.client:client.py:690 finish_test_item - ID: 4bcd9006-36fd-49ec-8d83-38a650913372",
      "DEBUG    ATFramework:log.py:80  Exception screenshot:/Users/qadf_at/Desktop/AT/PDRMac_BFT_reportportal/SFT/report/MyReport/[Exception]test_media_room_func_2_25_360.png",
      "INFO     ATFramework.utils._report.report:report.py:412 Fail Screenshot: media_room_page.py",
      "DEBUG    ATFramework:log.py:80  Exception: Exception occurs. log=Fail to find element."
    ]
  }



    flow_changed_func = None

    import configparser

    CONFIG_FILE = r'E:\Debby\9_Scripts\AIAgentSystem\app.config'
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option  # preserve case
    config.read(CONFIG_FILE)

    image_path = r"E:\Debby\9_Scripts\AIAgentSystem\1145b03d-30b6-4f98-b4eb-5e1aaeeb07ed.png"

    # AP_FAIL_REASONS = [item.strip() for line in config.get('General', "AP_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]
    # AT_FAIL_REASONS = [item.strip() for line in config.get('General', "AT_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]

    path_settings = {
        'test_case_json': config.get('General', 'TEST_CASE_JSON_PATH'),
        'pytest_log_json_path': config.get('General', 'PYTEST_LOG_JSON_PATH'),
    }

    error_analyzer = ErrorAnalyzer(flow_changed_func, path_settings)
    result = error_analyzer.analysis_process(case_name='test_intro_room_func_3_17')
    for key, value in result.items():
        print(f"\n\n{key}: {value}")




