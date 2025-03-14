from sentence_transformers import SentenceTransformer, util
import json
import os
import sys
parent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(parent_path)


from _ChatAPIConnector.ChatAPIConnector import ChatAPIConnector


class Generator():
    def __init__(self, full_help_content_json_file_path, current_status, desired_goal):
        with open(full_help_content_json_file_path, "r", encoding="utf-8") as file:
            self.full_help_content = json.load(file)
        self.threshold = 0.5

        self.model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
        self.chat_api_connector = ChatAPIConnector()

        self.current_status = current_status
        self.desired_goal = desired_goal


    def _get_related_func_in_help(self):
        # Define your query sentence
        query = f"Current Status is: {current_status} and Desired Goal is: {desired_goal}"
        query_embedding = self.model.encode(query, convert_to_tensor=True)

        results = []

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
        # Print the results
        for item in results:
            refer_data_list.append(f"{item['heading']}: {item['summary']}")
        
        return refer_data_list

    def _get_prompt(self, refer_data_list):
        prompt = f'''I will provide the current status of our PowerDirector UI and the desired goal. Please refer to following "Refer Data" for details. Now, generate only the step-by-step instructions required to transition from the current UI to the desired state. Steps must include:
- Action: Describe the specific change or modification to be made. Add [Action] at the beginning.
- Verify: Specify how to confirm that the change has been successfully implemented. Add [Verify] at the beginning.
List the steps sequentially with no additional commentary. Only Focus on to the steps to reach the desired goal only.


Refer Data: {refer_data_list}
Current Status: {self.current_status}
Desired Goal: {self.desired_goal}
'''
        return prompt
    
    def _ask_llm(self, prompt):
        system_role_msg = "Interpret the provided refer data, current UI status, and desired goal to generate a precise, step-by-step instruction list for transitioning the UI. Each step must clearly start with either [Action] or [Verify] and follow the sequence strictly. Do not add any extra commentary—only output the necessary steps."
        return self.chat_api_connector.generate_chat_response(prompt, system_role_msg)

    def _generated_steps_to_list(self, generated_row_steps):
        return generated_row_steps.split('\n')
    
    def _mapping_page_functions(self):
        pass

    def generate_process(self):
        refer_data_list = self._get_related_func_in_help()
        prompt = self._get_prompt(refer_data_list)
        generated_row_steps = self._ask_llm(prompt)
        generated_steps_list = self._generated_steps_to_list(generated_row_steps)
        generated_steps_string = self._mapping_page_functions()
        return generated_steps_string


if __name__ == "__main__":
    full_help_content_json_file_path = r"E:\Debby\9_Scripts\AIAgentSystem\GetHelpData\Help.json"
    current_status = 'PowerDirector is not launched'
    desired_goal = 'Download media from Stock Content'
    generator = Generator(full_help_content_json_file_path, current_status, desired_goal)
    generated_steps_string = generator.generate_process()


    import pyperclip
    pyperclip.copy(generated_steps_string)