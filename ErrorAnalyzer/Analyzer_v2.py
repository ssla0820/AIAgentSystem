import sys
import os
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector

from sentence_transformers import SentenceTransformer, util

class ErrorAnalyzer:
    def __init__(self, fail_case, flow_changed_func, fail_reasons):
        self.fail_case = fail_case
        self.flow_changed_func = flow_changed_func
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.ap_fail_reasons = fail_reasons["AP"]
        self.at_fail_reasons = fail_reasons["AT"]
        self.chat_api_connector = ChatAPIConnector()


    def _generate_prompt(self):
        """根據失敗測試案例生成詳細的 prompt。""" # 將多行 log 組合成一個字串（可根據需求進行格式調整） 
        error_log = "\n".join(self.fail_case.get("test_log", [])) 
        # ap_fail_str = "\n".join(self.ap_fail_reasons)
        # at_fail_str = "\n".join(self.at_fail_reasons)
        ap_fail_str =''
        at_fail_str = ''

        for key, value in self.ap_fail_reasons.items():
            ap_fail_str += f"{key}: {value}\n"

        for key, value in self.at_fail_reasons.items():
            at_fail_str += f"{key}: {value}\n"

        self.prompt = f"""Analyze the provided error log, screenshot, and test case code to identify the single most likely error reason for the auto testing failure. In your answer, clearly indicate whether the error falls under AP Fail or AT Fail. Then, propose a concrete fix for the error.
Note: If necessary, analyze the two compared images to support your findings.
Possible Error Categories:
AP Fail:
{ap_fail_str}
AT Fail:
{at_fail_str}
Additional Information:
Affected Functions (UI flow change): {self.flow_changed_func}
Error Log: 
{error_log}
Instruction:
Please analyze the above details and return only one error reason (the most likely cause). In your response, include whether this is an AT Fail or an AP Fail error, and propose a concrete fix for it."""


    def _ask_llm(self, image_path=None):
        system_role_msg = "You are an expert in analyzing auto testing failures. Your task is to examine error logs, test case code, and screenshots to determine the single most likely cause of failure. Categorize the error as either an AP Fail (application issue) or an AT Fail (automation script issue). Provide a concrete fix based on your analysis."
        self.error_reason = self.chat_api_connector.generate_chat_response(self.prompt, system_role_msg, image_path=image_path)


    def _reorganize_error_reason(self):
        error_types = ["AP Fail", "AT Fail"]

        error_conditions = self.ap_fail_reasons + self.at_fail_reasons

        # 產生嵌入
        error_msg_embedding = self.model.encode(self.error_reason, convert_to_tensor=True)
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
        self.organized_error_reason = {
            "error_type": selected_error_type,
            "error_condition": selected_condition,
            "full_error_reason": self.error_reason
        }


    def analysis_process(self, image_path=None):
        self._generate_prompt()
        print(self.prompt)
        # self._ask_llm(image_path)
        # self._reorganize_error_reason()

        # return self.organized_error_reason

    

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


    fail_reasons = {
    "AP": {
        "Locator change": "Locator for element has changed.",
        "No response after an action": "No system response after action.",
        "Image comparison result is really not as expected": "Image comparison did not match expected result.",
        "UI flow change": "UI flow has changed."
    },
    "AT": {
        "Incorrect locator provided due to incorrect order of test case steps": "Locator attempted before prior steps finished.",
        "Incorrect locator provided due to locator error": "Locator is incorrect or outdated.",
        "Incorrect locator provided due to previous steps not being completed": "Previous steps not completed before locator was used.",
        "Action executed before the previous step is complete": "Action performed before prior step finished.",
        "Image comparison similarity threshold set too high or too low": "Image comparison threshold is incorrectly set.",
        "Incorrect order of test case steps": "Test case steps executed in wrong order.",
        "Interference from an upper dialog box": "Dialog box blocks interaction with element.",
        "Incorrect verify value": "Wrong verification value used."
    }
    }


    error_analyzer = ErrorAnalyzer(fail_case, flow_changed_func, fail_reasons)
    result = error_analyzer.analysis_process(image_path=image_path)
    print(result)




