import os
import subprocess
import configparser
import pytest
import ast
import json

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
from TestStepGenerator.TestStepGenerator import TestStepGenerator
from TestCodeGenerator.TestCodeGenerator import GenerateCase
from FailLogCollector.FailLogCollector import FailLogCollector
from ErrorAnalyzer.Analyzer_v2 import ErrorAnalyzer
from CaseRefactor.CaseRefactor import CaseRefactor

CONFIG_FILE = 'app.config'

def read_config():
    """
    Reads the app.config file and assigns each parameter from the [General]
    section to a global variable.
    """
    global PYTEST_FILE_PATH, PYTEST_FILE_NAME, PYTEST_LOG_PATH, PYTEST_LOG_JSON_PATH, PYTEST_TEMPLATE_NAME,\
           TEST_CASE_PATH, TEST_CASE_JSON_PATH, TEST_CASE_FAISS_PATH, \
           PAGE_FUNCTIONS_PATH, PAGE_FUNCTIONS_JSON_PATH, PAGE_FUNCTIONS_FAISS_PATH, PAGE_FUNCTIONS_FILTERED_JSON_PATH, \
           SAVE_REFACTOR_TEST_CASE_PATH, API_KEY,\
            SAVE_HTML_PAGE_FOLDER, SAVE_JSON_PAGE_FOLDER, SAVE_FULL_HELP_JSON_FILE_NAME,\
            TEMP_GENERATED_TEST_STEPS, TEMP_EXTRACTED_PAGE_FUNCTION, TEMP_FAIL_CASES, TEMP_ERROR_REASON_ANALYSIS

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
    PYTEST_TEMPLATE_NAME = config.get('General', 'PYTEST_TEMPLATE_NAME')
    TEST_CASE_PATH = config.get('General', 'TEST_CASE_PATH')
    TEST_CASE_JSON_PATH = config.get('General', 'TEST_CASE_JSON_PATH')
    TEST_CASE_FAISS_PATH = config.get('General', 'TEST_CASE_FAISS_PATH')
    PAGE_FUNCTIONS_PATH = config.get('General', 'PAGE_FUNCTIONS_PATH')
    PAGE_FUNCTIONS_JSON_PATH = config.get('General', 'PAGE_FUNCTIONS_JSON_PATH')
    PAGE_FUNCTIONS_FAISS_PATH = config.get('General', 'PAGE_FUNCTIONS_FAISS_PATH')
    PAGE_FUNCTIONS_FILTERED_JSON_PATH = config.get('General', 'PAGE_FUNCTIONS_FILTERED_JSON_PATH')
    SAVE_REFACTOR_TEST_CASE_PATH = config.get('General', 'SAVE_REFACTOR_TEST_CASE_PATH')
    SAVE_HTML_PAGE_FOLDER = config.get('General', 'SAVE_HTML_PAGE_FOLDER')
    SAVE_JSON_PAGE_FOLDER = config.get('General', 'SAVE_JSON_PAGE_FOLDER')
    SAVE_FULL_HELP_JSON_FILE_NAME = config.get('General', 'SAVE_FULL_HELP_JSON_FILE_NAME')

    TEMP_GENERATED_TEST_STEPS = config.get('General', 'TEMP_GENERATED_TEST_STEPS')
    TEMP_EXTRACTED_PAGE_FUNCTION = config.get('General', 'TEMP_EXTRACTED_PAGE_FUNCTION')
    TEMP_FAIL_CASES = config.get('General', 'TEMP_FAIL_CASES')
    TEMP_ERROR_REASON_ANALYSIS = config.get('General', 'TEMP_ERROR_REASON_ANALYSIS')

    # API Key
    API_KEY = config.get('General', 'API_KEY')

def _save_to_json(data, file):
    """Save data to a JSON file."""
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def _read_from_json(file):
    """Read data from a JSON file."""
    with open(file, 'r') as f:
        return json.load(f)
    
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
    return True

@tool(
    name_or_callable="GenTestStepsTool",
    description=(
        "Generate the test steps based on the given current status and desired goal."
        "Input: Format must be 'current status;desired goal' where:"
        " - current status (list): The current status of the application UI"
        " - desired goal (list): The desired goal of the steps to reach"
        " - For example: ['In media room'];['Import stock media', 'The first stock media', 'Add the media to timeline']"
        "Output: The generated test steps."
    )
)
def gen_test_steps_func(input_str: str) -> str:
    """
    Generate the test steps based on the given current status and desired goal.
    args:
        input_str: str: The input string containing the current status and desired goal. 
    return:
        str: The generated test steps.
    """
    list_strs = input_str.split(';')

    current_status = ast.literal_eval(list_strs[0])
    desired_goal = ast.literal_eval(list_strs[1])

    generator = TestStepGenerator(TEST_CASE_JSON_PATH, PAGE_FUNCTIONS_JSON_PATH, SAVE_FULL_HELP_JSON_FILE_NAME, current_status, desired_goal)
    generated_steps = generator.generate_process()

    _save_to_json(generated_steps, TEMP_GENERATED_TEST_STEPS)
    print(f'Generated test steps:\n{generated_steps}')
    return True

    

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
        test_steps: str: None
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
    
    test_steps = _read_from_json(TEMP_GENERATED_TEST_STEPS)
    print(f'Get the test_steps from json file:\n{test_steps}')
    for step in test_steps.split("\n"):
        relevant_functions = search.extract_relevant_functions_step_by_step(step)
        if not relevant_functions:
            # call generate page function tool
            continue
        else:
            # Add only functions that aren't already in the list
            for func in relevant_functions:
                if func not in relevant_page_functions:
                    relevant_page_functions.append(func)

    # return relevant_page_functions
    _save_to_json(relevant_page_functions, TEMP_EXTRACTED_PAGE_FUNCTION)
    return True


