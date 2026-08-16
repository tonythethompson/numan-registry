import json
import re
import sys

def normalize_name(raw_name):
    # Strip (cargo-generate template), (String and HTML templating), (ccommit), by <author>, etc.
    clean = re.sub(r'\s+by\s+.*$', '', raw_name, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\s*\(.*\)$', '', clean).strip()
    clean = clean.lower().replace('-', '_')
    if clean.endswith('.nu'):
        clean = clean[:-3]
    return clean

def main():
    with open('awesome_nu_readme.md', 'r', encoding='utf-8') as f:
        readme_lines = f.readlines()

    with open('d:/Dev/numan_workspace/numan-registry/registry/index.json', 'r', encoding='utf-8') as f:
        registry = json.load(f)

    with open('d:/Dev/numan_workspace/numan-plugins/manifest.json', 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    with open('d:/Dev/numan_workspace/numan-plugins/docs/backlog.json', 'r', encoding='utf-8') as f:
        backlog = json.load(f)

    with open('d:/Dev/numan_workspace/numan-registry/docs/intake-state.json', 'r', encoding='utf-8') as f:
        intake_state = json.load(f)

    item_re = re.compile(r'^- \[([^\]]+)\]\(([^)]+)\):\s*(.*)$')
    sections = {}
    curr_sec = None
    for line in readme_lines:
        m = re.match(r'^##\s+(.*)', line)
        if m:
            curr_sec = m.group(1).strip()
            sections[curr_sec] = []
        elif curr_sec and line.strip().startswith('- ['):
            m_item = item_re.match(line.strip())
            if m_item:
                name, url, desc = m_item.groups()
                sections[curr_sec].append({
                    'name': name.strip(),
                    'url': url.strip(),
                    'desc': desc.strip(),
                })

    reg_pkgs = registry.get('packages', [])
    reg_by_name = {}
    reg_by_repo = {}
    for p in reg_pkgs:
        name = p['id']['name'].lower()
        owner = p['id']['owner'].lower()
        repo = p.get('repo', '').lower().rstrip('/')
        reg_by_name[name] = p
        reg_by_name[f'{owner}/{name}'] = p
        if repo:
            reg_by_repo[repo] = p

    manifest_active = manifest.get('active', [])
    manifest_by_name = {m['name'].lower().replace('-', '_'): m for m in manifest_active}
    manifest_by_repo = {m['repo'].lower(): m for m in manifest_active}

    backlog_plugins = backlog.get('plugins', [])
    backlog_by_name = {}
    backlog_by_repo = {}
    for b in backlog_plugins:
        if 'name' in b:
            backlog_by_name[normalize_name(b['name'])] = b
        if 'repo' in b:
            backlog_by_repo[b['repo'].lower().rstrip('/')] = b

    print("=================================================================")
    print("1. SUMMARY STATS")
    print("=================================================================")
    print("Awesome-Nu Inventory by Category:")
    for s, items in sections.items():
        print(f"  - {s}: {len(items)}")

    print(f"\nNuman Catalog State:")
    print(f"  - Total Packages in registry/index.json: {len(reg_pkgs)}")
    t_counts = {}
    for p in reg_pkgs:
        t_counts[p.get('type')] = t_counts.get(p.get('type'), 0) + 1
    for t, c in sorted(t_counts.items()):
        print(f"      * {t}: {c}")
    print(f"  - numan-plugins active (CI build matrix): {len(manifest_active)}")
    print(f"  - numan-plugins backlog tracking entries: {len(backlog_plugins)}")

    print("\n=================================================================")
    print("2. AWESOME-NU PLUGINS vs NUMAN (PLUGINS)")
    print("=================================================================")
    plugins_items = sections.get('Plugins', [])
    in_registry = []
    in_manifest_not_reg = []
    in_backlog_only = []
    untracked = []

    for item in plugins_items:
        raw_name = item['name']
        c_name = normalize_name(raw_name)
        url = item['url'].lower().rstrip('/')
        repo_slug = None
        if 'github.com/' in url:
            repo_slug = url.split('github.com/')[-1].split('/tree/')[0]
        elif 'codeberg.org/' in url:
            repo_slug = url.split('codeberg.org/')[-1].split('/src/')[0]
        elif 'gitlab.com/' in url:
            repo_slug = url.split('gitlab.com/')[-1]

        # Check match in registry
        match_reg = None
        if c_name in reg_by_name:
            match_reg = reg_by_name[c_name]
        elif url in reg_by_repo:
            match_reg = reg_by_repo[url]
        else:
            for r_url, p in reg_by_repo.items():
                if repo_slug and repo_slug in r_url:
                    match_reg = p
                    break
                if r_url and (r_url in url or url in r_url):
                    match_reg = p
                    break

        if match_reg:
            in_registry.append((item, match_reg))
            continue

        # Check match in manifest
        match_man = None
        if c_name in manifest_by_name:
            match_man = manifest_by_name[c_name]
        elif repo_slug and repo_slug in manifest_by_repo:
            match_man = manifest_by_repo[repo_slug]

        if match_man:
            in_manifest_not_reg.append((item, match_man))
            continue

        # Check backlog
        match_bl = None
        if c_name in backlog_by_name:
            match_bl = backlog_by_name[c_name]
        elif repo_slug and repo_slug in backlog_by_repo:
            match_bl = backlog_by_repo[repo_slug]

        if match_bl:
            in_backlog_only.append((item, match_bl))
            continue

        untracked.append(item)

    print(f"Awesome-Nu Plugins Total: {len(plugins_items)}")
    print(f"  [+] In Numan Registry (Available for install): {len(in_registry)}")
    print(f"  [~] In numan-plugins CI Manifest but not yet in index: {len(in_manifest_not_reg)}")
    print(f"  [.] In numan-plugins backlog with tracked status: {len(in_backlog_only)}")
    print(f"  [-] Not tracked in numan-plugins / numan-registry: {len(untracked)}")

    print("\n[+] IN REGISTRY (Available to `numan install <plugin>`):")
    for item, reg in sorted(in_registry, key=lambda x: x[1]['id']['name']):
        v_list = [f"{v['version']} (Nu: {v.get('nu_version', '*')})" for v in reg.get('versions', [])]
        targets_count = 0
        if reg.get('versions') and 'artifact' in reg['versions'][-1] and 'targets' in reg['versions'][-1]['artifact']:
            targets_count = len(reg['versions'][-1]['artifact']['targets'])
        print(f"  * {reg['id']['owner']}/{reg['id']['name']} (awesome-nu: '{item['name']}')")
        print(f"      Versions: {', '.join(v_list)} | Latest targets: {targets_count}")

    print("\n[.] IN BACKLOG (Tracked with reasons):")
    bl_by_status = {}
    for item, bl in in_backlog_only:
        st = bl.get('status', 'UNKNOWN')
        bl_by_status.setdefault(st, []).append((item, bl))

    for st, entries in sorted(bl_by_status.items()):
        print(f"\n  Status: {st} ({len(entries)} items)")
        for item, bl in entries:
            note = bl.get('c1_note') or bl.get('note') or bl.get('versions', [{}])[-1].get('note', '')
            print(f"    - {bl.get('repo', item['name'])}: {note}")

    print("\n[-] UNTRACKED PLUGINS (In awesome-nu, not in backlog/registry):")
    for item in untracked:
        print(f"  * {item['name']} ({item['url']}) - {item['desc']}")

    print("\n=================================================================")
    print("3. AWESOME-NU SCRIPTS / MODULES vs NUMAN")
    print("=================================================================")
    scripts_items = sections.get('Scripts', [])
    scripts_in_reg = []
    scripts_not_in_reg = []
    for item in scripts_items:
        raw_name = item['name']
        c_name = normalize_name(raw_name)
        url = item['url'].lower().rstrip('/')

        match = None
        if c_name in reg_by_name:
            match = reg_by_name[c_name]
        else:
            for r_url, p in reg_by_repo.items():
                if r_url in url or url in r_url:
                    match = p
                    break
        if match:
            scripts_in_reg.append((item, match))
        else:
            scripts_not_in_reg.append(item)

    print(f"Awesome-Nu Scripts Total: {len(scripts_items)}")
    print(f"  [+] In Numan Registry: {len(scripts_in_reg)}")
    print(f"  [-] Not in Registry: {len(scripts_not_in_reg)}")
    print("\n[+] In Registry:")
    for item, reg in scripts_in_reg:
        print(f"  * {reg['id']['owner']}/{reg['id']['name']} ({reg.get('type')}) - matched from awesome-nu '{item['name']}'")

    print("\n[-] Sample Not in Registry (Top 10):")
    for item in scripts_not_in_reg[:10]:
        print(f"  * {item['name']} ({item['url']}) - {item['desc']}")

    print("\n=================================================================")
    print("4. AWESOME-NU CUSTOM COMPLETIONS vs NUMAN")
    print("=================================================================")
    completions_items = sections.get('Custom Completions', [])
    for item in completions_items:
        raw_name = item['name']
        c_name = normalize_name(raw_name)
        matched = []
        for p in reg_pkgs:
            if p.get('type') == 'completion':
                p_name = p['id']['name'].lower()
                if c_name in p_name or p_name in c_name:
                    matched.append(f"{p['id']['owner']}/{p['id']['name']}")
        if matched:
            print(f"  * {raw_name}: In Registry as {', '.join(matched)}")
        else:
            print(f"  * {raw_name}: Not individually packaged in registry (or bundled in custom-completions)")

    print("\n=================================================================")
    print("5. NUMAN PACKAGES NOT LISTED IN AWESOME-NU")
    print("=================================================================")
    all_awesome_urls = set()
    for s_items in sections.values():
        for item in s_items:
            all_awesome_urls.add(item['url'].lower().rstrip('/'))
            all_awesome_urls.add(normalize_name(item['name']))

    numan_only = []
    for p in reg_pkgs:
        repo = p.get('repo', '').lower().rstrip('/')
        p_name = p['id']['name'].lower().replace('-', '_')
        matched = False
        if p_name in all_awesome_urls:
            matched = True
        elif repo in all_awesome_urls:
            matched = True
        else:
            for a_u in all_awesome_urls:
                if (repo and repo in a_u) or (repo and a_u in repo):
                    matched = True
                    break
        if not matched:
            numan_only.append(p)

    print(f"Packages in Numan Registry that are NOT in awesome-nu ({len(numan_only)}):")
    for p in sorted(numan_only, key=lambda x: (x.get('type'), x['id']['name'])):
        print(f"  * [{p.get('type')}] {p['id']['owner']}/{p['id']['name']} - {p.get('description', '')[:80]}")

if __name__ == '__main__':
    main()
