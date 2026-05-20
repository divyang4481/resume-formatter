def add_typing_imports():
    with open('backend/app/api/admin.py', 'r') as f:
        content = f.read()

    if 'from typing import ' not in content or 'List,' not in content:
        content = 'from typing import List, Dict, Any\n' + content
        with open('backend/app/api/admin.py', 'w') as f:
            f.write(content)
            print("Added typing imports")

add_typing_imports()
