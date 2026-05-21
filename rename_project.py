import os

target_dir = r"d:\Project"
exclude_dirs = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".next", "coverage", ".vscode"}

for root, dirs, files in os.walk(target_dir):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        filepath = os.path.join(root, file)
        
        # skip non-text files and the script itself
        if file.endswith(('.pyc', '.png', '.gif', '.ico', '.jpg', '.jpeg', '.pdf', '.docx', '.zip')) or file == "rename_project.py":
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'readitall' in content.lower() or 'read-it-all' in content.lower() or 'read it all' in content.lower():
                # perform replacements
                new_content = content.replace('readitall', 'cognimend')
                new_content = new_content.replace('ReadItAll', 'Cognimend')
                new_content = new_content.replace('READITALL', 'COGNIMEND')
                new_content = new_content.replace('Readitall', 'Cognimend')
                
                # Also handle read-it-all
                new_content = new_content.replace('read-it-all', 'cognimend')
                new_content = new_content.replace('Read-It-All', 'Cognimend')
                
                # Also handle Read It All
                new_content = new_content.replace('Read It All', 'Cognimend')
                new_content = new_content.replace('read it all', 'cognimend')
                
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    f.write(new_content)
        except Exception as e:
            # might be a binary file that wasn't excluded or unreadable
            pass

print("Replacement complete.")
