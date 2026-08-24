import re
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find {(( and replace with {( if there is only one closing parenthesis before .toFixed
    # Actually, let's just do a blanket replacement:
    content = content.replace("{((evidence?.success_rate_evidence?.baseline_success_rate * 100).toFixed(1)}", "{(evidence?.success_rate_evidence?.baseline_success_rate * 100).toFixed(1)}")
    content = content.replace("{((evidence?.success_rate_evidence?.current_success_rate * 100).toFixed(1)}", "{(evidence?.success_rate_evidence?.current_success_rate * 100).toFixed(1)}")
    content = content.replace("{((evidence.error_evidence.baseline.technical_error_rate * 100).toFixed(1)}", "{(evidence.error_evidence.baseline.technical_error_rate * 100).toFixed(1)}")
    content = content.replace("{((evidence.error_evidence.current.customer_error_rate * 100).toFixed(1)}", "{(evidence.error_evidence.current.customer_error_rate * 100).toFixed(1)}")
    content = content.replace("{((evidence.error_evidence.baseline.customer_error_rate * 100).toFixed(1)}", "{(evidence.error_evidence.baseline.customer_error_rate * 100).toFixed(1)}")

    # And for SupportIncidentDetail:
    # {((incident.success_rate_evidence.baseline_success_rate || 0) * 100).toFixed(1)} -> {((incident.success_rate_evidence.baseline_success_rate || 0) * 100).toFixed(1)}
    # wait, `{((incident... || 0) * 100).toFixed(1)}` is ACTUALLY VALID! 
    # Because `(incident... || 0)` is in parens, and we wrap it with `((...) * 100)` -> `( (incident... || 0) * 100 )` -> 2 opening, 2 closing!
    # Let's check `SupportIncidentDetail.tsx`:
    # `{((incident.success_rate_evidence.current_success_rate || 0) * 100).toFixed(1)}%`
    # `{` + `(` + `(` + `incident` + `|| 0` + `)` + `* 100` + `)` + `.toFixed(1)` + `}` -> VALID!
    # So the only invalid ones are the ones without `|| 0` which don't have the inner parens.

    with open(filepath, 'w') as f:
        f.write(content)

for filepath in glob.glob("frontend/src/pages/**/*.tsx", recursive=True):
    process_file(filepath)

