import re
import sys

def main():
    conf_path = '/opt/homebrew/var/postgresql@18/pg_hba.conf'
    with open(conf_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # Replace local connection method to trust
        if re.match(r'^\s*local\s+all\s+all\s+', line):
            line = re.sub(r'\s+\S+$', ' trust', line)
        # Replace host IPv4 connection method to trust
        elif re.match(r'^\s*host\s+all\s+all\s+127\.0\.0\.1/32\s+', line):
            line = re.sub(r'\s+\S+$', ' trust', line)
        # Replace host IPv6 connection method to trust
        elif re.match(r'^\s*host\s+all\s+all\s+::1/128\s+', line):
            line = re.sub(r'\s+\S+$', ' trust', line)
        new_lines.append(line)

    with open(conf_path, 'w') as f:
        f.writelines(new_lines)

if __name__ == '__main__':
    main()