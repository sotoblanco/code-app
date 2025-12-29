from google import genai
import os
import json
import re
from typing import Dict, Any

class AIService:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Warning: GEMINI_API_KEY not found in environment variables.")
        else:
            self.client = genai.Client(api_key=api_key)

    def generate_exercise(self, prompt: str) -> Dict[str, Any]:
        """
        Generates a coding exercise based on a prompt.
        Returns a dictionary with title, description, starting_code, and test_cases.
        """
        if not hasattr(self, "client"):
             return {"error": "AI service not configured"}

        full_prompt = f"""
        Create a coding exercise based on this request: "{prompt}".
        Provide the response in raw JSON format (no markdown code blocks) with the following structure:
        {{
            "title": "Exercise Title",
            "description": "Markdwon description of the problem",
            "starting_code": "code stub",
            "test_cases": "python code validation logic"
        }}
        """
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            text = response.text.strip()
            
            # Try to find JSON within code blocks first
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Fallback: try to find the first '{' and last '}'
                first_brace = text.find("{")
                last_brace = text.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    json_str = text[first_brace : last_brace + 1]
                else:
                    json_str = text

            return json.loads(json_str)
        except Exception as e:
            print(f"Error parsing AI response: {e}")
            # print(f"Raw response: {response.text}") # response might not exist if generation failed
            return {"error": f"Failed to generate valid exercise data: {str(e)}"}

    def chat(self, message: str, context: str = "") -> str:
        """
        Chat with the AI about implementation details.
        """
        if not hasattr(self, "client"):
             return "AI service not configured."

        full_prompt = f"Context: {context}\n\nUser: {message}"
        try:
            # Using the new SDK's generate_content for single turn, or we could use chats.create for multi-turn
            # For now, sticking to single turn as per original implementation
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=full_prompt
            )
            return response.text
        except Exception as e:
            return f"Error communicating with AI: {str(e)}"

ai_service = AIService()
