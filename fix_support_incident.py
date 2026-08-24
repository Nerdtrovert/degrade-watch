with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "r") as f:
    content = f.read()

bad_string = r"check.result === 'PASS' ? 'text-green-600' : 'text-red-600' === \'text-green-600\' ? \'bg-emerald-50 text-emerald-700 border-emerald-200\' : \'bg-red-50 text-red-700 border-red-200\'"
good_string = "check.result === 'PASS' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'"

content = content.replace(bad_string, good_string)

with open("frontend/src/pages/support/SupportIncidentDetail.tsx", "w") as f:
    f.write(content)
