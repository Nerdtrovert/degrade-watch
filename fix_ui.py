import re
import os
import glob

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Fix literal CSS class names
    content = re.sub(
        r'<span className="text-xs">\{([^}]+ \? \'text-green-600\' : \'text-red-600\')\}</span>',
        r'<span className={`text-xs font-semibold px-2 py-0.5 rounded border ${ \1 === \'text-green-600\' ? \'bg-emerald-50 text-emerald-700 border-emerald-200\' : \'bg-red-50 text-red-700 border-red-200\'}`}>{check.result}</span>',
        content
    )

    # Note: wait, the matched group \1 is just the ternary expression. It's better to just write it explicitly.
    content = content.replace(
        """<span className="text-xs">{check.result === 'PASS' ? 'text-green-600' : 'text-red-600'}</span>""",
        """<span className={`text-xs font-semibold px-2 py-0.5 rounded border ${check.result === 'PASS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}`}>{check.result}</span>"""
    )

    # Fix floating-point percentages: e.g. * 100}%
    # It looks like: {(incident.success_rate_evidence.baseline_success_rate || 0) * 100}%
    content = re.sub(r'(\([^\)]+\)\s*\*\s*100)\}%', r'\1).toFixed(1)}%', content)
    content = re.sub(r'(\w+\.confidence\s*\|\|\s*0\)\s*\*\s*100)\}%', r'\1).toFixed(1)}%', content)
    content = re.sub(r'(\(\w+\.success_rate\s*\|\|\s*0\)\s*\*\s*100)\}%', r'\1).toFixed(1)}%', content)
    content = re.sub(r'(\(\w+\.\w+\_rate\s*\|\|\s*0\)\s*\*\s*100)\}%', r'\1).toFixed(1)}%', content)

    # But maybe we just want to match ANY expression before `%` that is multiplied by 100.
    content = re.sub(r'(\*\s*100)\}%', r'\1).toFixed(1)}%', content)

    # Fix MerchantIncidentDetail specifically for blank recovery state
    content = content.replace(
        "}`}>{recovery.state}</span>",
        "}`}>{recovery.state || 'NOT_EXECUTED'}</span>"
    )

    # Fix SupportIncidentDetail and ApprovalDetail blank policy decisions
    content = content.replace(
        "<span className={`px-2 py-1 rounded text-xs font-medium ${t.policy_decision.decision===\"AUTO_APPROVED\"?\"bg-green-100 text-green-800\":t.policy_decision.decision===\"HUMAN_APPROVAL\"?\"bg-yellow-100 text-yellow-800\":t.policy_decision.decision===\"BLOCKED\"?\"bg-red-100 text-red-800\":\"bg-gray-100 text-gray-800\"}`}>{t.policy_decision.decision}</span>",
        ""
    )
    # Actually, let's just do simple string replacements for the card styling.
    content = content.replace(
        'className="bg-white p-4 rounded-lg shadow"',
        'className="card overflow-hidden border-slate-300 shadow-sm"'
    )
    content = content.replace(
        'className="text-xl font-bold mb-2"',
        'className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider"'
    )
    content = content.replace(
        'className="text-lg font-bold mb-2"',
        'className="text-sm font-bold text-slate-700 uppercase tracking-wider mb-3 border-b border-slate-100 pb-2"'
    )

    with open(filepath, 'w') as f:
        f.write(content)

for filepath in glob.glob("frontend/src/pages/**/*.tsx", recursive=True):
    process_file(filepath)

