#!/usr/bin/env python3
"""Fetch live profile data from the GitHub API into assets/data.json.

Run by .github/workflows/profile-cards.yml; assets/cards.py then renders the
SVGs from that file. Needs GH_TOKEN (or GITHUB_TOKEN) in the environment.

Two deliberate choices about honesty:

* Automated commits are excluded. The waka-readme job commits to the profile
  repo every night under the owner's authorship, which inflated the headline
  by two orders of magnitude - 345 of 353 public commits in the year to
  2026-09-18 were the bot. `commits` counts human commits; `contributions`
  reports GitHub's own calendar total alongside it, labelled as such.
* Private repositories are counted in totals but never named, so nothing
  leaks into a public README.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone

LOGIN = os.environ.get("PROFILE_LOGIN", "Vivek-Murali")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
# Commits whose committer is one of these are automation, not work.
BOTS = {"githubactionbot", "github-actions[bot]", "web-flow", "actions-user", "dependabot[bot]"}
WINDOW_DAYS = 365


def call(url, method="GET", body=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "%s-profile-cards" % LOGIN)
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data, timeout=60) as r:
        return json.loads(r.read().decode())


def paged(path, cap=10):
    out, page = [], 1
    while page <= cap:
        chunk = call("%s%s%sper_page=100&page=%d" % (API, path, "&" if "?" in path else "?", page))
        if not chunk:
            break
        out += chunk
        if len(chunk) < 100:
            break
        page += 1
    return out


def graphql(query, variables):
    return call(API + "/graphql", "POST", {"query": query, "variables": variables})


# ------------------------------------------------------------------ pieces --
def fetch_user():
    u = call("%s/users/%s" % (API, LOGIN))
    created = datetime.strptime(u["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    return {"login": u["login"], "followers": u["followers"],
            "since": created.year, "years": date.today().year - created.year}


def fetch_repos():
    """Public repos drive everything displayed; private ones only add to counts."""
    repos = paged("/users/%s/repos?type=owner&sort=pushed" % LOGIN)
    pub = [r for r in repos if not r["private"]]
    own = [r for r in pub if not r["fork"]]
    langs = Counter(r["language"] for r in own if r["language"])
    return {
        "repos": repos,
        "totals": {
            "public_repos": len(pub),
            "original": len(own),
            "stars": sum(r["stargazers_count"] for r in own),
            "forks": sum(r["forks_count"] for r in own),
        },
        "repo_langs": langs.most_common(6),
        # live numbers for whichever repos the cards choose to feature
        "repo_index": {r["name"]: {"stars": r["stargazers_count"], "forks": r["forks_count"],
                                   "lang": r["language"], "pushed": r["pushed_at"][:10]}
                       for r in own},
    }


def fetch_contributions():
    """GitHub's own calendar total, plus streak and active-day counts."""
    q = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    try:
        cal = (graphql(q, {"login": LOGIN})["data"]["user"]["contributionsCollection"]
               ["contributionCalendar"])
    except (KeyError, TypeError, urllib.error.HTTPError) as e:
        print("contribution calendar unavailable (%s); skipping" % e, file=sys.stderr)
        return {}
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    active = sum(1 for d in days if d["contributionCount"] > 0)
    streak = best = 0
    for d in days:
        streak = streak + 1 if d["contributionCount"] else 0
        best = max(best, streak)
    # current streak: walk back from the most recent day
    cur = 0
    for d in reversed(days):
        if d["contributionCount"]:
            cur += 1
        elif cur or d["date"] != days[-1]["date"]:
            break
    return {"calendar_total": cal["totalContributions"], "active_days": active,
            "tracked_days": len(days), "streak": cur, "longest": best}


def fetch_commits(repos, since):
    """Human commits per public repo inside the window, newest repos first."""
    per, total = [], 0
    for r in repos:
        if r["private"] or r["fork"]:
            continue
        if r.get("pushed_at", "") < since:
            continue
        try:
            commits = paged("/repos/%s/commits?author=%s&since=%s"
                            % (r["full_name"], LOGIN, since), cap=4)
        except urllib.error.HTTPError as e:
            if e.code in (404, 409):      # empty repo
                continue
            raise
        human = [c for c in commits
                 if ((c.get("committer") or {}).get("login") or "").lower() not in BOTS
                 and (((c.get("commit") or {}).get("committer") or {}).get("name") or "").lower()
                 not in BOTS]
        if human:
            per.append({"name": r["name"], "commits": len(human),
                        "lang": r["language"], "pushed": r["pushed_at"][:10]})
            total += len(human)
    per.sort(key=lambda p: (-p["commits"], p["name"]))
    return {"commits": total, "projects": per[:6]}


def parse_waka():
    """Reuse the block waka-readme already maintains - no WakaTime key needed."""
    readme = os.path.join(ROOT, "README.md")
    if not os.path.exists(readme):
        return {}
    block = re.search(r"<!--START_SECTION:waka-->(.*?)<!--END_SECTION:waka-->",
                      open(readme).read(), re.S)
    if not block:
        return {}
    body = block.group(1)
    rng = re.search(r"From:\s*(.+?)\s*-\s*To:\s*(.+)", body)
    total = re.search(r"Total Time:\s*(.+)", body)
    langs = re.findall(r"^(\S[^\d]*?)\s{2,}.*?([\d.]+)\s*%$", body, re.M)
    return {"from": rng.group(1).strip() if rng else "",
            "to": rng.group(2).strip() if rng else "",
            "total": total.group(1).strip() if total else "",
            "langs": [[n.strip(), float(p)] for n, p in langs][:8]}


def main():
    since = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo_data = fetch_repos()
    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "window_days": WINDOW_DAYS,
        "user": fetch_user(),
        "totals": repo_data["totals"],
        "repo_index": repo_data["repo_index"],
        "repo_langs": repo_data["repo_langs"],
        "contributions": fetch_contributions(),
        "waka": parse_waka(),
    }
    out.update(fetch_commits(repo_data["repos"], since))
    path = os.path.join(ROOT, "assets", "data.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write("\n")
    print("wrote %s" % path)
    print(json.dumps({k: v for k, v in out.items() if k != "projects"}, indent=2)[:900])


if __name__ == "__main__":
    main()
