import re

file_path = 'insert_today_ideas_v5.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken string literals
content = re.sub(r'체결\.\n"', r'체결.\\n"', content)
content = content.replace('협력.\n"', '협력.\\n"')
content = content.replace('시현.\n"', '시현.\\n"')
content = content.replace('유지.\n"', '유지.\\n"')
content = content.replace('착수.\n"', '착수.\\n"')
content = content.replace('예정.\n"', '예정.\\n"')
content = content.replace('급등).\n"', '급등).\\n"')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Successfully fixed insert_today_ideas_v5.py')
