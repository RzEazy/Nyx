## Usage
### Create Python Virtual Environment

Create a virtual environment and activating a virtual environment using: 
```bash
python3.12 -m venv venv
source bin/activate (In Linux)
.\Script\activate (In Windows)
```

### Install Dependencies
Nyxen requires various packages. Install these dependencies using:
```bash
pip install -r requirements.txt
```

### API Key
If you are using cohere as your service provider, copy your API Key and edit ```src/app.py``` and set ```python "API_KEY"```  as you cohere API Key.

### Usage
Finally, Nyxen is ready to use. Run: ```bash python3.12 app.py```. This will start a CLI and also automatically generate a JSON file, name "Nyxen_memory.json", which basically is a conversation history. A file will only be automatically be generated if, no memory file is found, in the directory. 


## DISCLAIMER
This project is still in a alpha stage, BUGS and Glitches are not yet patched. 

Thank You.
