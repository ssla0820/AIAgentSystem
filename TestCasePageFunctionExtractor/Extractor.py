import re
import json
import os
import sys

parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _Database.mapping_table import class_mapping

class TestCase_PageFunction_Extractor():
    def __init__(self, path_settings, max_lines=50000):
        self.max_lines = max_lines
        self.class_mapping = class_mapping
        self.page_function_json = path_settings['page_functions_json']
        self.test_case_json = path_settings['test_case_json']
        

        if path_settings['page_functions_dir']:
            self.page_function_files = [
                os.path.join(path_settings['page_functions_dir'], f)
                for f in os.listdir(path_settings['page_functions_dir'])
                if os.path.isfile(os.path.join(path_settings['page_functions_dir'], f))
            ]

        if path_settings['test_case_dir']:
            self.test_case_files = [
                os.path.join(path_settings['test_case_dir'], f)
                for f in os.listdir(path_settings['test_case_dir'])
                if os.path.isfile(os.path.join(path_settings['test_case_dir'], f))
            ]

    def _get_content_from_file(self, file_path):
        """Load content from file (limit to max_lines if necessary)."""
        print(f"🔍 Get File content from: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if len(lines) > self.max_lines:
                    print(f"⚠️ File too large, only processing first {self.max_lines} lines")
                    lines = lines[:self.max_lines]
                content = "".join(lines)
        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
            return []
        return content
    
    def _analyze_content_page_functions(self, content):
        """
        Analyze content for Page Functions.
        Extracts:
         - The description within @step('...')
         - The function name and its parameter list (excluding self)
         - The class hierarchy (supporting nested classes correctly)
        """
        print("🔍 Analyzing content for page functions...")
        class_stack = []  # track current class hierarchy
        extracted_functions = []
        lines = content.split("\n")

        for idx, line in enumerate(lines):
            stripped_line = line.strip()
            indent_level = len(line) - len(line.lstrip())

            # Match class definition
            class_match = re.match(r"^class (\w+)", stripped_line)
            if class_match:
                class_name = class_match.group(1).lower()

                # 移除不在當前縮排層級的 class
                while class_stack and class_stack[-1][1] >= indent_level:
                    class_stack.pop()
                
                # 加入新的 class
                class_stack.append((class_name, indent_level))

            # Detect @step() annotation
            # step_match = re.match(r"^\s*@step\('([^']+)'\)", stripped_line)
            step_match = re.match(r"^\s*@step\((?:'([^']+)'|\"([^\"]+)\")\)", stripped_line)
            if step_match:
                step_description = step_match.group(1) or step_match.group(2)

                if idx + 1 < len(lines):
                    function_line = lines[idx + 1]
                    function_match = re.match(r"^\s*def\s+(\w+)\((.*?)\)", function_line)
                    
                    if function_match:
                        func_name = function_match.group(1)
                        params_str = function_match.group(2)
                        params_list = [
                            param.strip() for param in params_str.split(",")
                            if param.strip() and param.strip() != "self"
                        ]
                        final_params_str = ", ".join(params_list)

                        # **根據縮排層級決定函數屬於哪個 class**
                        while class_stack and class_stack[-1][1] >= indent_level:
                            class_stack.pop()
                        
                        class_path = ".".join([cls[0] for cls in class_stack]) if class_stack else "UnknownClass"

                        # **確保 class_path 能正確替換**
                        class_path_parts = class_path.split(".")
                        corrected_class_path = ".".join([
                            self.class_mapping.get(part, part) for part in class_path_parts
                        ])

                        full_func_name = f"{corrected_class_path}.{func_name}({final_params_str})"
                        extracted_functions.append({
                            "name": full_func_name,
                            "description": step_description.strip(),
                        })
        return extracted_functions

    def _analyze_content_test_case(self, content):
        """
        Analyze content for Test Cases.
        Extracts:
         - Test case name
         - pytest.mark tags and the marked name (if any)
         - Description (split into a list)
         - Full code including markers and function definition
        """
        print("🔍 Analyzing content for test cases...")
        test_patterns = re.findall(
            r"((?:\s*@pytest\.mark\.[^\n]+\n\s*)+)(?:@[\w_]+\n\s*)*def (\w+)\(.*?\):\s+[\"']{3}([\s\S]+?)[\"']{3}\s*([\s\S]+?)(?=\n\s*@pytest\.mark|\Z)",
            content, re.DOTALL
        )
        if not test_patterns:
            print("❌ No test cases found. Please check file format.")
            return []

        extracted_tests = []
        for full_markers, test_name, description, test_content in test_patterns:
            tags = re.findall(r"@pytest\.mark\.(\w+)", full_markers)
            marked_name_match = re.search(r"@pytest\.mark\.name\('([^']+)'\)", full_markers)
            marked_name = marked_name_match.group(1) if marked_name_match else test_name
            if "name" in tags:
                tags.remove("name")
            description_list = [step.strip() for step in description.split("\n") if step.strip()]
            test_content_cleaned = test_content.strip()
            full_code = full_markers + f"def {test_name}(self):\n    '''{description}'''\n" + test_content_cleaned
            extracted_tests.append({
                "name": test_name,
                "tags": tags,
                "marked_name": marked_name,
                "description": description_list,
                "full_code": full_code.strip()
            })
        return extracted_tests

    def _organize_analyzed_data(self, file_path, file_type):
        """
        Organize analyzed data from a file based on type.
        file_type: 'page_function' or 'test_case'
        """
        content = self._get_content_from_file(file_path)
        if not content:
            return []

        if file_type == 'page_function':
            extracted_content = self._analyze_content_page_functions(content)
        elif file_type == 'test_case':
            extracted_content = self._analyze_content_test_case(content)
        else:
            print(f"❌ Unsupported file type: {file_type}")
            return []

        if not extracted_content:
            print(f"❌ No matching {file_type} found in {file_path}. Please check file format.")
            return []

        print(f"✅ Found {len(extracted_content)} {file_type}(s) in {file_path}")
        return extracted_content

    def extract_process(self, file_type):
        """
        Extract data from multiple files and save the result to a JSON file.
        file_type: 'page_function' or 'test_case'
        """
        if file_type == 'page_function':
            json_path = self.page_function_json
            file_path_list = self.page_function_files
        elif file_type == 'test_case':
            json_path = self.test_case_json
            file_path_list = self.test_case_files

        content_list = []
        for file in file_path_list:
            content_list.extend(self._organize_analyzed_data(file, file_type))

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(content_list, f, ensure_ascii=False, indent=4)

        print("✅ Extraction complete and data saved!")
        return content_list


if __name__ == "__main__":
    # Example usage:
    # Replace with actual file paths and desired JSON output paths
    page_function_files = [
        r"E:\Debby\9_Scripts\RAG_withPDR_ReportPortal\refer_data\page_function\base_page.py"
    ]
    test_case_files = [
        r"E:\Debby\9_Scripts\RAG_withPDR_ReportPortal\refer_data\test_case\some_test_file.py"
    ]

    extractor = ExtractorClass()

    # Extract page functions and save to JSON
    page_functions = extractor.extracted_all_data("page_function", page_function_files, "page_functions.json")
    print("Extracted Page Functions:")
    print(json.dumps(page_functions, indent=2, ensure_ascii=False))

    # # Extract test cases and save to JSON
    # test_cases = extractor.extracted_all_data("test_case", test_case_files, "test_cases.json")
    # print("Extracted Test Cases:")
    # print(json.dumps(test_cases, indent=2, ensure_ascii=False))
