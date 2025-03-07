import os
import subprocess
import openai
import configparser

from langchain.agents import tool, initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.prompts import SystemMessagePromptTemplate
from langchain.schema import HumanMessage

from GenTestCaseCode.Generator import GenerateCase
from GetFailCases.FailedCollector import FailedCollector
from ErrorAnalyzer.Analyzer_v2 import ErrorAnalyzer
from CaseRefactor.CaseRefactor import CaseRefactor

CONFIG_FILE = 'app.config'

def read_config():
    """
    Reads the app.config file and assigns each parameter from the [General]
    section to a global variable.
    """
    global PYTEST_FILE_PATH, PYTEST_FILE_NAME, PYTEST_LOG_PATH, PYTEST_LOG_JSON_PATH, \
           TEST_CASE_PATH, TEST_CASE_JSON_PATH, TEST_CASE_FAISS_PATH, \
           PAGE_FUNCTIONS_PATH, PAGE_FUNCTIONS_JSON_PATH, PAGE_FUNCTIONS_FAISS_PATH, \
           SAVE_REFACTOR_TEST_CASE_PATH, AP_FAIL_REASONS, AT_FAIL_REASONS

    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Config file '{CONFIG_FILE}' not found.")

    # Create a ConfigParser instance and preserve key case
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option  # preserve case
    config.read(CONFIG_FILE)

    # Assign variables from the "General" section
    PYTEST_FILE_PATH = config.get('General', 'PYTEST_FILE_PATH')
    PYTEST_FILE_NAME = config.get('General', 'PYTEST_FILE_NAME')
    PYTEST_LOG_PATH = config.get('General', 'PYTEST_LOG_PATH')
    PYTEST_LOG_JSON_PATH = config.get('General', 'PYTEST_LOG_JSON_PATH')
    TEST_CASE_PATH = config.get('General', 'TEST_CASE_PATH')
    TEST_CASE_JSON_PATH = config.get('General', 'TEST_CASE_JSON_PATH')
    TEST_CASE_FAISS_PATH = config.get('General', 'TEST_CASE_FAISS_PATH')
    PAGE_FUNCTIONS_PATH = config.get('General', 'PAGE_FUNCTIONS_PATH')
    PAGE_FUNCTIONS_JSON_PATH = config.get('General', 'PAGE_FUNCTIONS_JSON_PATH')
    PAGE_FUNCTIONS_FAISS_PATH = config.get('General', 'PAGE_FUNCTIONS_FAISS_PATH')
    SAVE_REFACTOR_TEST_CASE_PATH = config.get('General', 'SAVE_REFACTOR_TEST_CASE_PATH')

    # ap_fail = config.get("APFail", "ErrorReasons")
    AP_FAIL_REASONS = [item.strip() for line in config.get('General', "AP_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]
    AT_FAIL_REASONS = [item.strip() for line in config.get('General', "AT_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]


@tool(
    name="GenTestCaseCodeTool",
    description=(
        "Create a test case code file via the given test case name and test steps. "
        "Input: test_case_name (string) and test_steps (string). "
        "Output: The file path of the generated test case code."
    )
)
def gen_test_case_code_func(test_case_name: str, test_steps: str, force_update: bool) -> str:
    """
    Generate the test case code file by openai API via the given test case name and test steps.
    args:
        test_case_name: str: The name of the test case.
        test_steps: str: The test steps of the test case.
        force_update: bool: Whether to force update the generator.
    return:
        str: The file path of the generated test case code.
    """

    path_settings = {
        'page_functions_dir': PAGE_FUNCTIONS_PATH,
        'test_case_dir': TEST_CASE_PATH,
        'page_functions_json': PAGE_FUNCTIONS_JSON_PATH,
        'test_case_json': TEST_CASE_JSON_PATH,
        'page_functions_faiss': PAGE_FUNCTIONS_FAISS_PATH,
        'test_case_faiss': TEST_CASE_FAISS_PATH,
    }
    gen = GenerateCase(path_settings=path_settings, force_update=force_update)

    return gen.generate_process(test_case_name, test_steps)


@tool(
    name="RunPytestTool",
    description=(
        "Run the test case in local environment via pytest. "
        "Input: \
            file_path (string) the path of the test case file to run. \
            test_case_name (string) the name of the test case. "
        "Output: A Bool value indicates whether the test case run successfully."
    )
)
def run_pytest_func(test_case_name: str) -> dict:
    """
    Run the test case in local environment via pytest.
    args:
        test_case_name: str: The name of the test case.
    return:
        Bool: Whether the test case run successfully.
    """
    try:
        if test_case_name:
            test_path = f'{PYTEST_FILE_NAME}::{test_case_name}'
            # add "Single Test" to reportportal test name

        else:
            test_path = PYTEST_FILE_NAME

        result = subprocess.run(
            ["python3.9", "-m", "pytest", "--reportportal", "--color=yes", test_path],
            capture_output=True,
            text=True
        )
        return True
    except Exception as e:
        print(f'Error happened when executing pytest: {e}')
        return False
    

@tool(
    name="GetFailCasesTool",
    description=(
        "Get the failed test cases from the pytest result. "
        "Input: None"
        "Output: A list contains the failed test cases, log."
    )
)
def get_fail_cases_func() -> list:
    """
    Get the failed test cases from the pytest result.
    args:
        None
    return:
        list: A list contains the failed test cases, log.
    """
    collector = FailedCollector(path_setting={
        "log_path": PYTEST_LOG_PATH,
        "json_path": PYTEST_LOG_JSON_PATH
    })
    return collector.collect_process()


@tool(
    name="AnalyzeErrorTool",
    description=(
        "Analyze the pytest result to determine AP/AT error and the failure reason."
        "Input: \
            pytest_result (string) containing the result of the execution.\
            flow_changed_func (string) the function that the flow changed."
        "Output: 'AP Error' or 'AT Error' and the failure reason."
    )
)
def analysis_error_func(fail_case, flow_changed_func) -> str:
    """
    Analyze the pytest result to determine AP/AT error and the failure reason.
    args:
        fail_case: str: The failed test case.
        flow_changed_func: str: The function that the flow changed.
    return:
        str: 'AP Error' or 'AT Error' and the failure reason
    """

    error_analyzer = ErrorAnalyzer(fail_case, flow_changed_func, AP_FAIL_REASONS, AT_FAIL_REASONS)
    return error_analyzer.analysis_process()


@tool(
    name="RefactorCodeTool",
    description=(
        "Refactor the test case code based on the failure reason (AT bug). "
        "Input:\
            path_settings: dict: The path settings for the refactoring.\
            test_case_name: str: The name of the test case.\
            error_reason: str: The failure reason"
        "Output: file_path (string) the path of the refactored test case code."
    )
)
def refactor_code_func(path_settings: dict, test_case_name: str, error_reason: str) -> str:
    """
    Refactor the test case code based on the failure reason (AT bug).
    args:
        path_settings: dict: The path settings for the refactoring.
        test_case_name: str: The name of the test case.
        error_reason: str: The failure reason
    return:
        str: The path of the refactored test case code.
    """
    path_settings = {
        'test_case_json': TEST_CASE_JSON_PATH,
        'save_path': SAVE_REFACTOR_TEST_CASE_PATH
    }

    # Get the test case name and error reason from the pytest result
    refactor = CaseRefactor(test_case_name, error_reason, path_settings)
    return refactor.refactor_process()


# @tool(
#     name="ReportBugTool",
#     description=(
#         "建立 AP Bug 報告 (示範用，可整合到 Bug Tracking 系統)。"
#         "輸入: pytest_result (string) 錯誤日誌。"
#         "輸出: Bug 報告建立結果 (string)。"
#     )
# )
# def report_bug_func(pytest_result: str) -> str:
#     # 這裡僅示範輸出訊息，實際上可整合 Jira / GitHub Issue 等系統
#     return f"AP Bug 已回報。錯誤日誌如下：\n{pytest_result}"

# -----------------------------
# 2. 建立 LLM 與 Agent
# -----------------------------

# 使用 ChatOpenAI 作為 LLM
llm = ChatOpenAI(
    model_name="gpt-3.5-turbo",  # 或選用 gpt-4
    temperature=0.2
)

# 收集所有工具
tools = [
    gen_test_case_code_func,
    run_pytest_func, 
    get_fail_cases_func, 
    analysis_error_func, 
    refactor_code_func
    
]

# 建立 Agent 的系統提示，說明 Agent 的角色與可用工具
system_prompt = SystemMessagePromptTemplate.from_template("""
你是一個專業的測試與修復 AI Agent，你可以使用下列工具：
- CreateTestCaseTool
- RunPytestTool
- AnalyzeErrorTool
- RefactorCodeTool
- ReportBugTool

當需要時，請呼叫對應工具以完成測試產生、執行、錯誤分析與修正流程。
""")

agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # 這裡採用常用 Agent 類型
    verbose=True
)

# -----------------------------
# 3. 實作主流程 (可加入迴圈控制)
# -----------------------------

def main():
    # 範例使用：產生測試案例、執行測試、並根據結果進行後續處理
    # 初始輸入：測試案例名稱與測試場景
    user_input = "請幫我產生一個測試案例，名稱為 'login_flow'，測試場景為 '測試使用者登入流程'。" \
                 "然後執行測試，若測試失敗請分析錯誤，若為測試程式碼問題請修正；" \
                 "若確定是應用程式問題請建立 Bug 報告。"

    # 建立初始對話訊息：包含 system 與 user 的訊息
    system_message = system_prompt.format()
    human_message = HumanMessage(content=user_input)

    # 若要執行自動迴圈，可在此處加入多次調用邏輯
    # 這裡示範一次 Agent 呼叫，實際上可以透過外層迴圈重複執行直到成功或達到最大次數
    response = agent.run([system_message, human_message])
    print("\n[Agent Response]\n", response)

if __name__ == "__main__":
    flow_changed_func = ''
    main()
