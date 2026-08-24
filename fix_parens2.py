import re
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Revert to original (before * 100).toFixed(1))
    # Or just replace `{\(\(.*\)\.toFixed\(1\)\)}%`
    # Let's fix the extra closing paren
    content = re.sub(r'\{\(\((.*?)\s*\*\s*100\)\.toFixed\(1\)\)\}\%', r'{(\1 * 100).toFixed(1)}%', content)
    
    # What about the ones that missed the first pass? e.g.
    # {incident.success_rate_evidence.statistical_significance.confidence_level * 100).toFixed(1)}%
    content = re.sub(r'\{([^\(]+?)\s*\*\s*100\)\.toFixed\(1\)\}\%', r'{(\1 * 100).toFixed(1)}%', content)
    
    # Also in MerchantIncidentDetail there was a case: `(evidence?.success_rate_evidence?.baseline_success_rate * 100).toFixed(1)` that was already correct.

    with open(filepath, 'w') as f:
        f.write(content)

for filepath in glob.glob("frontend/src/pages/**/*.tsx", recursive=True):
    process_file(filepath)

