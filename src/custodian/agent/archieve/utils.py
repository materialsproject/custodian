
def read_context(directory, output_filename="vasp.out") -> dict:
    """Summarize a stopped VASP run for the LLM without sending whole files.

    Numbers come from pymatgen (OSZICAR, OUTCAR, vasprun.xml, CONTCAR); wording comes from the WARNING/ERROR
    messages in the log, grouped with counts. Each part is read separately, so one unreadable file only hides itself.
    """
    d = Path(directory)
    incar = Incar.from_str(_text(d / "INCAR"))
    log, stderr = _text(d / output_filename), _text(d / "std_err.txt")
    ctx = {
        "known_errors_in_log": sorted(
            k for k, msgs in ERROR_MSGS.items() if any(m in log or m in stderr for m in msgs)
        ),
        "log_messages": _section(lambda: _log_messages(log.splitlines())),
        "incar": dict(incar),
        "scf_and_ionic": _section(lambda: _oszicar_summary(d, incar)),
        "outcar": _section(lambda: _outcar_summary(d)),
        "vasprun": _section(lambda: _vasprun_summary(d)),
        "structure": _section(lambda: _structure_summary(d)),
        "log_tail": log.splitlines()[-15:],
        "prior_corrections": _prior_corrections(d),
    }
    if kpoints := _text(d / "KPOINTS"):
        ctx["kpoints"] = kpoints
    if stderr.strip():
        ctx["std_err_tail"] = stderr.splitlines()[-10:]
    return ctx


def _section(fn):
    try:
        return fn()
    except FileNotFoundError:
        return "missing"
    except Exception as exc:  # one unreadable file must not hide the rest
        return f"unreadable: {type(exc).__name__}: {exc}"[:200]


def _text(path) -> str:
    path = Path(zpath(str(path)))
    if not path.exists():
        return ""
    with zopen(path, mode="rt", errors="replace") as f:
        return f.read()


def _log_messages(lines, cap=12) -> list[dict]:
    """VASP's WARNING/ERROR boxes and lines containing WARNING/ERROR/Error, grouped (numbers ignored) with counts."""
    counts: Counter = Counter()
    texts: dict = {}
    i = 0
    while i < len(lines):
        if _BOX_BORDER.match(lines[i]) and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            j, rows = i + 1, []
            while j < len(lines) and lines[j].startswith("|"):
                rows.append(lines[j].strip().strip("|").strip())
                j += 1
            art = [r for r in rows if r and _BANNER_ART.match(r)]
            if art:  # ponytail: only WARNING boxes seen in real runs so far; ERROR art guessed from its letters
                kind = "WARNING box" if any("W    W" in r for r in art) else "ERROR box" if "EEEE" in art[0] else "box"
                text = " ".join(r for r in rows if r and not _BANNER_ART.match(r))
                key = (kind, _without_numbers(text))
                counts[key] += 1
                texts[key] = text
                i = j + 1
                continue
        if any(word in lines[i] for word in ("WARNING", "ERROR", "Error")):
            key = ("line", _without_numbers(lines[i]))
            counts[key] += 1
            texts[key] = lines[i].strip()
        i += 1
    return [{"kind": k[0], "count": n, "text": texts[k][:300]} for k, n in counts.most_common(cap)]


def _without_numbers(s) -> str:
    """Group messages that differ only in numbers (step counts, energies, residuals)."""
    return re.sub(r"\s+", " ", re.sub(r"[-+]?\d+(\.\d+)?([EeDd][-+]?\d+)?", "#", s)).strip()


def _oszicar_summary(d, incar) -> dict:
    osz = Oszicar(zpath(str(d / "OSZICAR")))
    nelm = incar.get("NELM", 60)
    n = [len(e) for e in osz.electronic_steps]
    hit = [x >= nelm for x in n]
    e0 = [s["E0"] for s in osz.ionic_steps]
    return {
        "ionic_steps": len(n),
        "NSW": incar.get("NSW", 0),
        "NELM": nelm,
        "n_steps_hitting_NELM": sum(hit),
        "longest_NELM_streak": max((len(list(g)) for k, g in groupby(hit) if k), default=0),
        "steps_hitting_NELM": [i + 1 for i, h in enumerate(hit) if h][-20:],
        "electronic_steps_last5": n[-5:],
        "E0_last5": [round(float(x), 5) for x in e0[-5:]],
        "magnetization_last": osz.ionic_steps[-1].get("mag") if osz.ionic_steps else None,
    }


