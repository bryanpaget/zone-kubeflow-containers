import re
import os
import requests
from git import Repo

# ----------------------------
# Configuration
# ----------------------------

DOCKERFILE_PATH = "images/mid/Dockerfile"
REPO_DIR = "."  # Root of your git repository
REPO_OWNER = "bryanpaget"
REPO_NAME = "zone-kubeflow-containers"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GIT_USERNAME = "Brybot"
GIT_EMAIL = "bryan.paget@statcan.gc.ca"

# ----------------------------
# Utility Functions
# ----------------------------

def extract_extensions_and_vsix(path):
    """
    Parse the Dockerfile to extract VSCode extensions and GitHub-hosted VSIX files.

    Args:
        path (str): Path to the Dockerfile.

    Returns:
        tuple:
            - extensions (list): Marketplace extensions with 'id' and 'version'.
            - vsix_files (list): Standalone .vsix files mentioned.
            - github_vsix (list): GitHub-hosted .vsix with repo, version, and file.
    """
    extensions, vsix_files, github_vsix = [], [], []

    with open(path, "r") as f:
        for line in f:
            # Match regular extensions like `ms-python.python@2022.10.0`
            m = re.search(r"code-server\s+--install-extension\s+([^\s@\\]+)(?:@([^\s\\]+))?", line)
            if m:
                ext, version = m.group(1), m.group(2)
                if ext.endswith(".vsix"):
                    vsix_files.append(ext)
                else:
                    extensions.append({"id": ext, "version": version})

            # Match .vsix downloads from GitHub
            wget = re.search(r"wget.*github\.com/([^/]+/[^/]+)/releases/download/v?([0-9.]+)/([^\s]+\.vsix)", line)
            if wget:
                github_vsix.append({
                    "repo": wget.group(1),
                    "version": wget.group(2),
                    "file": wget.group(3),
                })

    return extensions, vsix_files, github_vsix


def get_latest_openvsx_version(ext_id):
    """
    Query Open VSX registry for the latest version of an extension.

    Args:
        ext_id (str): Extension ID in the form 'namespace.name'.

    Returns:
        str or None: Latest version string or None on failure.
    """
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
    """
    Get the latest release tag from a GitHub repository.

    Args:
        repo (str): GitHub repository in the format 'owner/name'.

    Returns:
        str or None: Latest version tag or None on failure.
    """
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
    Replace an extension version in the Dockerfile in place.

    Args:
        ext_id (str): Extension ID.
        old_version (str): Current version in file.
        new_version (str): New version to update to.

    Returns:
        bool: True if replacement occurred.
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
        print(f"✅ Updated {ext_id}: {old_version} → {new_version}")
    return updated


def create_individual_prs(repo, outdated_extensions):
    """
    Create one branch and pull request per outdated extension.

    Args:
        repo (git.Repo): GitPython repository object.
        outdated_extensions (list): Extensions to update, each with id, old_version, new_version.
    """
    origin = repo.remotes.origin

    # Set Git identity
    repo.git.config("user.name", GIT_USERNAME)
    repo.git.config("user.email", GIT_EMAIL)

    base = repo.heads.master
    origin.pull(base)

    for ext in outdated_extensions:
        short_id = ext["id"].replace(".", "-").replace("/", "-").replace("@", "-").replace(".vsix", "")
        branch_name = f"update/{short_id}-{ext['new_version']}"

        # Start from master
        repo.head.reference = base
        repo.head.reset(index=True, working_tree=True)

        # Create and switch to a new branch
        branch = repo.create_head(branch_name)
        branch.checkout()

        # Update Dockerfile
        if not replace_in_dockerfile(ext["id"], ext["old_version"], ext["new_version"]):
            continue

        # Stage and commit change
        repo.index.add([DOCKERFILE_PATH])
        commit_msg = f"Update {ext['id']} to {ext['new_version']}"
        repo.index.commit(commit_msg)

        # Push branch
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
            print(f"🔀 PR created: {resp.json()['html_url']}")
        elif resp.status_code == 422 and "pull request already exists" in resp.text:
            print(f"⚠️  PR already exists for {branch_name}")
        else:
            print(f"❌ Failed to create PR: {resp.status_code} {resp.text}")


# ----------------------------
# Main Entry Point
# ----------------------------

if __name__ == "__main__":
    extensions, _, github_vsix = extract_extensions_and_vsix(DOCKERFILE_PATH)
    outdated = []

    print("🔍 Checking OpenVSX extensions:")
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

    print("\n🔍 Checking GitHub-hosted .vsix extensions:")
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

    if outdated:
        print(f"\n🚀 Creating PRs for {len(outdated)} updates...\n")
        repo = Repo(REPO_DIR)
        create_individual_prs(repo, outdated)
    else:
        print("\n✅ All extensions are up to date!")
