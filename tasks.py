#!/usr/bin/env python
"""
Deployment file to facilitate releases of custodian.
"""


import datetime
import glob
import json
import os
import re
import subprocess

import requests
from invoke import task
from monty.os import cd

from custodian import __version__ as CURRENT_VER

NEW_VER = datetime.datetime.today().strftime("%Y.%-m.%-d")


@task
def make_doc(ctx):
    with cd("docs_rst"):
        ctx.run("sphinx-apidoc -d 6 -o . -f ../custodian")
        ctx.run("rm custodian*.tests.rst")
        for file in glob.glob("*.rst"):
            if file.startswith("custodian") and file.endswith("rst"):
                newoutput = []
                suboutput = []
                subpackage = False
                with open(file) as fid:
                    for line in fid:
                        clean = line.strip()
                        if clean == "Subpackages":
                            subpackage = True
                        if not subpackage and not clean.endswith("tests"):
                            newoutput.append(line)
                        else:
                            if not clean.endswith("tests"):
                                suboutput.append(line)
                            if clean.startswith("custodian") and not clean.endswith("tests"):
                                newoutput.extend(suboutput)
                                subpackage = False
                                suboutput = []

                with open(file, "w") as fid:
                    fid.write("".join(newoutput))
        ctx.run("make html")
        # ctx.run("cp _static/* _build/html/_static")

    with cd("docs"):
        ctx.run("cp -r html/* .")
        ctx.run("rm -r html")
        ctx.run("rm -r doctrees")
        ctx.run("rm -r _sources")

        # Avoid the use of jekyll so that _dir works as intended.
        ctx.run("touch .nojekyll")


@task
def update_doc(ctx):
    make_doc(ctx)
    ctx.run("git add .")
    ctx.run('git commit -a -m "Update dev docs"')
    ctx.run("git push")


@task
def release_github(ctx):
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
def test(ctx):
    ctx.run("pytest custodian")


@task
def set_ver(ctx):
    lines = []
    with open("custodian/__init__.py") as file:
        for line in file:
            if "__version__" in line:
                lines.append(f'__version__ = "{NEW_VER}"')
            else:
                lines.append(line.rstrip())
    with open("custodian/__init__.py", "w") as file:
        file.write("\n".join(lines) + "\n")

    lines = []
    with open("setup.py") as file:
        for line in file:
            lines.append(re.sub(r"version=([^,]+),", f'version="{NEW_VER}",', line.rstrip()))
    with open("setup.py", "w") as file:
        file.write("\n".join(lines) + "\n")


@task
def update_changelog(ctx, version=None, sim=False):
    """
    Create a preliminary change log using the git logs.

    :param ctx:
    """
    version = version or datetime.datetime.now().strftime("%Y.%-m.%-d")
    output = subprocess.check_output(["git", "log", "--pretty=format:%s", f"v{CURRENT_VER}..HEAD"])
    lines = []
    misc = []
    for line in output.decode("utf-8").strip().split("\n"):
        m = re.match(r"Merge pull request \#(\d+) from (.*)", line)
        if m:
            pr_number = m.group(1)
            contrib, pr_name = m.group(2).split("/", 1)
            response = requests.get(f"https://api.github.com/repos/materialsproject/custodian/pulls/{pr_number}")
            lines.append(f"* PR #{pr_number} from @{contrib} {pr_name}")
            if "body" in response.json():
                for ll in response.json()["body"].split("\n"):
                    ll = ll.strip()
                    if ll in ["", "## Summary"]:
                        continue
                    if ll.startswith(("## Checklist", "## TODO")):
                        break
                    lines.append(f"    {ll}")
        misc.append(line)
    with open("docs_rst/changelog.rst") as f:
        contents = f.read()
    line = "=========="
    toks = contents.split(line)
    head = f"\n\nv{version}\n" + "-" * (len(version) + 1) + "\n"
    toks.insert(-1, head + "\n".join(lines))
    if not sim:
        with open("docs_rst/changelog.rst", "w") as f:
            f.write(toks[0] + line + "".join(toks[1:]))
        ctx.run("open docs_rst/changelog.rst")
    else:
        print(toks[0] + line + "".join(toks[1:]))
    print("The following commit messages were not included...")
    print("\n".join(misc))


@task
def release(ctx):
    set_ver(ctx)
    update_doc(ctx)
    release_github(ctx)
