import re
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find: { ( ... ) * 100 ).toFixed(1)}%
    # Replace with: {(( ... ) * 100).toFixed(1)}%
    # Wait, the regex replaced `(expr || 0) * 100` with `(expr || 0) * 100).toFixed(1)`.
    # Let's just fix it by adding the opening paren after `{`
    
    # We want to replace `{((` ? No, currently it is `{(incident... || 0) * 100).toFixed(1)}%`
    # We need it to be `{((incident... || 0) * 100).toFixed(1)}%`
    
    # Let's just replace `{(incident` with `{((incident` where it ends with `.toFixed(1)}%`
    # Actually, a simpler way:
    content = re.sub(r'\{(\([^\)]+\)\s*\*\s*100\)\.toFixed\(\d\))\}%', r'{(\1)}%', content)
    # Wait, `(\([^\)]+\)\s*\*\s*100)` means `(expr) * 100`. So it becomes `{( (expr) * 100 ).toFixed(1)}%`.
    
    with open(filepath, 'w') as f:
        f.write(content)

for filepath in glob.glob("frontend/src/pages/**/*.tsx", recursive=True):
    process_file(filepath)