def _outcar_summary(d) -> dict:
    """ponytail: Outcar parses the whole file (~1 s per 15 MB); long MD OUTCARs may need read_pattern only."""
    out = load_outcar(zpath(str(d / "OUTCAR")))
    return {
        "drift_last": [round(float(x), 4) for x in out.drift[-1]] if out.drift else None,
        "nelect": out.nelect,
        "efermi": out.efermi,
        "stopped_by_stopcar": out.is_stopped,
    }


def _vasprun_summary(d) -> dict:
    path = zpath(str(d / "vasprun.xml"))
    with zopen(path, mode="rb") as f:
        if path.endswith(".xml"):
            f.seek(max(0, os.path.getsize(path) - 512))
        complete = b"</modeling>" in f.read()[-512:]
    vr = load_vasprun(path, parse_dos=False, parse_eigen=complete, parse_potcar_file=False, exception_on_bad_xml=False)
    forces = [np.linalg.norm(s["forces"], axis=1).max() for s in vr.ionic_steps[-5:] if s.get("forces") is not None]
    out = {
        "complete": complete,
        "ionic_steps_written": len(vr.ionic_steps),
        "max_force_last5": [round(float(x), 3) for x in forces],
    }
    if complete:  # a killed run has no eigenvalues, and pymatgen reads "stopped before NSW" as ionic convergence
        out["converged_electronic"] = vr.converged_electronic
        out["converged_ionic"] = vr.converged_ionic
        out["band_gap"] = round(float(vr.eigenvalue_band_properties[0]), 4)
    return out


def _structure_summary(d) -> dict:
    """ponytail: full distance matrix, fine to a few thousand sites."""
    contcar = Path(zpath(str(d / "CONTCAR")))
    path = contcar if contcar.exists() and contcar.stat().st_size else Path(zpath(str(d / "POSCAR")))
    s = Structure.from_file(path)
    out = {
        "source": path.name,
        "formula": s.composition.reduced_formula,
        "nsites": len(s),
        "volume": round(s.volume, 2),
    }
    if len(s) > 1:
        dm = s.distance_matrix
        np.fill_diagonal(dm, np.inf)
        i, j = np.unravel_index(np.argmin(dm), dm.shape)
        out["min_distance"] = round(float(dm[i, j]), 3)
        out["min_distance_pair"] = [s[int(i)].species_string, s[int(j)].species_string]
    return out


def _prior_corrections(d) -> list[dict]:
    """Corrections already applied in this job (Custodian rewrites custodian.json after every check)."""
    try:
        corrections = json.loads(_text(d / "custodian.json"))[-1]["corrections"]
    except (OSError, ValueError, LookupError):
        corrections = []
    return [{"errors": c.get("errors"), "actions": c.get("actions")} for c in corrections]


def validate(actions, directory):
    """Return a reason string if actions are unsafe to apply, else None. This is the trust boundary."""
    if not isinstance(actions, list) or not actions:
        return "no actions"
    modder = None
    for a in actions:
        if a == _CONTCAR_COPY:
            continue
        ok = (
            isinstance(a, dict)
            and set(a) == {"dict", "action"}
            and a["dict"] in ("INCAR", "KPOINTS")
            and isinstance(a["action"], dict)
            and a["action"]
            and set(a["action"]) <= {"_set", "_unset"}
            and all(isinstance(v, dict) for v in a["action"].values())
        )
        if not ok:
            return f"disallowed action: {a}"
        if a["dict"] == "INCAR" and "_set" in a["action"]:
            with warnings.catch_warnings():
                warnings.simplefilter("error", BadIncarWarning)
                try:
                    Incar(a["action"]["_set"]).check_params()
                except BadIncarWarning as w:
                    return f"bad INCAR value: {w}"
        modder = modder or VaspModder(directory=directory)
        try:  # in-memory only: modify_object returns a new object, nothing is written
            modder.modify_object(a["action"], modder.vi[a["dict"]])
        except Exception as exc:
            return f"action does not apply: {a} ({exc})"
    return None