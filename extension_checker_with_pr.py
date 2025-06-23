import re
import os
import requests
from git import Repo

# Configuration
DOCKERFILE_PATH = "images/mid/Dockerfile"
REPO_DIR = "."  # Root of your git repo
REPO_OWNER = "bryanpaget"
REPO_NAME = "zone-kubeflow-containers"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GIT_USERNAME = "Brybot"
GIT_EMAIL = "bryan.paget@statcan.gc.ca"

# ----------- Helpers -----------

def extract_extensions_and_vsix(path):
    extensions, vsix_files, github_vsix = [], [], []

    with open(path, "r") as f:
        for line in f:
            m = re.search(r"code-server\s+--install-extension\s+([^\s@\\]+)(?:@([^\s\\]+))?", line)
            if m:
                ext, version = m.group(1), m.group(2)
                if ext.endswith(".vsix"):
                    vsix_files.append(ext)
                else:
                    extensions.append({"id": ext, "version": version})

            wget = re.search(r"wget.*github\.com/([^/]+/[^/]+)/releases/download/v?([0-9.]+)/([^\s]+\.vsix)", line)
            if wget:
                github_vsix.append({
                    "repo": wget.group(1),
                    "version": wget.group(2),
                    "file": wget.group(3),
                })

    return extensions, vsix_files, github_vsix

def get_latest_openvsx_version(ext_id):
    try:
        namespace, name = ext_id.split('.', 1)
        url = f"https://open-vsx.org/api/{namespace}/{name}/latest"
        resp = requests.get(url)
        if resp.status_code == 200:
            return resp.json().get("version", "").strip()
    except Exception as e:
        print(f"Error fetching {ext_id}: {e}")
    return None

def get_latest_github_release(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get('tag_name', '').lstrip('v').strip()
    return None

def replace_in_dockerfile(ext_id, old_version, new_version):
    """
    In-place replace of extension version using simple string substitution.
    """
    with open(DOCKERFILE_PATH, "r") as f:
        lines = f.readlines()

    updated = False
    with open(DOCKERFILE_PATH, "w") as f:
        for line in lines:
            target = f"code-server --install-extension {ext_id}@{old_version}"
            replacement = f"code-server --install-extension {ext_id}@{new_version}"
            if target in line:
                line = line.replace(target, replacement)
                updated = True
            f.write(line)

    if updated:
        print(f"Updated {ext_id} from {old_version} → {new_version}")
    return updated

def create_individual_prs(repo, outdated_extensions):
    """
    For each update, create a new branch, modify Dockerfile, commit, push, and open PR.
    """
    origin = repo.remotes.origin
    repo.git.config("user.name", GIT_USERNAME)
    repo.git.config("user.email", GIT_EMAIL)

    base = repo.heads.master
    origin.pull(base)

    for ext in outdated_extensions:
        short_id = ext["id"].replace(".", "-").replace("/", "-").replace("@", "-").replace(".vsix", "")
        branch_name = f"update/{short_id}-{ext['new_version']}"

        # Reset to master
        repo.head.reference = base
        repo.head.reset(index=True, working_tree=True)

        # Create branch
        branch = repo.create_head(branch_name)
        branch.checkout()

        # Apply update
        if not replace_in_dockerfile(ext["id"], ext["old_version"], ext["new_version"]):
            continue

        # Commit + push
        repo.index.add([DOCKERFILE_PATH])
        commit_msg = f"Update {ext['id']} to {ext['new_version']}"
        repo.index.commit(commit_msg)
        origin.push(branch)

        # Create PR via GitHub API
        pr_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        payload = {
            "title": f"Automated: {commit_msg}",
            "head": branch_name,
            "base": "master",
            "body": f"This PR updates `{ext['id']}` from `{ext['old_version']}` to `{ext['new_version']}`."
        }

        resp = requests.post(pr_url, headers=headers, json=payload)
        if resp.status_code == 201:
            print(f"✅ PR created: {resp.json()['html_url']}")
        elif resp.status_code == 422 and "pull request already exists" in resp.text:
            print(f"⚠️  PR already exists for {branch_name}")
        else:
            print(f"❌ Failed to create PR: {resp.status_code} {resp.text}")

# ----------- Main -----------

if __name__ == "__main__":
    extensions, _, github_vsix = extract_extensions_and_vsix(DOCKERFILE_PATH)
    outdated = []

    print("Checking Marketplace Extensions:")
    for ext in extensions:
        latest = get_latest_openvsx_version(ext["id"])
        if latest and ext["version"] and latest != ext["version"]:
            print(f"  - {ext['id']}@{ext['version']} → {latest}  [UPDATE]")
            outdated.append({
                "id": ext["id"],
                "old_version": ext["version"],
                "new_version": latest
            })
        else:
            print(f"  - {ext['id']}@{ext['version']} (latest: {latest or 'unknown'})")

    print("\nChecking GitHub-hosted .vsix extensions:")
    for gvsix in github_vsix:
        latest = get_latest_github_release(gvsix["repo"])
        if latest and gvsix["version"] and latest != gvsix["version"]:
            print(f"  - {gvsix['repo']} {gvsix['file']} (current: {gvsix['version']} → {latest})  [UPDATE]")
            outdated.append({
                "id": gvsix["file"],
                "old_version": gvsix["version"],
                "new_version": latest
            })
        else:
            print(f"  - {gvsix['repo']} {gvsix['file']} (current: {gvsix['version']}, latest: {latest or 'unknown'})")

    # Open repo and run updates
    repo = Repo(REPO_DIR)
    create_individual_prs(repo, outdated)
