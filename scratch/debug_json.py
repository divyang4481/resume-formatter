import json
import sys
with open(r'scratch\latest_job_data.json', 'r', encoding='utf-8') as f:
    job_data = json.load(f)

def print_keys(data, indent=""):
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"{indent}{k} (type: {type(v).__name__})")
            if isinstance(v, (dict, list)):
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    print(f"{indent}  [0] (type: dict)")
                    print_keys(v[0], indent + "    ")
                else:
                    print_keys(v, indent + "  ")

print_keys(job_data)
