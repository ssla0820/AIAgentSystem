 
import openai
import base64
import os
import configparser

class ChatAPIConnector():
    def __init__(self):
        self.api_key = self._get_api_key()
        self.client = openai.OpenAI(api_key=self.api_key)

    def _get_api_key(self):
        CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.config"))
        if not os.path.exists(CONFIG_FILE):
            raise FileNotFoundError(f"Config file '{CONFIG_FILE}' not found.")

        # Create a ConfigParser instance and preserve key case
        config = configparser.ConfigParser()
        config.optionxform = lambda option: option  # preserve case
        config.read(CONFIG_FILE)
        return config.get('General', 'API_KEY')

    def _encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def generate_chat_response(self, prompt, system_role_msg, has_image=False, model="gpt-4o"):
        messages=[
            {"role": "system", "content": system_role_msg},
            {"role": "user", "content": prompt}
        ]

        if has_image:
            image_path = "path/to/image.png"
            image_base64 = self._encode_image(image_path)
            messages.append({"role": "user", "content": "Here is the screenshot for reference.", "image_url": f"data:image/png;base64,{image_base64}"})

        response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7  # Adjust for randomness
            )
        return response.choices[0].message.content

if __name__ == "__main__":
    chat_api = ChatAPIConnector()
    response = chat_api.generate_chat_response("How do I reset my password?", "You can reset your password by following these steps:")
    print(response)