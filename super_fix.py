import re

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "r") as f:
    content = f.read()

# Fix anything that looks like `{((...)).toFixed(1)}` or `{(...)).toFixed(1)}`
# We want EXACTLY `{((some_expression || 0) * 100).toFixed(1)}`

content = re.sub(r'\{\(\(incident([^}]+)\s*\*\s*100\)\)\.toFixed\(1\)', r'{((incident\1 * 100)).toFixed(1)', content)
content = re.sub(r'\{\(incident([^}]+)\s*\*\s*100\)\)\.toFixed\(1\)', r'{((incident\1 * 100)).toFixed(1)', content)
content = re.sub(r'\{\(\(incident([^}]+)\s*\*\s*100\)\.toFixed\(1\)', r'{((incident\1 * 100)).toFixed(1)', content)
content = re.sub(r'\{\(incident([^}]+)\s*\*\s*100\)\.toFixed\(1\)', r'{((incident\1 * 100)).toFixed(1)', content)

# same for segmentData
content = re.sub(r'\{\(\(segmentData([^}]+)\s*\*\s*100\)\)\.toFixed\(1\)', r'{((segmentData\1 * 100)).toFixed(1)', content)
content = re.sub(r'\{\(segmentData([^}]+)\s*\*\s*100\)\)\.toFixed\(1\)', r'{((segmentData\1 * 100)).toFixed(1)', content)
content = re.sub(r'\{\(\(segmentData([^}]+)\s*\*\s*100\)\.toFixed\(1\)', r'{((segmentData\1 * 100)).toFixed(1)', content)
content = re.sub(r'\{\(segmentData([^}]+)\s*\*\s*100\)\.toFixed\(1\)', r'{((segmentData\1 * 100)).toFixed(1)', content)

# But wait! If I replace it with `{((incident\1 * 100)).toFixed(1)}`, `\1` already contains the `|| 0)`!
# e.g., `incident.success_rate_evidence.baseline_success_rate || 0)`
# So `{((incident.success_rate_evidence.baseline_success_rate || 0) * 100)).toFixed(1)}` is WRONG because of the inner paren not opened by `((`?
# YES! `{ ((incident... || 0) * 100).toFixed(1) }` -> THIS IS CORRECT. 2 opens: one before `incident` (no, before `(incident`), and one for `(`.
# Let's write a python script that just does:
def fix_line(match):
    inner = match.group(1).replace('(', '').replace(')', '') # just strip all parens and rewrite properly!
    # wait, `incident.error_evidence.baseline.customer_error_rate || 0` is the inner.
    # actually, I can just write:
    return "{(" + match.group(1) + " * 100).toFixed(1)}"

# The easiest way:
# Just replace the whole lines where I know the exact structure!
with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "w") as f:
    f.write(content)
