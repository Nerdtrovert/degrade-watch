import re

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "r") as f:
    content = f.read()

# Replace {(... * 100).toFixed(1)}% where the open parenthesis count is wrong
# Specifically, we know `{(incident` followed by `* 100).toFixed(1)}` needs an extra paren.
# So let's just do a regex that replaces `{(incident` with `{((incident` IF it's followed by `.toFixed(1)}` and doesn't already have two parens.
content = re.sub(r'\{\(incident([^\}]+)\* 100\)\.toFixed\(1\)\}', r'{((incident\1* 100)).toFixed(1)}', content)
content = re.sub(r'\{\(segmentData([^\}]+)\* 100\)\.toFixed\(1\)\}', r'{((segmentData\1* 100)).toFixed(1)}', content)

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "w") as f:
    f.write(content)
