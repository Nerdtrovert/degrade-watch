import re

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "r") as f:
    content = f.read()

# I will find every instance of `%</p>` or `%</li>` or `pp</p>` that has `.toFixed(1)` and rewrite it.
def replacer(m):
    full = m.group(0)
    # Extract the variable part, e.g. `incident.error_evidence.baseline.customer_error_rate`
    # It might have `|| 0`
    var_match = re.search(r'(incident[\w\.]+|segmentData[\w\.]+)', full)
    if not var_match: return full
    var = var_match.group(1)
    
    if "points" in full or "pp" in full:
        suffix = " pp</p>"
    elif "</li>" in full:
        suffix = "%</li>"
    else:
        suffix = "%</p>"
        
    prefix_match = re.search(r'(<p><strong>.*?</strong> |<li>Success Rate: )', full)
    if not prefix_match:
        if "Confidence Level:" in full:
            prefix = "<p>Confidence Level: "
        else:
            return full
    else:
        prefix = prefix_match.group(1)
        
    return f"{prefix}{{({var} * 100).toFixed(1)}}{suffix}"

content = re.sub(r'<p><strong>.*?</strong> \{.*?\.toFixed\(1\).*?</p>', replacer, content)
content = re.sub(r'<li>Success Rate: \{.*?\.toFixed\(1\).*?</li>', replacer, content)
content = re.sub(r'<p>Confidence Level: \{.*?\.toFixed\(1\).*?</p>', replacer, content)

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "w") as f:
    f.write(content)
