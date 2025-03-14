import os
import subprocess
import configparser
import pytest

# from langchain.agents import tool, initialize_agent, AgentType

# from langchain.prompts import SystemMessagePromptTemplate
# from langchain.schema import HumanMessage

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.schema import SystemMessage, HumanMessage
from langchain.agents import AgentExecutor, initialize_agent, AgentType
from langchain.tools import tool

from TestCasePageFunctionExtractor.Extractor import TestCase_PageFunction_Extractor
from PageFunctionMapper.PageFunctionMapper import SearchPageFunctions
from TestCodeGenerator.Generator import GenerateCase
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
           PAGE_FUNCTIONS_PATH, PAGE_FUNCTIONS_JSON_PATH, PAGE_FUNCTIONS_FAISS_PATH, PAGE_FUNCTIONS_FILTERED_JSON_PATH, \
           SAVE_REFACTOR_TEST_CASE_PATH, AP_FAIL_REASONS, AT_FAIL_REASONS, API_KEY

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
    PAGE_FUNCTIONS_FILTERED_JSON_PATH = config.get('General', 'PAGE_FUNCTIONS_FILTERED_JSON_PATH')
    SAVE_REFACTOR_TEST_CASE_PATH = config.get('General', 'SAVE_REFACTOR_TEST_CASE_PATH')

    # ap_fail = config.get("APFail", "ErrorReasons")
    AP_FAIL_REASONS = [item.strip() for line in config.get('General', "AP_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]
    AT_FAIL_REASONS = [item.strip() for line in config.get('General', "AT_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]

    # API Key
    API_KEY = config.get('General', 'API_KEY')

@tool(
    name_or_callable="ExtractTestCaseCodePageFunctionTool",
    description=(
        "Extract test case code and page function from the given directory. "
        "Input: None"
        "Output: Extracted test case code and page function to JSON file. (Gloable Variables)"
    )
)
def extract_test_case_code_page_function_to_json_func(input_str: str) -> str:
    path_settings = {
        'page_functions_dir': PAGE_FUNCTIONS_PATH,
        'test_case_dir': TEST_CASE_PATH,
        'page_functions_json': PAGE_FUNCTIONS_JSON_PATH,
        'test_case_json': TEST_CASE_JSON_PATH,
    }
    extract_obj = TestCase_PageFunction_Extractor(path_settings=path_settings)
    extract_obj.extract_process('test_case')
    extract_obj.extract_process('page_function')

@tool(
    name_or_callable="SearchRelevantFunctionsTool",
    description=(
        "Search relevant functions from the given test steps."
        "Input: test_steps (string) as test steps."
        "Output: A list contains the relevant functions."
    )
)
def search_relevant_functions_step_by_step_func(test_steps: str) -> list:
    """
    Search relevant functions step by step from the given test steps.
    args:
        test_steps: str: The test steps of the test case.
    return:
        list: The relevant functions
    """

    path_settings = {
        'page_functions_json': PAGE_FUNCTIONS_JSON_PATH,
        'page_functions_faiss': PAGE_FUNCTIONS_FAISS_PATH,
        'page_functions_filtered_json': PAGE_FUNCTIONS_FILTERED_JSON_PATH,
    }
    relevant_page_functions = []
    search = SearchPageFunctions(path_settings['page_functions_json'], path_settings['page_functions_faiss'], path_settings['page_functions_filtered_json'])
    for step in test_steps.split("\n"):
        relevant_functions = search.extract_relevant_functions_step_by_step(step)
        # Add only functions that aren't already in the list
        for func in relevant_functions:
            if func not in relevant_page_functions:
                relevant_page_functions.append(func)
        else:
            # call generate page function tool
            pass
    return relevant_page_functions



@tool(
    name_or_callable="GenTestCaseCodeTool",
    description=(
        "Create a test case code file via the given test case name and test steps."
        "Input: Format must be 'test_case_name;test_steps;force_update;relevant_functions' where:"
        " - test_case_name: The name of the test case"
        " - test_steps: The test steps description"
        " - force_update: Boolean (True/False) to force update"
        " - relevant_functions: List of function dictionaries with 'name' and 'description' from SearchRelevantFunctionsTool"
        "Output: Generate test case successfully or not."
    )
)
def gen_test_case_code_func(input_str: str) -> str:
    """
    Generate the test case code file by openai API via the given test case name and test steps.
    args:
        test_case_name: str: The name of the test case.
        test_steps: str: The test steps of the test case.
        force_update: bool: Whether to force update the generator.

    return:
        str: Generate test case successfully or not.
    """
    test_case_name, test_steps, force_update, relevant_functions = input_str.split(';')
    # change relevant_functions frm str to list
    relevant_functions = relevant_functions.split(',')

    path_settings = {
        'page_functions_dir': PAGE_FUNCTIONS_PATH,
        'test_case_dir': TEST_CASE_PATH,
        'page_functions_json': PAGE_FUNCTIONS_JSON_PATH,
        'test_case_json': TEST_CASE_JSON_PATH,
        'page_functions_faiss': PAGE_FUNCTIONS_FAISS_PATH,
        'test_case_faiss': TEST_CASE_FAISS_PATH,
        'pytest_file_name': PYTEST_FILE_NAME,
        'pytest_file_path': PYTEST_FILE_PATH
    }
    gen = GenerateCase(relevant_functions, path_settings=path_settings, force_update=bool(force_update))

    return gen.generate_process(test_case_name, test_steps)


@tool(
    name_or_callable="RunPytestTool",
    description=(
        "Run the test case in local environment via pytest. "
        "Input: \
            file_path (string) the path of the test case file to run. \
            test_case_name (string) the name of the test case. "
        "Output: A Bool value indicates whether the test case run successfully."
    )
)
def run_pytest_func(test_case_name: str = None) -> bool:
    """
    Run the specified test case in the local environment using pytest.
    Args:
        test_case_name (str): The name of the test case to run. If None, all tests are run.
    Returns:
        bool: True if the test(s) ran successfully, False otherwise.
    """
    try:
        # Determine the test path
        if test_case_name:
            # Assuming PYTEST_FILE_PATH and PYTEST_FILE_NAME are defined globally
            test_path = os.path.join(PYTEST_FILE_PATH, PYTEST_FILE_NAME, f"::{test_case_name}")
        else:
            # Otherwise, run the full test file
            test_path = os.path.join(PYTEST_FILE_PATH, PYTEST_FILE_NAME)
            mark_option = ""

        # Set any additional arguments to pass to pytest (e.g., reportportal integration)
        additional_args = [
            '--reportportal',  # Enable ReportPortal integration
            '--color=yes',     # Enable colored output
            # You can add other flags here based on your needs
        ]

        # Run pytest with the constructed test path and any additional arguments
        result = pytest.main([test_path] + additional_args)

        # Check if pytest ran successfully
        if result == 0:
            print("Tests ran successfully.")
            return True
        else:
            print(f"pytest exited with code {result}.")
            return False

    except Exception as e:
        print(f"Error occurred while executing pytest: {e}")
        return False

    

@tool(
    name_or_callable="GetFailCasesTool",
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
    name_or_callable="AnalyzeErrorTool",
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
    name_or_callable="RefactorCodeTool",
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
#     name_or_callable="ReportBugTool",
#     description=(
#         "建立 AP Bug 報告 (示範用，可整合到 Bug Tracking 系統)。"
#         "輸入: pytest_result (string) 錯誤日誌。"
#         "輸出: Bug 報告建立結果 (string)。"
#     )
# )
# def report_bug_func(pytest_result: str) -> str:
#     # 這裡僅示範輸出訊息，實際上可整合 Jira / GitHub Issue 等系統
#     return f"AP Bug 已回報。錯誤日誌如下：\n{pytest_result}"

def setup_agent():
    """Setup and return the LangChain agent with all tools."""
    # Read configuration first
    read_config()
    
    # Create system prompt
    system_prompt = """
    You are a professional testing and debugging AI Agent that helps users create, run, analyze, and fix automated tests.
    Your workflow typically follows these steps:
    1. Generate test case code based on test case name and steps
    2. Execute the test case using pytest
    3. If the test fails, analyze the error to determine if it's an Application Error (AP) or Automation Test Error (AT)
    4. For AT errors, refactor the test code to fix the issue
    5. For AP errors, provide a detailed error report

    Always report your progress clearly, and when using tools, make sure to provide the necessary information in the correct format.
    """

    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        api_key=API_KEY
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{input}")
    ])

    # Collect all tools
    tools = [
        extract_test_case_code_page_function_to_json_func,
        search_relevant_functions_step_by_step_func,
        gen_test_case_code_func,
        # run_pytest_func,
        # get_fail_cases_func,
        # analysis_error_func,
        # refactor_code_func
    ]

    # Initialize agent (ensure you pass the correct agent type)
    agent = initialize_agent(
        tools=tools,
        agent_type=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        llm=llm,
        verbose=True
    )
    return agent


def main():
    """Main execution function for the testing agent."""
    # Initialize the agent
    agent = setup_agent()
    
    # Example user input
    # user_input = """
    # Please help me generate a test case named 'login_flow' that tests the user login flow.
    # After generating the test case, run it, analyze any errors, and fix them if possible.
    # If it's an application issue, prepare a bug report.
    # """

    user_input = """
    Extract test case code and page function from the given directory.
    Then search relevant functions for these steps:
    1. Start APP
    2. Enter Room (Media)(1).
    After finding the relevant functions, use them to generate a test case "test_agent_func_21_1" with the same steps.
    Make sure to pass the results from the search function to the generate function.
    """


    # Run the agent
    response = agent.run(user_input)
    print("\n[Agent Response]\n")
    print("=====================\n")
    print(response)


if __name__ == "__main__":
    main()