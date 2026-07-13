import csv
import glob
import json
import os

import threading
import utils.config_yaml as config_env
import concurrent.futures
import tqdm

CONFIG = config_env.load_yaml_config("env.yaml")

HEX_ROOT_DIR = CONFIG["HEX"]["ROOT_DIR"]
GIG_ROOT = CONFIG["GIGA"]["ROOT"]
GIG_INPUT_DIR = CONFIG["GIGA"]["IN_DIR"]
OUTPUT_DIR = os.path.basename(HEX_ROOT_DIR)
GIG_OUTPUT_DIR = CONFIG["GIGA"]["OUT_DIR"]
GIGA_RULES = CONFIG["GIGA"]["RULES"]
THREAD_NUMBER = CONFIG["THREAD_NUMBER"]

# lock
lock = threading.Lock()

def read_csv_to_array(file_path):
    array = []
    with open(file_path, mode="r", newline="", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            array.append(row)
    return array

def append_to_json_file(map_data, file_path):
    with lock:
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        if not os.path.exists(file_path):
            with open(file_path,"w") as file:
                pass
        data_str = json.dumps(map_data, ensure_ascii=False)
        
        with open(file_path, mode="a", encoding="utf-8") as file:
            if file.tell() > 0:
                file.write("\n")
            file.write(data_str)

def read_from_json_file(file_path):
    all_data = []

    # Check if the file exists
    if not os.path.exists(file_path):
        return all_data  # Return an empty list if the file does not exist

    # Open the file and read line by line
    with open(file_path, mode="r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()  # Remove leading and trailing whitespace
            if line:  # Ensure the line is not empty
                # Remove trailing comma to avoid JSON parsing errors
                line = line.rstrip(",")
                try:
                    # Convert each line into a JSON object
                    json_data = json.loads(line)
                    all_data.append(json_data)
                except json.JSONDecodeError:
                    continue  # Skip the line if there is a JSON decoding error

    return all_data

def process_hex_file(hex_file):
    print(f"process_hex_file: {hex_file}\n")
    with open(hex_file, "r") as file:
        content = file.read()


    address = os.path.splitext(os.path.basename(hex_file))[0]

    # os.system("pwd")
    # os.system(f"echo \"sudo bash ./run_analysis.sh ./clients/analyze.dl ./examples/{address}.hex > /dev/null 2>&1\"")
    os.system(f"sudo bash ./run_analysis.sh ./clients/analyze.dl {hex_file} > /dev/null 2>&1")


    rule_dir = os.path.join(GIG_OUTPUT_DIR, address, "out")
    if os.path.isdir(rule_dir):
        for rule in GIGA_RULES:
            rule_output_file = os.path.join(rule_dir, rule + ".csv")
            if os.path.isfile(rule_output_file):
                rule_data = read_csv_to_array(rule_output_file)
                
                if rule_data:
                    # if rule != "AM_FuncInfo": 
                    #     print(f"\nDetector: Success on {address} - {rule}")
                    detect_map = {"address": address, "path": hex_file, "result": rule_data}
                    append_to_json_file(detect_map, f"./../detect_{OUTPUT_DIR}/{rule}.jsonl")
    else:
        print(f"ERROR: {rule_dir} Not Found")
    os.system(f"sudo rm -rf {os.path.join(GIG_OUTPUT_DIR, address)}")

    
def main():

    hex_dir = HEX_ROOT_DIR
    print(f"works_on: {hex_dir}")

    hex_files = glob.glob(os.path.join(hex_dir, "**", "*.hex"), recursive=True)
    original_cwd = os.getcwd()
    os.chdir(GIG_ROOT)

    with concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_NUMBER) as executor:
        # submit 
        futures = [executor.submit(process_hex_file, hex_file) for hex_file in hex_files]


    os.chdir(original_cwd)


if __name__ == "__main__":
    
    print("---start---")

    main()

    print("---end---")

