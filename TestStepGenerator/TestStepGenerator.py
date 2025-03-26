from sentence_transformers import SentenceTransformer, util
import json
import os
import sys
import torch
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)

from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector
class TestStepGenerator():
    def __init__(self, test_case_json_file_path, page_function_json_file, full_help_content_json_file_path, current_status, desired_goal):
        with open(full_help_content_json_file_path, "r", encoding="utf-8") as file:
            self.full_help_content = json.load(file)

        with open(page_function_json_file, 'r', encoding='utf-8') as file:
            self.page_function_content = json.load(file)

        self.threshold = 0.5
        with open(test_case_json_file_path, 'r', encoding='utf-8') as f:
            self.test_cases_content = json.load(f)
        
        self.model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
        # self.model = SentenceTransformer('all-mpnet-base-v2')
        self.chat_api_connector = ChatAPIConnector()

        self.current_status = current_status
        self.desired_goal = desired_goal

    def _get_related_func_in_help(self, query):
        results = []
        # Define your query sentence
        # query = f"Current Status is: {self.current_status} and Desired Goal is: {self.desired_goal}"
        query_embedding = self.model.encode(query, convert_to_tensor=True)

        # Iterate over the JSON data to compute similarity scores
        for block in self.full_help_content.get("blocks", []):
            for section in block.get("sections", []):
                combined_text = " ".join([section.get("heading", ""), section.get("summary", "")])
                section_embedding = self.model.encode(combined_text, convert_to_tensor=True)
                similarity = util.cos_sim(query_embedding, section_embedding).item()
                if similarity >= self.threshold:
                    results.append({
                        "block_title": block.get("block_title"),
                        "heading": section.get("heading"),
                        "summary": section.get("summary"),
                        "file": section.get("file"),
                        "similarity": similarity
                    })

        refer_data_list = []
        refer_data_heading = []
        # Print the results
        for item in results:
            refer_data_list.append(f"{item['heading']}: {item['summary']}")
            refer_data_heading.append(item['heading'])
        
        return refer_data_list, refer_data_heading

    def _get_simliary_test_case(self):
        # 定義查詢條件
        query = f"{self.current_status}, {self.desired_goal}"

        # 將每個測試案例的 name 與 description 合併成一個字串
        test_case_texts = []
        for tc in self.test_cases_content:
            name = tc.get("name", "")
            # 將 description 列表轉換成一個字串（以空格隔開）
            desc = " ".join(tc.get("description", []))
            full_text = f"{name}: {desc}"
            test_case_texts.append(full_text)

        # 編碼查詢與所有測試案例的文字
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        tc_embeddings = self.model.encode(test_case_texts, convert_to_tensor=True)

        # 計算查詢與每筆案例間的餘弦相似度
        cosine_scores = util.cos_sim(query_embedding, tc_embeddings)[0]

        # 取得前10筆相似度最高的案例（若總數不足 10，則取全部）
        top_k = min(10, len(test_case_texts))
        top_results = torch.topk(cosine_scores, k=top_k)

        # 輸出結果：依序印出 name、description 與相似度分數
        result = []
        result_name = []
        for score, idx in zip(top_results.values, top_results.indices):
            tc = self.test_cases_content[idx.item()]
            result.append(tc.get("description"))
            result_name.append(tc.get("name"))
        return result, result_name
    
    def _get_prompt_for_generate_steps(self, refer_data_list, refer_test_steps_list):
        prompt = f'''Generate precise operation steps for PowerDirector software with the following requirements:
- Each step must begin with an incremental number followed by [Action] or [Verify], e.g., "1. [Action]"
- Present steps as a single, continuous numbered list (1, 2, 3, etc.), NOT grouped by function
- Do NOT create separate sections with headers or sub-numbering
- Strictly adhere to PowerDirector's official terminology and UI element names
- Wrap function parameters as (value), e.g., select track (3)
- Represent buttons or options as [name], e.g., Click [Cancel] button
- Make each step atomic and focused on a single action or verification
- List the steps sequentially with no additional commentary. 
- Focus on to the steps to from the "current status" to reach the "desired goal" only
- Consider carefully how to perform each operation in PowerDirector to ensure accuracy and clarity
- If necessary, refer to the related test steps to ensure the steps are accurate and detailed

Reference Data: {refer_data_list}
Reference Test Steps: {refer_test_steps_list}
Current Status: {self.current_status}
Desired Goal: {self.desired_goal}'''

        return prompt
    
    def _ask_llm_to_generate_steps(self, prompt):
        system_role_msg = """
        You are a PowerDirector software expert with comprehensive knowledge of all its features and UI operations.
        You must strictly follow the software's operational workflow, ensuring the generated steps:
        1. Accurately reflect PowerDirector's actual operations
        2. Use official terminology and naming conventions
        3. Are clear, concise, and easy to understand
        4. Are presented in the [Action] and [Verify] format
        
        Before analyzing each step, consider:
        - Is this the most efficient way to perform this operation in PowerDirector?
        - Does this step use the correct UI element names?
        - Is this step clear and unambiguous?
        - Would a PowerDirector user immediately understand what to do?
        
        Focus on producing steps that match exactly how PowerDirector's interface works, using the exact terms found in the application.
        """
        return self.chat_api_connector.generate_chat_response(prompt, system_role_msg)
    
    def _get_related_page_functions_from_refer_data(self, refer_data_list, threshold=0.4):
        # Generate embeddings for descriptions
        descriptions = [item['description'] for item in self.page_function_content]
        embeddings = self.model.encode(descriptions, convert_to_tensor=True)

        unique_descriptions = set()  # Set to ensure unique descriptions
        related_page_function_descriptions_list = []

        # Iterate through the refer_data_list
        for query in refer_data_list:
            # Encode the query
            query_embedding = self.model.encode([query], convert_to_tensor=True)
            
            # Calculate cosine similarity
            cosine_scores = util.cos_sim(query_embedding, embeddings)[0]

            # Iterate over cosine scores and add descriptions with scores above threshold
            for idx, score in enumerate(cosine_scores):
                if score >= threshold:  # Check if the similarity score meets the threshold
                    most_similar_description = descriptions[idx]
                    if most_similar_description not in unique_descriptions:
                        unique_descriptions.add(most_similar_description)
                        related_page_function_descriptions_list.append(most_similar_description)

        return related_page_function_descriptions_list
    
    def _get_prompt_to_rewrite_test_step(self, raw_steps, refer_page_functions):
        prompt = f'''
Your task is to align raw_steps with the functions provided in refer_page_functions as follows:
 - If a step in raw_steps corresponds exactly to a function in refer_page_functions, replace it with the format used in refer_page_functions.
 - If multiple steps in raw_steps correspond to a single function in refer_page_functions, combine them into one step.
 - Each step should begin with an incremental number followed by [Action] or [Verify], e.g., "1. [Action]".
 - Present all steps as a continuous, numbered list (1, 2, 3, etc.), without grouping them by function.
 - Wrap function parameters in parentheses, e.g., select track (3).
 - Represent buttons or options as [name], e.g., Click [Cancel] button.

raw_steps: {raw_steps}
refer_page_functions: {refer_page_functions}
'''
        return prompt

    def _ask_llm_to_rewrite_test_step(self, prompt):
        system_role_msg = """
        You are a tool designed to transform raw test steps into a standardized format. You need to match the raw steps with predefined functions and reformat them according to the rules provided. Your task is to align raw steps to the custom format and ensure consistency across the steps.
        """
        return self.chat_api_connector.generate_chat_response(prompt, system_role_msg)
    
    def generate_process(self):
        refer_data_list = []
        refer_data_heading = []
        # Get Related Function in Help for Current Status
        for query in self.current_status:
            data_list, data_heading = self._get_related_func_in_help(query)
            refer_data_list.extend(data_list)
            refer_data_heading.extend(data_heading)
        for query in self.desired_goal:
            data_list, data_heading = self._get_related_func_in_help(query)
            refer_data_list.extend(data_list)
            refer_data_heading.extend(data_heading)
        refer_test_steps_list, refer_test_name_list = self._get_simliary_test_case()
        related_page_function_descriptions_list = self._get_related_page_functions_from_refer_data(refer_data_heading)

        print(f'related_page_function_descriptions_list: {related_page_function_descriptions_list}')

        prompt_to_gen_step = self._get_prompt_for_generate_steps(refer_data_list, refer_test_steps_list)
        generated_raw_steps = self._ask_llm_to_generate_steps(prompt_to_gen_step)
        print(f'generated_raw_steps:\n{generated_raw_steps}')
        prompt_to_rewrite_test_step = self._get_prompt_to_rewrite_test_step(generated_raw_steps, related_page_function_descriptions_list)
        generated_steps = self._ask_llm_to_rewrite_test_step(prompt_to_rewrite_test_step)
        # print(f'generated_steps\n{generated_steps}')

        # print(generated_steps)
        return generated_steps


if __name__ == "__main__":
    test_case_json_file_path = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\test_cases_code.json"
    full_help_content_json_file_path = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\full_help_content.json"
    page_function_json_file_path = r"E:\Debby\9_Scripts\AIAgentSystem\_Database\page_functions.json"
    current_status = ['In media room']
    desired_goal = ['Eneter Title Room', 'Choose Title Template ("Default")', 'Add to Timeline']
    generator = TestStepGenerator(test_case_json_file_path, page_function_json_file_path, full_help_content_json_file_path, current_status, desired_goal)
    generated_steps_string = generator.generate_process()
