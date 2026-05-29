"""
GitHub Setup Script — Push repo + configure secrets.

This automates the GitHub setup so you don't have to copy-paste secrets.
Requires: gh CLI (https://cli.github.com)

Usage:
    python setup_github.py             # Creates repo, pushes code
    python setup_github.py --secrets   # Also configure secrets (need gh auth)
    python setup_github.py --dry-run   # Just show what would happen
"""
import subprocess
import sys
import os

REPO_NAME = "web-agency-leads"
REPO_DESCRIPTION = "Lead Generation Pipeline — Scrape Instagram, Supabase DB, Cold Outreach"


def run(cmd, check=True):
    """Run a shell command and return output."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
        if r.returncode != 0 and check:
            print(f"  WARN: {r.stderr.strip()[:200]}")
        return r.stdout.strip()
    except Exception as e:
        print(f"  ERROR: {e}")
        return ""


def check_gh_installed():
    r = subprocess.run(["where", "gh"], capture_output=True, text=True, timeout=10, shell=True)
    return r.returncode == 0


def main():
    dry_run = "--dry-run" in sys.argv
    do_secrets = "--secrets" in sys.argv

    print("=" * 60)
    print(f"  GITHUB SETUP — {REPO_NAME}")
    print("=" * 60)

    if not check_gh_installed():
        print("\n[!] GitHub CLI (gh) not found.")
        print("    Download from: https://cli.github.com/")
        print("\n    Alternative: Create repo manually, then run:")
        print(f"    git remote add origin https://github.com/YOUR_USERNAME/{REPO_NAME}.git")
        print("    git push -u origin master")
        print("\n    Then add secrets at:")
        print(f"    https://github.com/YOUR_USERNAME/{REPO_NAME}/settings/secrets/actions")
        return

    if dry_run:
        print("\n[DRY RUN] Would execute:")
        print(f"  gh repo create {REPO_NAME} --public --source=. --remote=origin --push")
        if do_secrets:
            print("  Then add 6 secrets (SERPAPI_KEY, SUPABASE_*)")
        return

    # Step 1: Create repo and push
    repo_url = f"https://github.com/YOUR_USERNAME/{REPO_NAME}"
    print(f"\n[1/4] Creating GitHub repo: {REPO_NAME}...")
    r = run(f"gh repo create {REPO_NAME} --public --source=. --remote=origin --push")
    if "already exists" in r:
        print("  Repo already exists. Pushing current code...")
        run("git push -u origin master", check=False)

    # Step 2: Verify remote
    print(f"\n[2/4] Verifying remote...")
    remote = run("git remote -v")
    if "origin" in remote:
        repo_url = remote.split("\n")[0].split("\t")[1].split(" ")[0]
        print(f"  Remote: {repo_url}")

    # Step 3: Configure secrets
    if do_secrets:
        print(f"\n[3/4] Configuring secrets...")
        secrets = {
            "SERPAPI_KEY": "SERPAPI_KEY",
            "SUPABASE_DB": "SUPABASE_DB",
            "SUPABASE_USER": "SUPABASE_USER",
            "SUPABASE_PASSWORD": "SUPABASE_PASSWORD",
            "SUPABASE_HOST": "SUPABASE_HOST",
            "SUPABASE_PORT": "SUPABASE_PORT",
        }
        for name, env_var in secrets.items():
            value = os.getenv(env_var, "")
            if value:
                run(f'gh secret set {name} --body "{value}"')
                print(f"  Set: {name}")
            else:
                print(f"  SKIP: {name} (not in current env)")
                print(f"    Set later: gh secret set {name}")
    else:
        print(f"\n[3/4] Secrets NOT configured (use --secrets flag)")
        print(f"    Or set manually at:")
        print(f"    {REPO_URL.replace('YOUR_USERNAME', '<your-username>')}/settings/secrets/actions")

    # Step 4: Verify Actions
    print(f"\n[4/4] Next steps:")
    print(f"  1. Watch pipeline run:")
    print(f"     {repo_url}/actions")
    print(f"  2. Check leads export:")
    print(f"     Actions → Lead Pipeline → latest run → Artifacts")
    print(f"  3. The pipeline auto-runs every 6 hours 24/7")

    print(f"\n{'='*60}")
    print(f"  SETUP COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
