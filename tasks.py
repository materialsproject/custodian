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
        for f in glob.glob("*.rst"):
            if f.startswith("custodian") and f.endswith("rst"):
                newoutput = []
                suboutput = []
                subpackage = False
                with open(f) as fid:
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

                with open(f, "w") as fid:
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
    with open("custodian/__init__.py") as f:
        for l in f:
            if "__version__" in l:
                lines.append(f'__version__ = "{NEW_VER}"')
            else:
                lines.append(l.rstrip())
    with open("custodian/__init__.py", "w") as f:
        f.write("\n".join(lines) + "\n")

    lines = []
    with open("setup.py") as f:
        for l in f:
            lines.append(re.sub(r"version=([^,]+),", f'version="{NEW_VER}",', l.rstrip()))
    with open("setup.py", "w") as f:
        f.write("\n".join(lines) + "\n")


@task
def update_changelog(ctx, version=datetime.datetime.now().strftime("%Y.%-m.%-d"), sim=False):
    """
    Create a preliminary change log using the git logs.

    :param ctx:
    """
    output = subprocess.check_output(["git", "log", "--pretty=format:%s", f"v{CURRENT_VER}..HEAD"])
    lines = []
    misc = []
    for l in output.decode("utf-8").strip().split("\n"):
        m = re.match(r"Merge pull request \#(\d+) from (.*)", l)
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
                    elif ll.startswith("## Checklist") or ll.startswith("## TODO"):
                        break
                    lines.append(f"    {ll}")
        misc.append(l)
    with open("changelog.rst") as f:
        contents = f.read()
    l = "=========="
    toks = contents.split(l)
    head = f"\n\nv{version}\n" + "-" * (len(version) + 1) + "\n"
    toks.insert(-1, head + "\n".join(lines))
    if not sim:
        with open("docs_rst/changelog.rst", "w") as f:
            f.write(toks[0] + l + "".join(toks[1:]))
        ctx.run("open docs_rst/changelog.rst")
    else:
        print(toks[0] + l + "".join(toks[1:]))
    print("The following commit messages were not included...")
    print("\n".join(misc))


@task
def release(ctx):
    set_ver(ctx)
    update_doc(ctx)
    release_github(ctx)
