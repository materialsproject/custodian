"""Deployment file to facilitate releases of custodian."""

import datetime
import json
import os
import re
import subprocess
from glob import glob

import requests
from invoke import task
from monty.os import cd

from custodian import __version__ as CURRENT_VER

NEW_VER = datetime.datetime.now().strftime("%Y.%-m.%-d")


@task
def make_doc(ctx) -> None:
    with cd("docs"):
        ctx.run("touch index.rst")
        ctx.run("rm custodian.*.rst", warn=True)
        ctx.run("sphinx-apidoc --separate -P -M -d 7 -o . -f ../src/custodian")
        ctx.run("sphinx-build -M markdown . .")
        ctx.run("rm *.rst", warn=True)
        ctx.run("cp markdown/custodian*.md .")
        ctx.run("rm custodian*tests*.md", warn=True)
        for fn in glob("custodian*.md"):
            with open(fn) as file:
                lines = [line.rstrip() for line in file if "Submodules" not in line]
            if fn == "custodian.md":
                preamble = ["---", "layout: default", "title: API Documentation", "nav_order: 6", "---", ""]
            else:
                preamble = ["---", "layout: default", "title: " + fn, "nav_exclude: true", "---", ""]
            with open(fn, "w") as file:
                file.write("\n".join(preamble + lines))
        ctx.run("rm -r markdown doctrees", warn=True)


@task
def update_doc(ctx) -> None:
    make_doc(ctx)
    ctx.run("git add .", warn=True)
    ctx.run('git commit -a -m "Update dev docs"', warn=True)
    ctx.run("git push", warn=True)


@task
def release_github(ctx) -> None:
    payload = {
        "tag_name": "v" + NEW_VER,
        "target_commitish": "master",
        "name": "v" + NEW_VER,
        "body": "See changes at https://materialsproject.github.io/custodian",
        "draft": False,
        "prerelease": False,
    }
    response = requests.post(
        "https://api.github.com/repos/materialsproject/custodian/releases",
        data=json.dumps(payload),
        headers={"Authorization": "token " + os.environ["GITHUB_RELEASES_TOKEN"]},
    )
    print(response.text)


@task
def test(ctx) -> None:
    ctx.run("pytest custodian")


@task
def set_ver(ctx) -> None:
    with open("pyproject.toml") as file:
        lines = [re.sub(r"^version = \"([^,]+)\"", f'version = "{NEW_VER}"', line.rstrip()) for line in file]

    with open("pyproject.toml", "w") as file:
        file.write("\n".join(lines) + "\n")

    ctx.run("ruff check --fix custodian")
    ctx.run("ruff format pyproject.toml")


@task
def update_changelog(ctx, version=None, sim=False) -> None:
    """
    Create a preliminary change log using the git logs.

    :param ctx:
    """
    version = version or datetime.datetime.now().strftime("%Y.%-m.%-d")
    output = subprocess.check_output(["git", "log", "--pretty=format:%s", f"v{CURRENT_VER}..HEAD"])
    lines = []
    misc = []
    for line in output.decode("utf-8").strip().split("\n"):
        m = re.search(r"\(\#(\d+)\)", line)
        if m:
            pr_number = m.group(1)
            pr_name = m.group().rsplit(r"\(", 1)[0]
            response = requests.get(f"https://api.github.com/repos/materialsproject/custodian/pulls/{pr_number}")
            try:
                dct = response.json()
                contrib = dct["user"]["login"]
                lines.append(f"* PR #{pr_number} from @{contrib} {pr_name}")
                if "body" in response.json():
                    for ll in response.json()["body"].split("\n"):
                        ll = ll.strip()
                        if ll in {"", "## Summary"}:
                            continue
                        if ll.startswith(("## Checklist", "## TODO")):
                            break
                        lines.append(f"    {ll}")
            except:
                pass
        else:
            misc.append("- " + line)
    with open("docs/changelog.md") as file:
        contents = file.read()
    head = "# Change Log"
    i = contents.find(head)
    i += len(head)

    contents = contents[0:i] + f"\n\n## {NEW_VER}\n" + "\n".join(lines) + contents[i:]
    if not sim:
        with open("docs/changelog.md", "w") as file:
            file.write(contents)
        ctx.run("open docs/changelog.md")
    else:
        print(contents)
    print("The following commit messages were not included...")
    print("\n".join(misc))


@task
def release(ctx) -> None:
    set_ver(ctx)
    update_doc(ctx)
    release_github(ctx)
