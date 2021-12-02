"""
Deployment file to facilitate releases of custodian.
"""


import datetime
import glob
import json
import os
import re

import requests
from invoke import task
from monty.os import cd

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
    with open("custodian/__init__.py", "wt") as f:
        f.write("\n".join(lines) + "\n")

    lines = []
    with open("setup.py") as f:
        for l in f:
            lines.append(re.sub(r"version=([^,]+),", f'version="{NEW_VER}",', l.rstrip()))
    with open("setup.py", "wt") as f:
        f.write("\n".join(lines) + "\n")


@task
def release(ctx):
    set_ver(ctx)
    update_doc(ctx)
    release_github(ctx)
