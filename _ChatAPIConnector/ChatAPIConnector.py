 
import openai
import base64

class ChatAPIConnector():
    def __init__(self):
        self.api_key = "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"
        self.client = openai.OpenAI(api_key=self.api_key)

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