@tool(
    name_or_callable="GenTestCaseCodeTool",
    description=(
        "Create a test case code file via the given test case name and test steps."
        "Input: test_case_name: The name of the test case"
        "Output: Generate test case successfully or not."
    )
)
def gen_test_case_code_func(test_case_name: str) -> str:
    """
    Generate the test case code file by openai API via the given test case name and test steps.
    args:
        test_case_name: str: The name of the test case.
    return:
        str: Generate test case successfully or not.
    """
    test_steps = _read_from_json(TEMP_GENERATED_TEST_STEPS)
    print(f'Get the test_steps from json file:\n{test_steps}')

    relevant_functions = _read_from_json(TEMP_EXTRACTED_PAGE_FUNCTION)
    print(f'Get the relevant functions from json file:\n{relevant_functions}')
    path_settings = {
        'test_case_dir': TEST_CASE_PATH,
        'test_case_json': TEST_CASE_JSON_PATH,
        'test_case_faiss': TEST_CASE_FAISS_PATH,
        'pytest_file_name': PYTEST_FILE_NAME,
        'pytest_file_path': PYTEST_FILE_PATH,
        'pytest_template_name': PYTEST_TEMPLATE_NAME,
    }
    gen = GenerateCase(relevant_functions, path_settings=path_settings)
    gen.generate_process(test_case_name, test_steps)

    return True


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
            test_path = f"{os.path.join(PYTEST_FILE_PATH, PYTEST_FILE_NAME)}::{test_case_name}"
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
        return None

    

@tool(
    name_or_callable="GetFailCasesTool",
    description=(
        "Get the failed test cases from the pytest result. "
        "Input: None"
        "Output: A list contains the failed test cases, log."
    )
)
def get_fail_cases_func(input_str: str = None) -> list:
    """
    Get the failed test cases from the pytest result.
    args:
        None
    return:
        list: A list contains the failed test cases, log.
    """
    collector = FailLogCollector(path_setting={
        "log_path": PYTEST_LOG_PATH,
        "json_path": PYTEST_LOG_JSON_PATH
    })
    fail_cases = collector.collect_process()
    _save_to_json(fail_cases, TEMP_FAIL_CASES)
    return fail_cases


@tool(
    name_or_callable="AnalyzeErrorTool",
    description=(
        "Analyze the pytest result to determine AP/AT error and the failure reason."
        "Input: Input: Format must be 'fail_case;flow_changed_func' where:"
            "fail_case (string) The failed test case name."
            "flow_changed_func (string) the function that the flow changed."
        "Output: 'AP Error' or 'AT Error' and the failure reason."
    )
)
def analysis_error_func(input_str: str) -> str:
    """
    Analyze the pytest result to determine AP/AT error and the failure reason.
    args:
        fail_case: str: The failed test case name.
        flow_changed_func: str: The function that the flow changed.
    return:
        str: 'AP Error' or 'AT Error' and the failure reason
    """
    path_settings = {
        'test_case_json': TEST_CASE_JSON_PATH,
        'pytest_log_json_path': PYTEST_LOG_JSON_PATH,
    }

    fail_case, flow_changed_func = input_str.split(';')

    error_analyzer = ErrorAnalyzer(flow_changed_func, path_settings)

    error_reason = error_analyzer.analysis_process(fail_case)
    _save_to_json(error_reason, TEMP_ERROR_REASON_ANALYSIS)

    return error_reason["error_type"] + error_reason["error_condition"]


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
        gen_test_steps_func,
        search_relevant_functions_step_by_step_func,
        gen_test_case_code_func,
        run_pytest_func,
        get_fail_cases_func,
        analysis_error_func,
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

    current_status = ['APP is not launched']
    desired_goal = ['Enter Room (Title)']
    test_name = 'test_afdsafdsg_room_func_100_1'

    user_input = f"""Please follw the steps to complete the assigned task:
1. Extract test case code and page function from the given directory.
2. Generate test step from current status {current_status} to desired goal {desired_goal}.
3. After generated test steps and found the relevant page functions, generate test code with test name '{test_name}'.
4. Run the test case '{test_name}' by tool run_pytest_func.
5. If the test fails (Return False), collect and analyze the failures, then:
- If it's an AT Error:
    o Incorrect order of test case steps => Call 'GenTestStepsTool' to generate the correct test steps
    o Image comparison similarity threshold set too high or too low => Call 'GenTestCaseCodeTool' to refactor the threshold
    o Incorrect verify value => Call 'GenTestCaseCodeTool' to refactor the value
    o Interference from an upper dialog box => Call 'GenTestStepsTool' to generate the correct test steps
    o Action executed before the previous step is complete => Call 'GenTestCaseCodeTool' or 'GenTestStepsTool' to refactor the test case
    o Incorrect locator provided due to locator error => Call 'PageFunctionGeneratorTool' to generate the correct locator
- If it's an AP Error, provide a detailed error report

    Just tell me which tool you want to use to deal with all fail cases.
    With the format 'test_name: want to use tool'
"""


    # Run the agent
    response = agent.run(user_input)
    print("\n[Agent Response]\n")
    print("=====================\n")
    print(response)


if __name__ == "__main__":
    main()