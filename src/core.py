import cohere
import json
import subprocess

class nyxen:
    def __init__(self, api_key, memory_file="Nyxen_memory.json"):
        self.co = cohere.Client(api_key)
        self.memory_file = memory_file
        self.load_memory()

    def load_memory(self):
        try:
            with open(self.memory_file, "r") as f:
                self.memory = json.load(f)
        except:
            self.memory = {
                "conversations": [],
                "personal_info": {}
            }
            self.save_memory()

    def save_memory(self):
        with open(self.memory_file, "w") as f:
            json.dump(self.memory, f, indent=4)

    def generate_response(self, user_input):

        # Run command feature
        if user_input.lower().startswith("run command"):
            command = user_input.replace("run command", "").strip()
            return self.run_system_command(command)

        # Build prompt
        prompt = self.build_prompt(user_input)

        # Updated Cohere Chat call (2025 model)
        response = self.co.chat(
            model="command-a-03-2025",
            stop_sequences=["User: "],
            message=prompt,
            temperature=0
        )

        ai_response = response.text.strip()

        # Save to memory
        self.memory["conversations"].append({
            "user": user_input,
            "Nyxen": ai_response
        })
        self.save_memory()

        return ai_response

    def build_prompt(self, user_input):
        # Last 10 messages
        history = ""
        for conv in self.memory["conversations"][-10:]:
            history += f"User: {conv['user']}\nNyxen: {conv['Nyxen']}\n"

        # Clean, Gen-Z, no cringe tone
        return (
            f"{history}"
            f"User: {user_input}\nNyxen:"
        )

    def run_system_command(self, command):
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return f"Command Output:\n{result.stdout}"
            else:
                return f"Command Error:\n{result.stderr}"
        except Exception as e:
            return f"Command Failed: {str(e)}"
