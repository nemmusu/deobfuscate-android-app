# Deobfuscate Android App (Forked)

This repository is a fork of the original "Deobfuscate Android App" project. It uses Google's Gemini public API to find potential security vulnerabilities in Android apps and to deobfuscate Android app code.

**Note:** The screenshots shown below are from the original repository and are not produced by this fork.

Android apps generally use Proguard or similar tools for obfuscation, making reverse engineering challenging. Large Language Models (LLMs) can sometimes assist by identifying the context of code, renaming variables/functions for better readability, and commenting code sections. Of course, results vary, and the output may not always be perfect.

## Description

**Input:** Takes a decompiled code directory as input.

**Output:**
1. A JSON file named `vuln_report` will be created in the provided output directory, listing discovered security risks and their impact.
2. If the `--save_code` flag is used, the tool will deobfuscate and save the processed code for easier manual review, tagging any identified security issues with `#SECURITY-ISSUE`.

## Additional Improvements (Global Context)

This fork introduces an enhancement:
- The tool can now generate a global context (`GlobalContext`) before analyzing individual files. 
- It first collects class/method information from all Java files, sends it to the LLM using `global_prompt.txt`, and receives a summarized context.
- This `GlobalContext` is then included for each file analysis, giving the model better understanding of cross-file relationships and potentially improving the accuracy of the deobfuscation and vulnerability detection.

To use this feature, ensure `global_prompt.txt` is present. The script will:
- Generate a global map of classes and methods.
- Query the LLM once for a global summary.
- Use that summary when analyzing each file.

## Installation

### 1. Clone the repo (Forked version)

### 2. Install dependencies

pip3 install -r requirements.txt

### 3. Decompile APK

Use [jadx](https://github.com/skylot/jadx) to decompile the APK:

jadx androidapp.apk

You will have a `sources` directory with the decompiled `.java` files.

### 4. Run the script
Set your Gemini API key:

export GEMINI_API_KEY="Your Gemini API Key"

You can get the API key from [https://ai.google.dev](https://ai.google.dev/)

Example command:

python3 script.py --llm_model gemini-1.5-flash --output_dir /tmp/ver/ --source_dir "input_dir1/ input_dir2/"

**Parameters:**
- `--llm_model`: Choose the LLM model variant (only Google's Gemini supported).
- `--output_dir`: Where to save generated reports and optionally the code.
- `--source_dir`: One or more directories containing the decompiled `.java` files.
- `--save_code` (optional): If `True`, saves the deobfuscated code in the output directory.

**Note:**  
Do not process the entire codebase at once (including all libraries). Focus on the relevant parts of the app's package. For example, if the app code is in `com/google/android/yourapp/`, pass only `com/google/android/yourapp/receivers/` or a specific subdirectory to avoid very large runs.

## Demo

**Note:** The following screenshots are from the original repository and not produced by this fork.

Decompiled code (Obfuscated):

![Original Screenshot - Obfuscated Code](https://github.com/user-attachments/assets/1908bbd7-3354-4fcc-adbb-64dee857ae2d)

Decompiled code (After processing with LLM):

![Original Screenshot - Deobfuscated Code](https://github.com/user-attachments/assets/a9c8d34d-3a24-4f64-819a-b908a8dc815f)

Security Issues identified by LLM:

![Original Screenshot - Identified Security Issues](https://github.com/user-attachments/assets/bba67dd9-69e8-4323-b696-203a232a33cd)

## Contributing

See [`CONTRIBUTING.md`](docs/CONTRIBUTING.md) for details.

## License

Apache 2.0; see [`LICENSE`](LICENSE) for details.

## Disclaimer

This is a fork of an experimental project. It is not affiliated with or supported by the original authors. Use at your own risk.  
It is not an official Google project. It is not supported by Google, and Google disclaims all warranties as to its quality, merchantability, or fitness for a particular purpose.  
Review the Gemini API TOS before using the tool: https://ai.google.dev/gemini-api/terms


