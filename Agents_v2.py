import os
import subprocess
import configparser
from langgraph import Graph, Tool, ChatOpenAI
from langgraph.llms import OpenAI
from langgraph.prompts import PromptTemplate

# Import your specific tools
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
    SAVE_REFACTOR_TEST_CASE_PATH = config.get('General', 'SAVE_REFACTOR_TEST_CASE_PATH')

    AP_FAIL_REASONS = [item.strip() for line in config.get('General', "AP_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]
    AT_FAIL_REASONS = [item.strip() for line in config.get('General', "AT_ErrorReasons").splitlines() for item in line.split(';') if item.strip()]
    API_KEY = config.get('General', 'API_KEY')


# Define your tools using LangGraph
def gen_test_case_code_func(test_case_name: str, test_steps: str, force_update: bool) -> str:
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
    gen = GenerateCase(path_settings=path_settings, force_update=force_update)
    return gen.generate_process(test_case_name, test_steps)


def run_pytest_func(test_case_name: str) -> dict:
    try:
        if test_case_name:
            test_path = os.path.join(PYTEST_FILE_PATH, PYTEST_FILE_NAME, f"::{test_case_name}")
        else:
            test_path = os.path.join(PYTEST_FILE_PATH, PYTEST_FILE_NAME)

        result = subprocess.run(
            ["python3.9", "-m", "pytest", "--reportportal", "--color=yes", test_path],
            capture_output=True,
            text=True
        )
        return True
    except Exception as e:
        print(f'Error happened when executing pytest: {e}')
        return False


def get_fail_cases_func() -> list:
    collector = FailedCollector(path_setting={
        "log_path": PYTEST_LOG_PATH,
        "json_path": PYTEST_LOG_JSON_PATH
    })
    return collector.collect_process()


def analysis_error_func(fail_case: str, flow_changed_func: str) -> str:
    error_analyzer = ErrorAnalyzer(fail_case, flow_changed_func, AP_FAIL_REASONS, AT_FAIL_REASONS)
    return error_analyzer.analysis_process()


def refactor_code_func(path_settings: dict, test_case_name: str, error_reason: str) -> str:
    path_settings = {
        'test_case_json': TEST_CASE_JSON_PATH,
        'save_path': SAVE_REFACTOR_TEST_CASE_PATH
    }

    refactor = CaseRefactor(test_case_name, error_reason, path_settings)
    return refactor.refactor_process()


# Set up the LangGraph agent with multi-input capabilities
def setup_agent():
    # Read configuration first
    read_config()

    # Define the LLM model using OpenAI
    llm = OpenAI(api_key=API_KEY, model="gpt-4o", temperature=0.7)

    # Create a prompt template
    prompt_template = """
    You are a professional testing and debugging AI Agent that helps users create, run, analyze, and fix automated tests.
    Your workflow typically follows these steps:
    1. Generate test case code based on test case name and steps
    2. Execute the test case using pytest
    3. If the test fails, analyze the error to determine if it's an Application Error (AP) or Automation Test Error (AT)
    4. For AT errors, refactor the test code to fix the issue
    5. For AP errors, provide a detailed error report

    Always report your progress clearly, and when using tools, make sure to provide the necessary information in the correct format.
    """

    # Initialize LangGraph agent
    agent = Graph(
        llm=llm,
        tools=[gen_test_case_code_func, run_pytest_func, get_fail_cases_func, analysis_error_func, refactor_code_func],
        prompt_template=prompt_template,
        verbose=True
    )

    return agent


def main():
    agent = setup_agent()

    # Example user input
    user_input = """
    Please generate a test case "test_agent_func_21_1" for the following test steps:
    1. Start APP
    2. Enter Room (Media)(1)
    """

    # Run the agent
    response = agent.run(user_input)
    print("\n[Agent Response]\n", response)


if __name__ == "__main__":
    main()
