import re
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # We want to replace {(something * 100).toFixed(1)}% with {((something * 100).toFixed(1)}%
    # Note: `something` here can be `(incident... || 0)`.
    # Let's match `{` followed by `(` (optional) followed by stuff, followed by `* 100).toFixed(1)}%`
    
    # Actually, let's just do a plain string replacement for all the known broken patterns.
    # The broken pattern is: `{(` or `{` followed by `... * 100).toFixed(1)}%` where the parenthesis before `.toFixed` has no matching open paren.
    
    # Let's strip ALL `.toFixed(1)` that I added earlier and do it cleanly:
    
    # First, let's remove `.toFixed(1)` where it is broken:
    # Pattern: `{([^}]+)\)\.toFixed\(1\)\}\%`
    # Replace with: `{\1}%`
    content = re.sub(r'\{([^\}]+)\)\.toFixed\(1\)\}\%', r'{\1}%', content)
    
    # Now it is back to `{(incident.success_rate_evidence.baseline_success_rate || 0) * 100}%`
    
    # Now cleanly add `.toFixed(1)` to ALL `{ ... * 100 }%`
    # We want to wrap the inside of `{...}` in `(...).toFixed(1)`
    content = re.sub(r'\{([^\}]+?\*\s*100)\}\%', r'{(\1).toFixed(1)}%', content)

    with open(filepath, 'w') as f:
        f.write(content)

for filepath in glob.glob("frontend/src/pages/**/*.tsx", recursive=True):
    process_file(filepath)

