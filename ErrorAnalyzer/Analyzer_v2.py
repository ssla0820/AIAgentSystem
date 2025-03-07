import sys
import os
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector

from sentence_transformers import SentenceTransformer, util

class ErrorAnalyzer:
    def __init__(self, fail_case, flow_changed_func, ap_fail_reasons, at_fail_reasons):
        self.fail_case = fail_case
        self.flow_changed_func = flow_changed_func
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.ap_fail_reasons = ap_fail_reasons
        self.at_fail_reasons = at_fail_reasons
        self.chat_api_connector = ChatAPIConnector()


    def _generate_prompt(self):
        """根據失敗測試案例生成詳細的 prompt。""" # 將多行 log 組合成一個字串（可根據需求進行格式調整） 
        error_log = "\n".join(self.fail_case.get("test_log", [])) 
        ap_fail_str = "\n".join(self.ap_fail_reasons)
        at_fail_str = "\n".join(self.at_fail_reasons)

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


    def _ask_llm(self):
        system_role_msg = "You are an expert in analyzing auto testing failures. Your task is to examine error logs, test case code, and screenshots to determine the single most likely cause of failure. Categorize the error as either an AP Fail (application issue) or an AT Fail (automation script issue). Provide a concrete fix based on your analysis."
        self.error_reason = self.chat_api_connector.generate_chat_response(self.prompt, system_role_msg)


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


    def analysis_process(self):
        self._generate_prompt()
        self._ask_llm()
        self._reorganize_error_reason()

        return self.organized_error_reason

    

if __name__ == "__main__":
    fail_case = {}
    flow_changed_func = None

    import configparser

    CONFIG_FILE = r'E:\Debby\9_Scripts\AIAgentSystem\app.config'
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option  # preserve case
    config.read(CONFIG_FILE)


    AP_FAIL_REASONS = [item.strip() for line in config.get('General', "AP_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]
    AT_FAIL_REASONS = [item.strip() for line in config.get('General', "AT_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]

    error_analyzer = ErrorAnalyzer(fail_case, flow_changed_func, AP_FAIL_REASONS, AT_FAIL_REASONS)
    error_analyzer.analysis_process()




