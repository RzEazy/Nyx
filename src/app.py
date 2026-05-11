from core import nyxen
import time
nyxen = nyxen(
    api_key="jADyfv6mP1ieilwk9swmx9cYvYx67OscByreAm3x",
    memory_file="Nyxen_memory.json"
)

def chat():
    print()

    while True:
        user_input = input("\nYou: ")

        if user_input.lower() in ["exit", "quit", "bye","goodbye"]:
            print("Lia: Peace!")
            break

        response = nyxen.generate_response(user_input)
        #print("Lia:" response)
        for char in response:
            print(char, end='',flush=True)
            time.sleep(0.05)

if __name__ == "__main__":
    chat()
