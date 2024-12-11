import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from absl import app, flags
from typing import Sequence
import os
import traceback
import sys
import json
import threading
import asyncio
from collections import defaultdict
from google.api_core.exceptions import ResourceExhausted
import re

_LLM_MODEL = flags.DEFINE_string(
    'llm_model', None, 'LLM Model to use')
_OUTPUT_DIR = flags.DEFINE_string(
    'output_dir', None, 'the output directory to save the report and source code (if flag provided)')
_SOURCE_DIR = flags.DEFINE_spaceseplist('source_dir', [], 'List of Directory of the Source code')
_SAVE_CODE = flags.DEFINE_boolean(
    'save_code', False, 'If provided we will save the deobfuscated code')
_THREAD_SIZE = flags.DEFINE_integer(
    'thread_size',1, 'No. of threads to use for concurrent requests to Gemini')

output_data_lock = threading.Lock()
output_data = defaultdict(list)

global_context = None
prompt = None
global_prompt = None

def find_java_files(directory):
    java_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root,file))
    return java_files

def read_file_content(file_path):
    with open(file_path, 'r',encoding="utf-8") as file:
      content = file.read()+"\n\n"
    return content

def extract_class_and_method_signatures(file_path):
    # Simple extraction of classes and methods from a Java file.
    # This is a basic regex approach and can be improved as needed.
    content = read_file_content(file_path)
    classes = re.findall(r'class\s+(\w+)', content)
    methods = re.findall(r'(public|private|protected)?\s+(static\s+)?(\w+|\<\w+\>)\s+(\w+)\(.*?\)', content)
    method_names = [m[3] for m in methods]
    return classes, method_names

def build_global_map(code_files):
    global_info = {"files":{}}
    for f in code_files:
        classes, methods = extract_class_and_method_signatures(f)
        global_info["files"][f] = {
            "classes": classes,
            "methods": methods
        }
    return global_info

async def send_code_to_gemini(client,files_data):
    retry_delay = 2
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response_template =  await client.generate_content_async([files_data],
            safety_settings={
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            })
            return response_template.text
        except ResourceExhausted as e:
            print(f"Rate limit error: {e}")
            print(f"Retrying in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2
        except Exception as e:
            print(f"Gemini API Error: {e}")
            traceback.print_exc()
            sys.exit()

def process_response(response_text,file_path,output_dir):
    with output_data_lock:
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(response_text)

        java_code = data.get('Code', '')
        if _SAVE_CODE.value:
            create_unobfuscated_code_files(output_dir,file_path,java_code)

        vulnerabilities = data.get('Vulnerabilities', [])
        if len(vulnerabilities) > 0:
            output_data[file_path].extend(vulnerabilities)

def create_unobfuscated_code_files(code_output_directory, file_path, java_code):
    directory = os.path.join(code_output_directory,os.path.dirname(file_path))
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    full_file_path = os.path.join(code_output_directory, file_path)
    with open(full_file_path, 'a+',encoding="utf-8") as output_file:
        output_file.write(java_code)

    print(f"Created file: {full_file_path}")

def write_vuln_output(output_vuln_dir):
    output_json = {}
    
    for file_name, vulnerabilities in output_data.items():
        output_json[file_name] = vulnerabilities
    
    with open(output_vuln_dir, "w+", encoding="utf-8") as output_file:
        json.dump(output_json, output_file, indent=4)

async def process_code_files(semaphore, file_path, global_context):
    async with semaphore:
        try:
            content = read_file_content(file_path)
            
            # Construct the final input by combining global_context, prompt, and the file content.
            final_input = f"{global_context}\n\n{prompt}\n\nFILE:\n{content}"

            client = genai.GenerativeModel(_LLM_MODEL.value,
                                           system_instruction="")
            print(f"Processing file {file_path} with Semaphore : {semaphore._value}")

            response =  await send_code_to_gemini(client,final_input)

            process_response(response,file_path,_OUTPUT_DIR.value)
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            traceback.print_exc()
        finally:
            print(f"File processing completed {file_path}.")

async def main(argv: Sequence[str]) -> None:
    flags.FLAGS(argv)
    if _LLM_MODEL.value is None or _OUTPUT_DIR.value is None or  len(_SOURCE_DIR.value) == 0:
        raise app.UsageError(
            f'Usage: {argv[0]} -llm_model=<LLM Model to use> -output_dir=<output directory> -source_dir=<source directory>'
        )
    if os.environ.get('GEMINI_API_KEY') is None:
        raise app.UsageError('Set GEMINI_API_KEY in the environment')

    genai.configure(api_key=os.environ['GEMINI_API_KEY'])

    semaphore = asyncio.Semaphore(_THREAD_SIZE.value)
    
    global prompt
    global global_prompt
    global global_context

    # Load the file-level prompt (unchanged)
    with open("prompt.txt", 'r',encoding="utf-8") as file:
        prompt = file.read()

    # Load the global prompt
    with open("global_prompt.txt", 'r',encoding="utf-8") as file:
        global_prompt = file.read()

    # Find all java files
    code_files = []
    for source_dirs in _SOURCE_DIR.value:
        code_files = code_files + find_java_files(source_dirs)

    if len(code_files) == 0:
        print("No decompiled java files found")
        return

    # Build a global map of the project
    global_map = build_global_map(code_files)

    client = genai.GenerativeModel(_LLM_MODEL.value, system_instruction="")

    # Convert the global map to JSON and send to the model with the global prompt
    global_map_str = json.dumps(global_map, indent=4)
    global_input = f"{global_prompt}\n\n{global_map_str}"
    global_context_response = await send_code_to_gemini(client, global_input)

    # Attempt to parse the global context as JSON
    try:
        global_context_data = json.loads(global_context_response)
        global_context_text = global_context_data.get("GlobalContext","")
    except:
        # If not valid JSON, just use the raw response
        global_context_text = global_context_response

    tasks = []
    for file_path in code_files:
        task = asyncio.create_task(
            process_code_files(semaphore, file_path, global_context_text)
        )
        tasks.append(task)

    await asyncio.gather(*tasks)

    if (len(output_data.items()) > 0):
        output_vuln_path = os.path.join(_OUTPUT_DIR.value,"vuln_report")
        write_vuln_output(output_vuln_path)
        print("Vulnerability report created at " + output_vuln_path)
    else:
        print("No Vulnerability found to report")


if __name__ == '__main__':
    asyncio.run(main(sys.argv))
