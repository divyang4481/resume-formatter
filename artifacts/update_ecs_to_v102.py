import json
import subprocess
import sys
import os

def update_and_register(family, original_file, new_tag):
    try:
        with open(original_file, 'r', encoding='utf-16') as f:
            data = json.load(f)
    except:
        try:
            with open(original_file, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
        except:
            with open(original_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
    
    task_def = data.get('taskDefinition', data)
    
    # Remove fields not allowed in register-task-definition
    keys_to_remove = [
        'taskDefinitionArn', 'revision', 'status', 'requiresAttributes', 
        'compatibilities', 'registeredAt', 'registeredBy'
    ]
    for key in keys_to_remove:
        task_def.pop(key, None)
    
    # Update image tags
    for container in task_def['containerDefinitions']:
        image = container['image']
        if ':' in image:
            base_image = image.split(':')[0]
            container['image'] = f"{base_image}:{new_tag}"
    
    # Write to a clean JSON file
    clean_file = f"clean_{family}.json"
    with open(clean_file, 'w') as f:
        json.dump(task_def, f, indent=4)
    
    # Register new task definition
    print(f"Registering new task definition for {family} with tag {new_tag}...")
    cmd = ["aws", "ecs", "register-task-definition", "--cli-input-json", f"file://{clean_file}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error registering {family}: {result.stderr}")
        return None
    
    new_task_def = json.loads(result.stdout)['taskDefinition']['taskDefinitionArn']
    print(f"Registered: {new_task_def}")
    return new_task_def

def update_service(cluster, service, task_def_arn):
    print(f"Updating service {service} to use {task_def_arn} and setting desired-count to 1...")
    cmd = ["aws", "ecs", "update-service", "--cluster", cluster, "--service", service, "--task-definition", task_def_arn, "--desired-count", "1"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error updating service {service}: {result.stderr}")
    else:
        print(f"Service {service} updated successfully.")

if __name__ == "__main__":
    cluster = "agentic-doc-cluster-dev"
    
    # Defaults or from command line
    # Usage: python update_ecs.py <api_worker_tag> <frontend_tag>
    api_worker_tag = sys.argv[1] if len(sys.argv) > 1 else "v1.5.1"
    frontend_tag = sys.argv[2] if len(sys.argv) > 2 else "v1.2.5"
    
    print(f"Deploying with tags: API/Worker={api_worker_tag}, Frontend={frontend_tag}")

    # Update API
    api_arn = update_and_register("api", "temp_api_task_def.json", api_worker_tag)
    if api_arn:
        update_service(cluster, "api-service-dev", api_arn)
    
    # Update Worker
    worker_arn = update_and_register("worker", "temp_worker_task_def.json", api_worker_tag)
    if worker_arn:
        update_service(cluster, "worker-service-dev", worker_arn)

    # Update Frontend
    frontend_arn = update_and_register("frontend", "temp_frontend_task_def.json", frontend_tag)
    if frontend_arn:
        update_service(cluster, "frontend-service-dev", frontend_arn)
