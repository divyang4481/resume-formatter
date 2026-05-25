import subprocess

def stop_service(cluster, service):
    print(f"Stopping service {service} (setting desired-count to 0)...")
    cmd = ["aws", "ecs", "update-service", "--cluster", cluster, "--service", service, "--desired-count", "0"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error stopping {service}: {result.stderr}")
    else:
        print(f"Service {service} stopped successfully.")

if __name__ == "__main__":
    cluster = "agentic-doc-cluster-dev"
    stop_service(cluster, "api-service-dev")
    stop_service(cluster, "worker-service-dev")
    stop_service(cluster, "frontend-service-dev")
