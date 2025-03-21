import re
import os
import json

class FailedCollector:
    def __init__(self, path_setting):
        self.log_path = path_setting['log_path']
        if not os.path.exists(self.log_path):
            raise FileNotFoundError(f"Log file not found: {self.log_path}")
        self.error_log_json_path = path_setting['json_path']
        self.fail_cases = []

    def _get_log_from_pytest_log(self):
        test_items = []
        current_test = None
        in_test_section = False

        # 取得 test_name 的正則表達式（原本的內容中，name 欄位包含整行，例：
        # "[test_launch_process_1_1] GDPR shows up when first launch"）
        start_pattern = re.compile(
            r"Start TestItem: request_body=.*?'name':\s*'([^']+)'"
        )
        # 取得 test_result 的正則表達式
        finish_pattern = re.compile(
            r"Finish TestItem: request_body=.*?'status':\s*'([^']+)'"
        )

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line_stripped = line.strip()

                # 嘗試匹配測試開始行
                match_start = start_pattern.search(line_stripped)
                if match_start:
                    # 若已有上一個 test 未結束，先存入
                    if current_test:
                        test_items.append(current_test)
                    # 取得原始的 test_name，再取出 [] 內的內容
                    full_name = match_start.group(1)
                    inner_name_match = re.search(r"\[(.*?)\]", full_name)
                    if inner_name_match:
                        test_name = inner_name_match.group(1)
                    else:
                        test_name = full_name

                    current_test = {
                        "test_name": test_name,
                        "test_result": "",
                        "test_log": []
                    }
                    in_test_section = True
                    # Debug:
                    print("Found test start:", current_test["test_name"])
                    continue

                # 嘗試匹配測試結束行
                match_finish = finish_pattern.search(line_stripped)
                if match_finish and current_test:
                    raw_result = match_finish.group(1).upper()
                    if raw_result == "PASSED":
                        current_test["test_result"] = "PASS"
                    elif raw_result == "FAILED":
                        current_test["test_result"] = "FAIL"
                    elif raw_result == "SKIPPED":
                        current_test["test_result"] = "SKIP"
                    else:
                        current_test["test_result"] = raw_result

                    print("Found test finish with result:", current_test["test_result"])
                    test_items.append(current_test)
                    current_test = None
                    in_test_section = False
                    continue

                # 若在測試區段中，將該行加入 test_log (排除包含 "HTTP/1.1" 201 None 的行)
                if in_test_section and current_test:
                    if 'HTTP/1.1" 201 None' in line_stripped or 'HTTP/1.1" 200 None' in line_stripped or 'response message' in line_stripped:
                        continue
                    current_test["test_log"].append(line_stripped)

        if current_test:
            test_items.append(current_test)

        print("Total test items found:", len(test_items))

        with open(self.error_log_json_path, "w", encoding="utf-8") as out_f:
            json.dump(test_items, out_f, ensure_ascii=False, indent=2)

    def _get_fail_cases(self):
        with open(self.error_log_json_path, 'r') as f:
            data = json.load(f)
            
            for item in data:
                if item.get('test_result', '').upper() == 'FAIL':
                    test_name = item.get('test_name', '')
                    test_log = item.get('test_log', [])
                    self.fail_cases.append({"test_name": test_name, "test_log": test_log})

    def collect_process(self):
        self._get_log_from_pytest_log()
        self._get_fail_cases()
        return self.fail_cases
    

if __name__ == "__main__":
    path_setting = {
        'log_path': 'pytest_0228_1350.log',
        'json_path': 'output.json'
    }
    collector = FailedCollector(path_setting)
    fail_cases = collector.collect_process()
    print(f'There are {len(fail_cases)} failed test cases.\n Fail cases:')
    for case in fail_cases:
        print(f'  {case.get("test_name", "")}')