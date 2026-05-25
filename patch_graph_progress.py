def update_graph_progress():
    with open('backend/app/agent/graph.py', 'r') as f:
        content = f.read()

    old_wrapper = """        async def wrapped_node(state: AgentState):
            job_id = state.get("session_id")
            if job_repo and job_id:
                try:
                    job = job_repo.get_job(job_id)
                    if job:
                        job.stage = stage_map.get(node_name, node_name)
                        job_repo.save_job(job)
                except Exception as e:
                    print(f"Non-critical: Failed to update job progress: {e}")

            # If the node is a compiled subgraph (Runnable), use ainvoke
            if hasattr(node_func, "ainvoke"):
                return await node_func.ainvoke(state)

            # If it's a coroutine function, await it
            if asyncio.iscoroutinefunction(node_func):
                return await node_func(state)

            # Otherwise, call it directly
            return node_func(state)"""

    # We want to intercept the result, update state, and then save again if transform
    new_wrapper = """        async def wrapped_node(state: AgentState):
            job_id = state.get("session_id")
            if job_repo and job_id:
                try:
                    job = job_repo.get_job(job_id)
                    if job:
                        job.stage = stage_map.get(node_name, node_name)
                        job_repo.save_job(job)
                except Exception as e:
                    print(f"Non-critical: Failed to update job progress: {e}")

            # Execute node
            result = None
            if hasattr(node_func, "ainvoke"):
                result = await node_func.ainvoke(state)
            elif asyncio.iscoroutinefunction(node_func):
                result = await node_func(state)
            else:
                result = node_func(state)

            # If transform step finished, save the json
            if node_name == "transform" and job_repo and job_id and result and "transformed_document_json" in result:
                try:
                    job = job_repo.get_job(job_id)
                    if job:
                        job.transform_json = result["transformed_document_json"]
                        job_repo.save_job(job)
                except Exception as e:
                    print(f"Non-critical: Failed to save transform_json: {e}")

            return result"""

    if old_wrapper in content:
        content = content.replace(old_wrapper, new_wrapper)
        with open('backend/app/agent/graph.py', 'w') as f:
            f.write(content)
        print("Updated wrapped_node in graph.py")
    else:
        print("Could not find wrapped_node in graph.py")

update_graph_progress()
