#!/usr/bin/env python3 
import json

def process_test_results(json_file): 
    """讀取 JSON 檔，並回傳失敗測試案例的字典列表（包含 test_name 與 test_log）。"""
    with open(json_file, 'r') as f: 
        data = json.load(f) 
        fail_cases = [] 
        for item in data: # 判斷測試結果是否不為 PASS 
            if item.get('test_result', '').upper() == 'FAIL': 
                test_name = item.get('test_name', '') 
                test_log = item.get('test_log', []) 
                fail_cases.append({"test_name": test_name, "test_log": test_log}) 
        return fail_cases

def generate_prompt(fail_case, flow_changed_func=None): 
    """根據失敗測試案例生成詳細的 prompt。""" # 將多行 log 組合成一個字串（可根據需求進行格式調整） 
    error_log = "\n".join(fail_case.get("test_log", [])) 
    prompt = f"""
Analyze the provided error log, screenshot, and test case code to identify the single most likely error reason for the auto testing failure. In your answer, clearly indicate whether the error falls under AP Fail or AT Fail. Then, propose a concrete fix for the error.
Note: If necessary, analyze the two compared images to support your findings.
Possible Error Categories:
AP Fail:
Locator change
No response after an action
Image comparison result differs from GroundTruth
UI flow change
AT Fail:
Incorrect locator provided
Action executed before the previous step is complete
Image comparison similarity threshold set too high or too low
Incorrect order of test case steps
Interference from an upper dialog box
Additional Information:
Affected Functions (UI flow change): {flow_changed_func}
Error Log: {error_log}
Instruction:
Please analyze the above details and return only one error reason (the most likely cause). In your response, include whether this is an AT Fail or an AP Fail error, and propose a concrete fix for it."""
    

    return prompt


json_file = "output.json" # 請確認此檔案位於正確路徑或進行調整 
fail_cases = process_test_results(json_file)
print(fail_cases)
for case in fail_cases: 
    prompt = generate_prompt(case) 
    print(f'=== {case.get("test_name", "")} ===')
    print(prompt)
    print("===")