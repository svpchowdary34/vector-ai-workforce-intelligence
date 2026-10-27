# ==============================================================================
# VECTOR AI — Workforce Capability & Skills Intelligence | ONE Google Colab cell
# The right skills. At the right time.
# ==============================================================================
import subprocess, sys, os, re, json, zipfile, html, math, warnings
warnings.filterwarnings("ignore")

def _deps():
    try:
        from importlib.metadata import version
        if int(version("gradio").split(".")[0]) not in (4, 5): raise RuntimeError("gradio")
        for p in ("plotly", "scipy", "requests", "pandas", "numpy"): version(p)
    except Exception:
        print("Installing dependencies (about a minute)...")
        try: subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "gradio>=4.44,<6", "plotly", "scipy", "requests", "pandas", "numpy"]); print("Dependencies installed.")
        except Exception as e: print("Install warning:", type(e).__name__, "- check internet access and re-run.")
_deps()
try:
    import numpy as np, pandas as pd, plotly.graph_objects as go, gradio as gr, requests
    from scipy import sparse
    from scipy.optimize import linprog
except Exception as e:
    raise SystemExit("Libraries could not be imported (" + type(e).__name__ + "). Restart the runtime and re-run this cell.")

C = dict(bg="#151C27", sf="#263442", mi="#7BE0C3", la="#D3B5FF", am="#F1BE78", tx="#F2F5F7", mu="#A7B5C5", co="#F18C91")
G = {}; TESTS = []; ASSUME = {}; _DEMO = {}
BLANK = ["", "nan", "none", "n/a", "na", "-", "null", "nat"]
esc = lambda x: html.escape(str(x))
norm = lambda s: re.sub(r"\W+", "_", str(s).strip().lower()).strip("_")
sk_key = lambda s: re.sub(r"[^a-z0-9+#&]+", " ", str(s).lower()).strip()
nul = lambda v: v is None or (not isinstance(v, str) and bool(pd.isna(v)))
nf = lambda v: "—" if nul(v) else format(v, ",.0f")
fx = lambda v, d=1: "—" if nul(v) else format(v, "." + str(d) + "f")
pc0 = lambda v: "—" if nul(v) else format(v, ".0%")
money = lambda v: "—" if nul(v) else ("-$" if v < 0 else "$") + format(abs(v), ",.0f")
dts = lambda v: "—" if nul(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
STC = {"Ready": C["mi"], "At Risk": C["am"], "Critical": C["co"], "No demand": C["mu"]}
FLAGC = {"Skill shortage": C["co"], "Proficiency shortage": C["am"], "Headcount shortage": C["co"], "Timing shortage": C["la"], "Allocation shortage": C["am"], "Concentration risk": C["la"], "Capacity contention": C["mu"]}
def pill(s, col=None): col = col or STC.get(s, C["mu"]); return "<span class='pill' style='color:%s;border-color:%s'>%s</span>" % (col, col, esc(s))
flags_html = lambda l: " ".join(pill(f, FLAGC.get(f)) for f in l) if len(l) else "—"
def note(t, k="info"):
    col = {"info": C["mu"], "ok": C["mi"], "warn": C["am"], "err": C["co"], "ai": C["la"]}[k]
    return "<div class='note' style='border-left:3px solid %s'>%s</div>" % (col, t)
def card(lab, val, desc, col=C["mi"]): return "<div class='kc'><div class='kl'>%s</div><div class='kv' style='color:%s'>%s</div><div class='kd'>%s</div></div>" % (lab, col, val, desc)
H = lambda t: "<div class='sec'>%s</div>" % t
def tbl(d, cols, fmt=None):
    fmt = fmt or {}; h = "<div class='tw'><table><tr>" + "".join("<th>%s</th>" % n for _, n in cols) + "</tr>"
    for _, r in d.iterrows(): h += "<tr>" + "".join("<td>%s</td>" % (fmt[k](r[k]) if k in fmt else ("—" if nul(r[k]) else esc(r[k]))) for k, _n in cols) + "</tr>"
    return h + "</table></div>"
def sty(f, h=380, t=""):
    f.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=C["tx"]), height=h, title=dict(text=t, x=.02), margin=dict(l=60, r=20, t=55, b=50), legend=dict(orientation="h", y=-.25), colorway=[C["mi"], C["la"], C["am"], C["co"]])
    return f
def empty(msg):
    f = go.Figure(); f.add_annotation(text=msg, showarrow=False, font=dict(color=C["mu"], size=14)); f.update_xaxes(visible=False); f.update_yaxes(visible=False); return sty(f, 300)
NOP = lambda n: tuple(empty("No data") for _ in range(n))
def clean_str(s):
    t = s.astype(str).str.strip(); return t.where(~(s.isna() | t.str.lower().isin(BLANK)), np.nan)
def to_num(s):
    if pd.api.types.is_numeric_dtype(s): return s.astype(float)
    return pd.to_numeric(s.astype(str).str.replace(r"[$,%£€₹\s]", "", regex=True), errors="coerce")
def to_dt(s):
    try: return pd.to_datetime(s, errors="coerce", format="mixed")
    except Exception: return pd.to_datetime(s, errors="coerce")
def read_csv_any(f):
    p = f if isinstance(f, str) else getattr(f, "name", f)
    try: d = pd.read_csv(p)
    except Exception: d = pd.read_csv(p, sep=None, engine="python", encoding_errors="replace")
    if d.empty: raise ValueError("A file contains no rows.")
    return d
DEF = dict(start="2026-11-02", weeks=12, max_share=.9, tier1=.6, allow_exc=False, count_inf=False, stale=18, conc=3, ready=90, risk=70, crit_unc=.25, nosens=False, cap_boost=0.0,
           w=dict(hours=.25, crit=.15, dead=.15, prof=.10, dep=.10, subst=.15, lead=.10), hire_lead=10, hire_fee=.2, hire_prem=1.15, ctr_lead=2, ctr_prem=1.6, redeploy=0.0, slip=0, hpw=36)

# ------------------------------ FICTIONAL synthetic data ------------------------------
SKILLS = [("Python", "Programming", "", "py;python3"), ("SQL", "Data", "", "structured query language;t-sql;postgres"), ("Statistics", "Data", "", "stats"), ("Data Engineering", "Data", "SQL;Python", "etl;data pipelines"),
    ("Machine Learning", "Data", "Python;Statistics", "ml"), ("NLP", "Data", "Machine Learning", "natural language processing"), ("Computer Vision", "Data", "Machine Learning", "cv"), ("Data Visualization", "Data", "SQL", "dataviz;bi dashboards"),
    ("Cloud Architecture", "Infrastructure", "Networking", "cloud design;aws architecture"), ("DevOps", "Infrastructure", "", "ci/cd"), ("Kubernetes", "Infrastructure", "DevOps", "k8s"), ("Networking", "Infrastructure", "", "network engineering"),
    ("Cybersecurity", "Security", "Networking", "infosec;security engineering"), ("Frontend Development", "Programming", "", "front end;react"), ("Backend Development", "Programming", "Python", "back end;api development"), ("Mobile Development", "Programming", "", "ios;android"),
    ("QA Automation", "Programming", "", "test automation"), ("Embedded Systems", "Programming", "", ""), ("UX Design", "Design", "", "ux;user experience"), ("UI Design", "Design", "", "visual design"), ("Product Management", "Business", "", "pm;product owner"),
    ("Project Management", "Business", "", "pmp;delivery management"), ("Business Analysis", "Business", "", "ba;requirements analysis"), ("Agile Coaching", "Business", "", "scrum master"), ("Financial Modeling", "Finance", "", "fp&a modelling"),
    ("Digital Marketing", "Marketing", "", "seo;performance marketing"), ("Customer Success", "Operations", "", "cs"), ("Supply Chain Analytics", "Operations", "SQL", "scm analytics"), ("ERP Configuration", "Operations", "", "sap config"),
    ("Technical Writing", "Business", "", "documentation"), ("Legal Compliance", "Governance", "", "regulatory compliance")]
DEFSK = pd.DataFrame([dict(canonical_name=n, category=c, prerequisites=p, aliases=a) for n, c, p, a in SKILLS])
DEPTS = {"Engineering": 70, "Data & Analytics": 50, "Product": 35, "Design": 25, "Security & Infrastructure": 30, "Operations": 40, "Marketing": 25, "Finance": 25}
POOL = {"Engineering": ["Python", "Backend Development", "Frontend Development", "Mobile Development", "QA Automation", "DevOps", "Kubernetes", "Cloud Architecture", "Embedded Systems"],
        "Data & Analytics": ["Python", "SQL", "Statistics", "Data Engineering", "Machine Learning", "NLP", "Computer Vision", "Data Visualization"], "Product": ["Product Management", "Business Analysis", "Agile Coaching", "Technical Writing", "Project Management", "Data Visualization"],
        "Design": ["UX Design", "UI Design", "Frontend Development", "Technical Writing"], "Security & Infrastructure": ["Networking", "Cybersecurity", "Cloud Architecture", "DevOps", "Kubernetes", "Legal Compliance"],
        "Operations": ["Supply Chain Analytics", "ERP Configuration", "Customer Success", "SQL", "Project Management", "Business Analysis"], "Marketing": ["Digital Marketing", "Data Visualization", "SQL", "Technical Writing", "UX Design"], "Finance": ["Financial Modeling", "SQL", "Business Analysis", "Legal Compliance", "Statistics"]}
ROLES = {"Engineering": ["Software Engineer", "Senior Engineer", "SRE"], "Data & Analytics": ["Data Analyst", "Data Engineer", "Data Scientist"], "Product": ["Product Manager", "Business Analyst", "Delivery Lead"], "Design": ["UX Designer", "UI Designer"],
         "Security & Infrastructure": ["Security Engineer", "Network Engineer", "Platform Engineer"], "Operations": ["Operations Analyst", "ERP Consultant"], "Marketing": ["Marketing Analyst", "Content Strategist"], "Finance": ["Financial Analyst", "Compliance Analyst"]}
SCARCE = {"Data Engineering", "NLP", "Kubernetes", "Cybersecurity", "Computer Vision"}
PROJ = [("Customer Data Platform", "Data & Analytics", "Data Engineering|SQL|Python|Data Visualization"), ("Fraud Detection Engine", "Data & Analytics", "Machine Learning|Data Engineering|Python|Cybersecurity"), ("Cloud Migration Wave 2", "Engineering", "Cloud Architecture|Kubernetes|DevOps|Networking"),
    ("Zero Trust Rollout", "Security & Infrastructure", "Cybersecurity|Networking|Cloud Architecture|Legal Compliance"), ("Mobile Banking App", "Engineering", "Mobile Development|Backend Development|UX Design|QA Automation"), ("Supply Chain Control Tower", "Operations", "Supply Chain Analytics|Data Engineering|SQL|Data Visualization"),
    ("Personalisation Engine", "Data & Analytics", "Machine Learning|Backend Development|Data Engineering|Python"), ("Compliance Automation", "Finance", "Legal Compliance|Business Analysis|Backend Development|SQL"), ("Self-Service Analytics", "Data & Analytics", "Data Visualization|SQL|Data Engineering|Business Analysis"),
    ("ERP Modernisation", "Operations", "ERP Configuration|Business Analysis|Project Management|SQL"), ("Support Chatbot", "Product", "NLP|Backend Development|UX Design|Machine Learning"), ("Quality Inspection Vision", "Engineering", "Computer Vision|Machine Learning|Embedded Systems|Python"),
    ("Brand Experience Redesign", "Design", "UX Design|UI Design|Frontend Development|Digital Marketing"), ("Pricing Optimisation", "Finance", "Financial Modeling|Statistics|Machine Learning|SQL"), ("Partner API Gateway", "Engineering", "Backend Development|Cybersecurity|DevOps|Technical Writing"),
    ("Data Lakehouse Build", "Data & Analytics", "Data Engineering|Cloud Architecture|Kubernetes|SQL"), ("Kubernetes Platform", "Engineering", "Kubernetes|DevOps|Cloud Architecture|Cybersecurity"), ("Marketing Attribution Revamp", "Marketing", "Digital Marketing|Data Engineering|SQL|Data Visualization"),
    ("Regulatory Reporting Upgrade", "Finance", "Legal Compliance|SQL|Financial Modeling|Data Visualization"), ("Onboarding Experience", "Product", "Product Management|UX Design|Frontend Development|Customer Success"), ("Demand Forecasting", "Operations", "Statistics|Machine Learning|Supply Chain Analytics|Python"),
    ("Identity Platform", "Security & Infrastructure", "Cybersecurity|Backend Development|Cloud Architecture|DevOps"), ("Customer Success Portal", "Product", "Customer Success|Frontend Development|Backend Development|UX Design"), ("Edge Device Firmware", "Engineering", "Embedded Systems|QA Automation|Networking|Cybersecurity"),
    ("Finance Close Automation", "Finance", "Financial Modeling|Business Analysis|ERP Configuration|Python"), ("Security Operations Centre", "Security & Infrastructure", "Cybersecurity|Networking|DevOps|Project Management"), ("Recommendation Service", "Data & Analytics", "Machine Learning|NLP|Data Engineering|Backend Development"),
    ("Web Accessibility Overhaul", "Design", "UI Design|Frontend Development|QA Automation|Technical Writing"), ("Order Management Rebuild", "Operations", "Backend Development|ERP Configuration|Kubernetes|SQL"), ("Knowledge Base Search", "Product", "NLP|Data Engineering|Frontend Development|Technical Writing")]
def make_data(seed=5):
    r = np.random.default_rng(seed); H0 = pd.Timestamp(DEF["start"]); names = list(DEFSK.canonical_name); emp, es = [], []; n = 0
    for d, cnt in DEPTS.items():
        pool = POOL[d]; wt = np.array([.3 if s in SCARCE else 1.0 for s in pool]); wt = wt / wt.sum()
        for _ in range(cnt):
            n += 1; eid = "E%03d" % n; ey = float(np.clip(r.gamma(2.2, 3.2), .5, 25)); u = r.random(); av = float(r.choice([40, 32], p=[.85, .15]))
            al = float(r.uniform(36, 40)) if u < .12 else (float(r.uniform(0, 12)) if u < .27 else float(np.clip(r.normal(24, 8), 8, 34)))
            emp.append(dict(employee_id=eid, department=d, current_role=str(r.choice(ROLES[d])), experience=round(ey, 1), available_hours=av, allocated_hours=round(min(al, av), 1), location=str(r.choice(["London", "Bengaluru", "Austin", "Berlin"])),
                            hourly_cost=round(float(np.clip(28 + ey * 3.2 + r.normal(0, 5), 25, 150)), 1), career_interests=str(r.choice(names)) if r.random() < .4 else ""))
            ch = list(r.choice(pool, size=min(int(r.integers(3, 7)), len(pool)), replace=False, p=wt))
            if r.random() < .3: ch.append(str(r.choice(names)))
            for s in set(ch):
                lv = int(r.choice([1, 2, 3, 4, 5], p=[.45, .35, .15, .04, .01] if s in SCARCE else [.15, .3, .3, .18, .07])); lv = min(5, lv + (1 if ey > 12 and r.random() < .4 else 0))
                src = str(r.choice(["verified", "self_reported", "inferred"], p=[.55, .35, .10])); cf = float(r.uniform(.85, 1) if src == "verified" else (r.uniform(.5, .85) if src == "self_reported" else r.uniform(.3, .6)))
                es.append(dict(employee_id=eid, skill=s, proficiency=lv, last_assessed_date=(H0 - pd.Timedelta(days=float(np.clip(r.exponential(330), 30, 1400)))).strftime("%Y-%m-%d"), assessment_source=src, confidence=round(cf, 2), effective_from=None))
    emp = pd.DataFrame(emp); es = pd.DataFrame(es); recent = (H0 - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    def put(e, s, lv): 
        nonlocal es; es = es[~((es.employee_id == e) & (es.skill == s))]; es = pd.concat([es, pd.DataFrame([dict(employee_id=e, skill=s, proficiency=lv, last_assessed_date=recent, assessment_source="verified", confidence=.95, effective_from=None)])], ignore_index=True)
    for s, (d, k) in {"Data Engineering": ("Data & Analytics", 3), "NLP": ("Data & Analytics", 2), "Kubernetes": ("Engineering", 3), "Cybersecurity": ("Security & Infrastructure", 2), "Computer Vision": ("Data & Analytics", 1)}.items():
        es.loc[(es.skill == s) & (es.proficiency >= 4), "proficiency"] = 3
        for j, e in enumerate(r.choice(emp.loc[emp.department == d, "employee_id"].values, size=k, replace=False)): put(e, s, 5 if j == 0 else 4)
    for s, d, prs, k in [("Data Engineering", "Data & Analytics", ["SQL", "Python"], 6), ("Kubernetes", "Engineering", ["DevOps"], 5), ("Cybersecurity", "Security & Infrastructure", ["Networking"], 4)]:
        ex = set(es[(es.skill == s) & (es.proficiency >= 4)].employee_id); pl = [e for e in emp.loc[emp.department == d, "employee_id"] if e not in ex]
        for e in r.choice(pl, size=k, replace=False):
            es = es[~((es.employee_id == e) & (es.skill == s))]
            for p in prs: put(e, p, 3)
            emp.loc[emp.employee_id == e, "allocated_hours"] = round(float(r.uniform(2, 10)), 1)
    es = es.sort_values("proficiency").drop_duplicates(["employee_id", "skill"], keep="last").reset_index(drop=True)
    pr, rq = [], []
    for i, (nm, d, th) in enumerate(PROJ):
        pid = "P%02d" % (i + 1); st = H0 + pd.Timedelta(days=float(r.uniform(-14, 42))); dl = st + pd.Timedelta(weeks=float(r.uniform(8, 26))); tot = 0
        for s in th.split("|"):
            sc = s in SCARCE; hrs = int(r.integers(250, 600) if sc else r.integers(60, 320)); tot += hrs; rb = max(dl - pd.Timedelta(weeks=float(r.uniform(0, 3))), st + pd.Timedelta(weeks=3))
            rq.append(dict(project_id=pid, skill=s, required_proficiency=int(r.choice([3, 4, 4, 5] if sc else [2, 3, 3, 4])), required_hours=hrs, required_headcount=int(r.choice([1, 1, 2]) if sc else (2 if r.random() < .1 else 1)), required_by_date=rb.strftime("%Y-%m-%d")))
        pr.append(dict(project_id=pid, project_name=nm, department=d, priority=int(r.choice([1, 2, 3, 4, 5], p=[.1, .2, .3, .25, .15])), start_date=st.strftime("%Y-%m-%d"), deadline=dl.strftime("%Y-%m-%d"), estimated_effort=tot, budget=int(tot * 75 * r.uniform(1.1, 1.4)), status="Active" if st <= H0 else "Planned"))
    trn, cid = [], 0
    for nm, c, pre, al in SKILLS:
        p2 = ";".join("%s:2" % x for x in pre.split(";") if x)
        for mc, res, dur, cost, suc, pq in [(0, 3, (8, 12), (2800, 6000), .70, p2), (1, 3, (4, 6), (1500, 3000), .85, p2), (2, 4, (6, 10), (3500, 7000), .80, p2), (3, 5, (8, 12), (5000, 9000), .65, p2.replace(":2", ":3"))]:
            cid += 1; trn.append(dict(course_id="C%03d" % cid, skill=nm, min_current=mc, result_proficiency=res, prerequisites=pq, duration_weeks=int(r.integers(dur[0], dur[1] + 1)), cost=int(r.integers(cost[0], cost[1])), hours_per_week=6, success_rate=suc))
    return dict(emp=emp, es=es, proj=pd.DataFrame(pr), req=pd.DataFrame(rq), trn=pd.DataFrame(trn), skills=DEFSK.copy())

# ------------------------------ validation and loading ------------------------------
FIELDS = {"emp": {"employee_id": (1, ["emp_id", "staff_id", "id"]), "department": (1, ["dept", "team"]), "current_role": (0, ["role", "job_title", "title"]), "experience": (0, ["years_experience"]), "available_hours": (1, ["weekly_available_hours", "capacity_hours"]),
                   "allocated_hours": (1, ["weekly_allocated_hours", "committed_hours"]), "location": (0, ["office", "site"]), "hourly_cost": (1, ["cost_per_hour", "hourly_rate", "rate"]), "career_interests": (0, ["interests"]), "available_from": (0, []), "available_until": (0, [])},
          "es": {"employee_id": (1, ["emp_id", "staff_id"]), "skill": (1, ["skill_name"]), "proficiency": (1, ["level", "proficiency_level"]), "last_assessed_date": (0, ["assessed_on"]), "assessment_source": (0, ["source"]), "confidence": (0, []), "effective_from": (0, [])},
          "proj": {"project_id": (1, ["id"]), "project_name": (0, ["name"]), "department": (0, ["dept"]), "priority": (1, ["project_priority"]), "start_date": (1, ["start"]), "deadline": (1, ["end_date", "due_date"]), "estimated_effort": (0, ["effort"]), "budget": (0, []), "status": (0, [])},
          "req": {"project_id": (1, ["id"]), "skill": (1, ["skill_name"]), "required_proficiency": (1, ["min_proficiency", "required_level"]), "required_hours": (1, ["hours", "effort_hours"]), "required_headcount": (0, ["headcount"]), "required_by_date": (0, ["required_by", "needed_by"])},
          "trn": {"course_id": (1, ["id"]), "skill": (1, ["skill_name", "skills_developed"]), "min_current": (0, ["min_current_proficiency"]), "result_proficiency": (1, ["resulting_proficiency", "proficiency_after"]), "prerequisites": (0, ["prereqs"]), "duration_weeks": (1, ["duration"]),
                  "cost": (1, ["price"]), "hours_per_week": (0, []), "success_rate": (0, ["completion_rate"])},
          "skills": {"canonical_name": (1, ["skill", "name"]), "category": (0, []), "prerequisites": (0, []), "aliases": (0, [])}}
def parse_map(text):
    ov = {}
    for p in re.split(r"[,;\n]", text or ""):
        if "=" in p: k, v = p.split("=", 1); ov[norm(k.replace(".", "_") if False else k.strip())] = norm(v)
    return ov
def map_table(raw, t, ov, iss):
    d = raw.copy(); d.columns = [norm(c) for c in d.columns]; ren = {}
    for f, (req, al) in FIELDS[t].items():
        c = ov.get(t + "." + f) or ov.get(f); c = c if c in d.columns else next((a for a in [f] + al if a in d.columns and a not in ren), None)
        if c is None or c in ren:
            if req: iss.append(("error", "%s table: required field '%s' not found (columns: %s). Use the mapping box, e.g. %s=your_column." % (t, f, ", ".join(map(str, raw.columns[:10])), f)))
            continue
        if c != f and f in d.columns: d = d.drop(columns=[f])
        ren[c] = f
    d = d.rename(columns=ren); d = d.loc[:, ~d.columns.duplicated()]; return d[[f for f in FIELDS[t] if f in d.columns]]
def col(d, c, default=np.nan): return d[c] if c in d.columns else pd.Series(default, index=d.index)
def alias_map(sk):
    m = {}
    for r in sk.itertuples():
        for a in [r.canonical_name] + [x for x in str(r.aliases).split(";") if x.strip() and x != "nan"]: m[sk_key(a)] = r.canonical_name
    return m
def parse_pre(s):
    out = []
    for p in str(s).split(";"):
        if ":" in p:
            n, l = p.rsplit(":", 1)
            try: out.append((n.strip(), int(float(l))))
            except Exception: pass
    return out
def c_emp(d, iss, ex):
    d = d.copy(); d["employee_id"] = d.employee_id.astype(str).str.strip(); m = d.employee_id.str.lower().isin(BLANK); ex += [("employees", int(i), "missing employee_id") for i in d.index[m]]; d = d[~m]
    m = d.duplicated("employee_id", keep="first")
    if m.any(): iss.append(("warn", "%d duplicate employee_id rows ignored (first kept): %s" % (m.sum(), ", ".join(d.employee_id[m].head(5))))); ex += [("employees", int(i), "duplicate employee_id") for i in d.index[m]]; d = d[~m]
    for c in ("available_hours", "allocated_hours", "hourly_cost"): d[c] = to_num(d[c])
    z = d[["available_hours", "allocated_hours", "hourly_cost"]]; m = z.isna().any(axis=1) | (z < 0).any(axis=1) | (d.available_hours > 80)
    if m.any(): iss.append(("warn", "%d employees excluded (missing, negative or implausible hours/cost): %s" % (m.sum(), ", ".join(d.employee_id[m].head(6))))); ex += [("employees", int(i), "invalid hours or cost") for i in d.index[m]]; d = d[~m]
    m = d.allocated_hours > d.available_hours
    if m.any(): iss.append(("warn", "%d employees have allocated hours above available hours; allocation was capped (they have no free capacity)." % m.sum())); d.loc[m, "allocated_hours"] = d.loc[m, "available_hours"]
    d["current_role"] = col(d, "current_role", "n/a").fillna("n/a"); d["location"] = col(d, "location", "n/a").fillna("n/a"); d["career_interests"] = col(d, "career_interests", "").fillna("").astype(str); d["department"] = d.department.fillna("n/a").astype(str)
    d["experience"] = to_num(col(d, "experience")); d["available_from"] = to_dt(col(d, "available_from")); d["available_until"] = to_dt(col(d, "available_until"))
    return d.reset_index(drop=True)
def c_es(d, emp, ns, iss, ex):
    d = d.copy(); d["employee_id"] = d.employee_id.astype(str).str.strip(); d["skill"] = d.skill.map(ns); d["proficiency"] = to_num(d.proficiency)
    m = d.skill.isna() | d.proficiency.isna() | (d.proficiency < 0) | (d.proficiency > 5)
    if m.any(): iss.append(("warn", "%d employee-skill rows excluded (missing skill or proficiency outside 0-5)." % m.sum())); ex += [("employee_skills", int(i), "invalid skill or proficiency") for i in d.index[m]]; d = d[~m]
    m = ~d.employee_id.isin(emp.employee_id)
    if m.any(): iss.append(("warn", "%d employee-skill rows excluded (employee_id not in the employee table)." % m.sum())); ex += [("employee_skills", int(i), "unknown employee") for i in d.index[m]]; d = d[~m]
    raw = col(d, "assessment_source"); src = raw.astype(str).str.lower(); d["assessment_source"] = np.where(src.str.contains("infer"), "inferred", np.where(src.str.contains("verif|assess|certif|test"), "verified", "self_reported"))
    if raw.isna().any(): iss.append(("info", "%d skill rows have no assessment source and are treated as self-reported." % raw.isna().sum()))
    dc = d.assessment_source.map({"verified": .9, "self_reported": .65, "inferred": .4}); d["confidence"] = to_num(col(d, "confidence")).clip(0, 1).fillna(dc)
    d["last_assessed_date"] = to_dt(col(d, "last_assessed_date")); d["effective_from"] = to_dt(col(d, "effective_from")); d["proficiency"] = d.proficiency.round().astype(int)
    n0 = len(d); d = d.sort_values("proficiency", kind="mergesort").drop_duplicates(["employee_id", "skill"], keep="last")
    if len(d) < n0: iss.append(("warn", "%d duplicate employee-skill rows merged (highest proficiency kept)." % (n0 - len(d))))
    return d.reset_index(drop=True)
def c_proj(d, iss, ex):
    d = d.copy(); d["project_id"] = d.project_id.astype(str).str.strip(); m = d.project_id.str.lower().isin(BLANK) | d.duplicated("project_id")
    if m.any(): iss.append(("warn", "%d projects excluded (missing or duplicate project_id)." % m.sum())); ex += [("projects", int(i), "missing or duplicate id") for i in d.index[m]]; d = d[~m]
    d["start_date"] = to_dt(d.start_date); d["deadline"] = to_dt(d.deadline); d["priority"] = to_num(d.priority)
    m = d.start_date.isna() | d.deadline.isna() | (d.deadline <= d.start_date) | d.priority.isna()
    if m.any(): iss.append(("warn", "%d projects excluded (missing/impossible dates or priority): %s" % (m.sum(), ", ".join(d.project_id[m].head(6))))); ex += [("projects", int(i), "impossible dates or missing priority") for i in d.index[m]]; d = d[~m]
    if ((d.priority < 1) | (d.priority > 5)).any(): iss.append(("warn", "Some priorities outside 1-5 were clipped.")); d["priority"] = d.priority.clip(1, 5)
    d["project_name"] = col(d, "project_name").fillna(d.project_id).astype(str); d["department"] = col(d, "department", "n/a").fillna("n/a").astype(str); d["status"] = col(d, "status", "Active").fillna("Active")
    d["estimated_effort"] = to_num(col(d, "estimated_effort")); d["budget"] = to_num(col(d, "budget")); return d.reset_index(drop=True)
def c_req(d, proj, ns, iss, ex):
    d = d.copy(); d["project_id"] = d.project_id.astype(str).str.strip(); d["skill"] = d.skill.map(ns); d["required_proficiency"] = to_num(d.required_proficiency); d["required_hours"] = to_num(d.required_hours)
    d["required_headcount"] = to_num(col(d, "required_headcount", 1)).fillna(1).clip(lower=1).round().astype(int); d["required_by_date"] = to_dt(col(d, "required_by_date"))
    pj = proj.set_index("project_id"); m = (~d.project_id.isin(pj.index)) | d.skill.isna() | d.required_proficiency.isna() | (d.required_proficiency < 1) | (d.required_proficiency > 5) | d.required_hours.isna() | (d.required_hours < 0)
    if m.any(): iss.append(("warn", "%d requirement rows excluded (unknown project, missing skill, proficiency outside 1-5, or negative/missing hours)." % m.sum())); ex += [("requirements", int(i), "invalid requirement") for i in d.index[m]]; d = d[~m]
    d["required_by_date"] = d.required_by_date.fillna(d.project_id.map(pj.deadline)); m = d.required_by_date <= d.project_id.map(pj.start_date)
    if m.any(): iss.append(("warn", "%d requirements excluded (required-by date not after project start)." % m.sum())); ex += [("requirements", int(i), "impossible date") for i in d.index[m]]; d = d[~m]
    n0 = len(d); d = d.drop_duplicates()
    if len(d) < n0: iss.append(("warn", "%d exact duplicate requirement rows removed." % (n0 - len(d))))
    d["required_proficiency"] = d.required_proficiency.round().astype(int); return d.reset_index(drop=True)
def c_trn(d, ns, iss, ex):
    d = d.copy(); d["skill"] = d.skill.map(ns); d["result_proficiency"] = to_num(d.result_proficiency); d["duration_weeks"] = to_num(d.duration_weeks); d["cost"] = to_num(d.cost)
    m = d.skill.isna() | d.result_proficiency.isna() | d.duration_weeks.isna() | (d.duration_weeks <= 0) | d.cost.isna() | (d.cost < 0)
    if m.any(): iss.append(("warn", "%d training courses excluded (missing skill, non-positive duration or invalid cost)." % m.sum())); ex += [("training", int(i), "invalid course") for i in d.index[m]]; d = d[~m]
    d["min_current"] = to_num(col(d, "min_current", 0)).fillna(0); d["hours_per_week"] = to_num(col(d, "hours_per_week", 6)).fillna(6); d["success_rate"] = to_num(col(d, "success_rate", .8)).fillna(.8).clip(.05, 1); d["prerequisites"] = col(d, "prerequisites", "").fillna("").astype(str)
    return d.reset_index(drop=True)
def load_all(raw, mapping, S):
    iss, ex, ov = [], [], parse_map(mapping)
    sk = DEFSK.copy()
    if raw.get("skills") is not None:
        st = map_table(raw["skills"], "skills", ov, iss); st["category"] = col(st, "category", "Unclassified"); st["prerequisites"] = col(st, "prerequisites", "").fillna(""); st["aliases"] = col(st, "aliases", "").fillna(""); sk = st
    amap = alias_map(sk); unk = set()
    def ns(x):
        k = sk_key(x)
        if not k: return None
        if k not in amap: unk.add(str(x).strip()); amap[k] = str(x).strip()
        return amap[k]
    T = {}
    for t in ("emp", "es", "proj", "req", "trn"):
        if raw.get(t) is None: iss.append(("error", "Missing table: %s." % t)); continue
        T[t] = map_table(raw[t], t, ov, iss)
    errs = [m for l, m in iss if l == "error"]
    if errs: raise ValueError(" | ".join(errs))
    emp = c_emp(T["emp"], iss, ex); es = c_es(T["es"], emp, ns, iss, ex); proj = c_proj(T["proj"], iss, ex); req = c_req(T["req"], proj, ns, iss, ex); trn = c_trn(T["trn"], ns, iss, ex)
    if emp.empty or proj.empty: raise ValueError("No valid employees or projects remain after validation.")
    used = set(es.skill) | set(req.skill) | set(trn.skill); miss = sorted(used - set(sk.canonical_name))
    if miss: iss.append(("warn", "%d skill names were not in the skills dictionary and were added as new skills (not discarded): %s" % (len(miss), ", ".join(miss[:8])))); sk = pd.concat([sk, pd.DataFrame([dict(canonical_name=n, category="Unclassified", prerequisites="", aliases="") for n in miss])], ignore_index=True)
    return dict(emp=emp, es=es, proj=proj, req=req, trn=trn, skills=sk.reset_index(drop=True), issues=iss, excluded=ex, amap=amap, rows_in={t: len(T[t]) for t in T})

# ------------------------------ capacity model ------------------------------
def prepare(D, S):
    emp = D["emp"].reset_index(drop=True); es = D["es"]; proj = D["proj"].set_index("project_id"); req = D["req"].reset_index(drop=True)
    H0 = pd.Timestamp(S["start"]).normalize(); W = int(S["weeks"]); ws = pd.date_range(H0, periods=W, freq="7D"); we = ws + pd.Timedelta(days=7)
    skills = list(D["skills"].canonical_name); sidx = {s: i for i, s in enumerate(skills)}; eidx = {e: i for i, e in enumerate(emp.employee_id)}; E = len(emp)
    av = emp.available_hours.values.astype(float) * (1 + float(S.get("cap_boost", 0))); al = emp.allocated_hours.values.astype(float); avl = np.tile(av[:, None], (1, W))
    af = pd.to_datetime(emp.available_from, errors="coerce"); au = pd.to_datetime(emp.available_until, errors="coerce")
    for i in range(E):
        if pd.notna(af.iloc[i]): avl[i, np.asarray(we <= af.iloc[i])] = 0
        if pd.notna(au.iloc[i]): avl[i, np.asarray(ws >= au.iloc[i])] = 0
    free = np.maximum(avl - al[:, None], 0) * (avl > 0); P = np.zeros((len(skills), E, W), dtype=np.int8)
    for r in es.itertuples():
        if r.assessment_source == "inferred" and not S["count_inf"]: continue
        e = eidx.get(r.employee_id); s = sidx.get(r.skill)
        if e is None or s is None: continue
        w0 = max(0, int(math.ceil((pd.Timestamp(r.effective_from) - H0).days / 7))) if pd.notna(r.effective_from) else 0
        if w0 < W: P[s, e, w0:] = np.maximum(P[s, e, w0:], int(r.proficiency))
    rows = []
    for i, r in enumerate(req.itertuples()):
        if r.project_id not in proj.index or r.skill not in sidx: continue
        p = proj.loc[r.project_id]; st = pd.Timestamp(p.start_date); en = pd.Timestamp(r.required_by_date) if pd.notna(r.required_by_date) else pd.Timestamp(p.deadline)
        wi = np.nonzero(np.asarray((we > st) & (ws < en)))[0]; tw = max(1, int(math.ceil((en - st).days / 7))); dem = float(r.required_hours) * min(1.0, len(wi) / tw)
        rows.append(dict(rid="%s|%s|%d" % (r.project_id, r.skill, i), project_id=r.project_id, project_name=p.project_name, dept=p.department, prio=float(p.priority), skill=r.skill, s=sidx[r.skill], rp=int(r.required_proficiency), hours=float(r.required_hours),
                         hc=int(r.required_headcount), required_by=en, start=st, demand_h=dem, w_idx=[int(x) for x in wi], days_to_req=(en - H0).days))
    cols = ["rid", "project_id", "project_name", "dept", "prio", "skill", "s", "rp", "hours", "hc", "required_by", "start", "demand_h", "w_idx", "days_to_req"]
    return dict(emp=emp, ws=ws, we=we, free=free, avl=avl, P=P, skills=skills, sidx=sidx, eidx=eidx, R=pd.DataFrame(rows, columns=cols), H0=H0, W=W, intr=np.array([sidx.get(str(x), -1) for x in emp.career_interests]))
EMPTY = lambda: pd.DataFrame(dict(ei=np.zeros(0, int), ri=np.zeros(0, int), w=np.zeros(0, int), h=np.zeros(0), exc=np.zeros(0, int)))
def solve_lp(X, S):
    R, free, P, emp, W = X["R"], X["free"], X["P"], X["emp"], X["W"]; nR = len(R); ev, rv, wv, xv = [], [], [], []
    for ri in range(nR):
        r = R.iloc[ri]
        if r["demand_h"] <= 1e-9 or len(r["w_idx"]) == 0: continue
        wi = np.array(r["w_idx"]); Pm = P[int(r["s"])][:, wi]; f = free[:, wi] > 1e-9; ms = [(0, (Pm >= r["rp"]) & f)]
        if S["allow_exc"] and r["rp"] >= 2: ms.append((1, (Pm == r["rp"] - 1) & (Pm >= 1) & f))
        for flag, m in ms:
            ee, ww = np.nonzero(m); ev.append(ee); wv.append(wi[ww]); rv.append(np.full(len(ee), ri)); xv.append(np.full(len(ee), flag))
    if not ev or sum(len(a) for a in ev) == 0: return dict(assign=EMPTY(), method="LP (no feasible qualified pairs)")
    ev, wv, rv, xv = [np.concatenate(a).astype(int) for a in (ev, wv, rv, xv)]; nx = len(ev)
    pw = R["prio"].values ** 1.5 * (1 + 1 / (1 + np.maximum(R["days_to_req"].values, 0) / 14.0)); pr = P[R["s"].values[rv], ev, wv].astype(float); over = np.clip(pr - R["rp"].values[rv], 0, 3)
    cost = emp.hourly_cost.values[ev] / max(emp.hourly_cost.max(), 1); pref = (X["intr"][ev] == R["s"].values[rv]).astype(float)
    val = 10 * pw[rv] * (1 - .08 * over) - 5 * xv + .4 * pref - cost
    ew = ev * W + wv; uew, ewi = np.unique(ew, return_inverse=True); ny = len(uew); t1 = min(S["tier1"], S["max_share"])
    hc = R["hc"].values[rv]; m2 = hc > 1; uer, eri = np.unique(ev[m2] * nR + rv[m2], return_inverse=True); base = nR + len(uer)
    rows = [rv, nR + eri, base + ewi, base + np.arange(ny)]; cols = [np.arange(nx), np.nonzero(m2)[0], np.arange(nx), nx + np.arange(ny)]; vals = [np.ones(nx), np.ones(int(m2.sum())), np.ones(nx), -np.ones(ny)]
    A = sparse.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(base + ny, nx + ny)).tocsr(); fe = free[uew // W, uew % W]
    b = np.concatenate([R["demand_h"].values, R["demand_h"].values[uer % nR] / R["hc"].values[uer % nR], t1 * fe]); ub = np.concatenate([np.full(nx, np.inf), np.maximum(S["max_share"] - t1, 0) * fe])
    res = linprog(np.concatenate([-val, np.full(ny, 2.0)]), A_ub=A, b_ub=b, bounds=list(zip(np.zeros(nx + ny), ub)), method="highs")
    if res.status != 0: raise RuntimeError("LP status %s" % res.status)
    x = res.x[:nx]; k = x > 1e-6; return dict(assign=pd.DataFrame(dict(ei=ev[k], ri=rv[k], w=wv[k], h=x[k], exc=xv[k])), method="Linear program (SciPy HiGHS, exact optimum of the documented objective)")
def solve_greedy(X, S, by_prio=False):
    rem = X["free"] * S["max_share"]; R, P = X["R"], X["P"]; out = []
    order = R.sort_values(["prio", "days_to_req"], ascending=[False, True]).index if by_prio else R.sort_values("project_id", kind="mergesort").index
    for ri in order:
        r = R.loc[ri]; need = float(r["demand_h"]); cap = need / r["hc"]; used = {}
        if need <= 1e-9: continue
        for w in r["w_idx"]:
            if need <= 1e-9: break
            for e in np.nonzero((P[int(r["s"])][:, w] >= r["rp"]) & (rem[:, w] > 1e-9))[0]:
                t = min(need, rem[e, w], cap - used.get(e, 0.0))
                if t <= 1e-9: continue
                out.append((e, ri, w, t, 0)); rem[e, w] -= t; used[e] = used.get(e, 0.0) + t; need -= t
                if need <= 1e-9: break
    a = pd.DataFrame(out, columns=["ei", "ri", "w", "h", "exc"]) if out else EMPTY()
    return dict(assign=a.astype({"ei": int, "ri": int, "w": int, "exc": int}), method="Greedy " + ("priority-ordered fallback" if by_prio else "first-come baseline (project-ID order, first qualified employee, no fit or priority logic)"))
def plan_stats(X, plan):
    a = plan["assign"]; cov = np.zeros(len(X["R"])); load = np.zeros_like(X["free"])
    if len(a): np.add.at(cov, a.ri.values.astype(int), a.h.values); np.add.at(load, (a.ei.values.astype(int), a.w.values.astype(int)), a.h.values)
    return cov, load
def verify_plan(X, S, plan):
    R, P = X["R"], X["P"]; a = plan["assign"]; cov, load = plan_stats(X, plan); chk = []
    chk.append(("No employee-week exceeds available capacity", bool((load <= X["free"] * S["max_share"] + 1e-6).all()), "max load %.1f h" % (load.max() if load.size else 0)))
    chk.append(("No requirement is assigned more hours than its demand", bool((cov <= R["demand_h"].values + 1e-6).all()) if len(R) else True, "ok"))
    bad = 0
    if len(a):
        pr = P[R["s"].values[a.ri.values], a.ei.values, a.w.values]; rp = R["rp"].values[a.ri.values]; bad = int(((pr < rp) & (a.exc.values == 0)).sum() + ((pr < rp - 1) | (pr < 1)).sum() * 0 + ((pr < rp) & (a.exc.values == 1) & (pr < rp - 1)).sum())
        if not S["allow_exc"]: bad += int((a.exc.values == 1).sum())
    chk.append(("Required proficiency respected (exceptions only if permitted and labelled)", bad == 0, "%d violations" % bad))
    hcv = 0
    if len(a):
        g = a.groupby(["ei", "ri"]).h.sum().reset_index(); lim = R["demand_h"].values[g.ri.values] / R["hc"].values[g.ri.values]; hcv = int((g.h.values > lim + 1e-6).sum())
    chk.append(("Required headcount respected (hours per person capped at demand / headcount)", hcv == 0, "%d violations" % hcv)); return chk

# ------------------------------ analytics ------------------------------
def is_stale(d, H0, months): return True if nul(d) else (H0 - pd.Timestamp(d)).days > months * 30.44
def lead_min(D, skill, rp):
    t = D["trn"]; t = t[(t.skill == skill) & (t.result_proficiency >= rp)]; return int(t.duration_weeks.min()) if len(t) else None
def train_cands(D, S, skill, rp, res):
    X = D["X"]; si = X["sidx"].get(skill)
    if si is None: return pd.DataFrame()
    P, emp, sx = X["P"], X["emp"], X["sidx"]; cs = [c for c in D["trn"][(D["trn"].skill == skill) & (D["trn"].result_proficiency >= rp)].itertuples()]; rows = []
    for e in range(len(emp)):
        lv = int(P[si, e, 0])
        if lv >= rp or res[e].mean() < 4: continue
        best = None
        for c in cs:
            if lv < c.min_current: continue
            miss = [("%s>=%d" % (n, l)) for n, l in parse_pre(c.prerequisites) if int(P[sx[n], e, 0]) < l] if True else []
            if len(miss) > 1: continue
            row = dict(ei=e, employee_id=emp.employee_id.iloc[e], department=emp.department.iloc[e], level=lv, course_id=c.course_id, result=int(c.result_proficiency), weeks=int(c.duration_weeks), cost=float(c.cost), success=float(c.success_rate), hpw=float(c.hours_per_week),
                       rate=float(emp.hourly_cost.iloc[e]), free_wk=float(res[e].mean()), status="eligible" if not miss else "blocked: needs " + miss[0])
            if best is None or (row["status"] == "eligible", -row["cost"]) > (best["status"] == "eligible", -best["cost"]): best = row
        if best: rows.append(best)
    d = pd.DataFrame(rows)
    return d.sort_values(["status", "weeks", "cost"], ascending=[True, True, True]).reset_index(drop=True) if len(d) else d
def status_of(score, S): return "Ready" if score >= S["ready"] else ("At Risk" if score >= S["risk"] else "Critical")
def analyze(D, S, plan, full=True):
    X = D["X"]; R = X["R"]; P, free, avl = X["P"], X["free"], X["avl"]; cov, load = plan_stats(X, plan); a = plan["assign"]; H0 = X["H0"]
    nas = a.groupby("ri").ei.nunique().reindex(range(len(R))).fillna(0).values if len(a) else np.zeros(len(R)); gross = np.zeros(len(R)); nq = np.zeros(len(R))
    for i, r in enumerate(R.itertuples()):
        if len(r.w_idx) == 0: continue
        q = P[r.s][:, r.w_idx] >= r.rp; gross[i] = float((q * free[:, r.w_idx]).sum()); nq[i] = float(q.any(1).sum())
    Q = R[["rid", "project_id", "project_name", "dept", "skill", "rp", "hours", "hc", "required_by", "demand_h", "prio", "days_to_req"]].copy(); Q["covered"] = np.minimum(cov, R["demand_h"].values) if len(R) else cov
    Q["unc"] = np.maximum(Q.demand_h - Q.covered, 0); Q.loc[Q.unc < 1e-6, "unc"] = 0.0; Q["cov_pct"] = np.where(Q.demand_h > 1e-9, Q.covered / np.where(Q.demand_h > 1e-9, Q.demand_h, 1), np.nan); Q["gross"] = gross; Q["n_qual"] = nq; Q["n_assigned"] = nas
    res = np.maximum(free * S["max_share"] - load, 0); A = dict(req=Q, res=res, load=load, cov=cov); prow = []
    for _, p in D["proj"].iterrows():
        g = Q[(Q.project_id == p.project_id) & (Q.demand_h > 1e-9)]
        if g.empty: prow.append(dict(project_id=p.project_id, name=p.project_name, dept=p.department, prio=p.priority, deadline=p.deadline, demand=0.0, covered=0.0, coverage=np.nan, worst=np.nan, score=np.nan, status="No demand", blocking=[], conflicts=0, lead_conf=[])); continue
        c = g.covered.sum() / g.demand_h.sum(); worst = float(g.cov_pct.min()); sc = 100 * (.6 * c + .4 * worst); blk = g[g.cov_pct < .9].sort_values("unc", ascending=False); lc = []
        for r in blk.itertuples():
            lt = lead_min(D, r.skill, r.rp); lead = min(lt if lt else 999, S["hire_lead"])
            if lead > (r.required_by - H0).days / 7: lc.append("%s (fastest build route %d wk > %.1f wk available)" % (r.skill, lead, (r.required_by - H0).days / 7))
        prow.append(dict(project_id=p.project_id, name=p.project_name, dept=p.department, prio=p.priority, deadline=p.deadline, demand=float(g.demand_h.sum()), covered=float(g.covered.sum()), coverage=c, worst=worst, score=sc, status=status_of(sc, S),
                         blocking=blk.skill.tolist(), conflicts=int(((blk.unc > 8) & (blk.gross >= blk.demand_h * .999)).sum()), lead_conf=lc))
    A["proj"] = pd.DataFrame(prow); dm, cv = float(Q.demand_h.sum()), float(Q.covered.sum()); pj = A["proj"]
    A["kpi"] = dict(demand=dm, covered=cv, unc=dm - cv, cov=cv / dm if dm > 0 else np.nan, ready=int((pj.status == "Ready").sum()), risk=int((pj.status == "At Risk").sum()), crit=int((pj.status == "Critical").sum()), cost=float((a.h.values * X["emp"].hourly_cost.values[a.ei.values.astype(int)]).sum()) if len(a) else 0.0,
                    maxutil=float((load / np.where(X["avl"] > 0, X["avl"], 1)).max()) if load.size else 0.0, nemp=int(a.ei.nunique()) if len(a) else 0, nexc=int((a.exc == 1).sum()) if len(a) else 0)
    if full: A["skills"] = skill_table(D, S, A, plan)
    return A
def skill_table(D, S, A, plan):
    X = D["X"]; R = X["R"]; P, free, avl = X["P"], X["free"], X["avl"]; Q = A["req"]; res = A["res"]; H0 = X["H0"]; w = S["w"]; sw = sum(w.values()) or 1.0; rows = []
    for sk in Q[Q.demand_h > 1e-9].skill.unique():
        s = X["sidx"][sk]; rr = R[(R.skill == sk) & (R.demand_h > 1e-9)]; q = Q[(Q.skill == sk) & (Q.demand_h > 1e-9)]; uw = sorted({x for l in rr.w_idx for x in l}); minrp, maxrp, hc = int(rr.rp.min()), int(rr.rp.max()), int(rr.hc.max())
        dem, cv, unc = float(q.demand_h.sum()), float(q.covered.sum()), float(q.unc.sum()); Ps = P[s]; qm = Ps[:, uw] >= minrp; n_hold = int((Ps[:, -1] >= 1).sum()); n_q = int(qm.any(1).sum()); n_exp = int((Ps[:, -1] >= 3).sum())
        gross = float((qm * free[:, uw]).sum()); avail = float((qm * avl[:, uw]).sum()); capfull = float(((Ps >= minrp) * free).sum()); sig = unc >= max(8, .05 * dem); fl = []
        if sig:
            if n_hold < hc: fl.append("Skill shortage")
            elif n_q < hc: fl.append("Proficiency shortage")
            elif avail < dem - 1e-6: fl.append("Headcount shortage")
            elif capfull < dem - 1e-6: fl.append("Allocation shortage")
            elif gross < dem - 1e-6: fl.append("Timing shortage")
            else: fl.append("Capacity contention")
        if n_exp <= S["conc"]: fl.append("Concentration risk")
        crit = q[q.unc > np.maximum(8, .05 * q.demand_h)]; cd = crit.required_by.min() if len(crit) else pd.NaT; wk = (cd - H0).days / 7 if pd.notna(cd) else np.nan
        tc = train_cands(D, S, sk, minrp, res) if sig else pd.DataFrame(); trainable = int((tc.status == "eligible").sum()) if len(tc) else 0; lt = lead_min(D, sk, minrp); lead = min(lt if lt else 999, S["hire_lead"])
        ev = "uncovered %s h of %s h (%s); %d employees reach level %d+ (%d hold the skill at any level); qualified free capacity in windows %s h; qualified total available hours %s h; earliest critical date %s" % (nf(unc), nf(dem), pc0(unc / dem if dem else np.nan), n_q, minrp, n_hold, nf(gross), nf(avail), dts(cd))
        rows.append(dict(skill=sk, demand=dem, covered=cv, unc=unc, unc_pct=unc / dem if dem else np.nan, n_proj=int((q.unc > 1).sum()), minrp=minrp, maxrp=maxrp, n_hold=n_hold, n_qual=n_q, n_expert=n_exp, gross=gross, avail=avail, capfull=capfull, crit_date=cd, wk=wk,
                         trainable=trainable, flags=fl, evidence=ev, avgprio=float(np.average(q.prio, weights=q.unc + 1e-9)), lead=lead))
    d = pd.DataFrame(rows)
    if d.empty: return pd.DataFrame(columns=["skill", "prio_score", "flags", "unc", "demand", "unc_pct", "n_proj", "trainable", "crit_date", "evidence"])
    mu_, mp = max(d.unc.max(), 1e-9), max(d.n_proj.max(), 1); c = dict(hours=d.unc / mu_, crit=d.avgprio / 5, dead=1 / (1 + np.maximum(d.wk.fillna(52), 0) / 28), prof=d.maxrp / 5, dep=d.n_proj / mp, subst=1 - np.minimum(1, d.n_qual / 8), lead=np.minimum(1, d.lead / np.maximum(1, d.wk.fillna(52))))
    d["prio_score"] = 100 * sum(w[k] * c[k] for k in w) / sw; d.loc[d.unc <= 1e-6, "prio_score"] = d.prio_score * .2; return d.sort_values("prio_score", ascending=False).reset_index(drop=True)

# ------------------------------ build or buy ------------------------------
def bob(D, S, skill, A, plan):
    X = D["X"]; Q = A["req"]; q = Q[(Q.skill == skill) & (Q.unc > 1e-6)]
    if q.empty: return None
    R = X["R"]; H0, P, emp, avl, res = X["H0"], X["P"], X["emp"], X["avl"], A["res"]; need = float(q.unc.sum()); minrp = int(q.rp.min()); uw = sorted({w for l in R[R.rid.isin(q.rid)].w_idx for w in l}); wk_to = (q.required_by.min() - H0).days / 7
    qual = P[X["sidx"][skill]][:, uw].max(1) >= minrp if uw else np.zeros(len(emp), bool); rate_note = ""
    if qual.any(): rate = float(emp.hourly_cost.values[qual].mean())
    else: rate = float(emp.hourly_cost.mean()) * 1.3; rate_note = " (ASSUMPTION: no qualified staff, rate = 130% of average cost)"
    opts = []
    def add(nm, cover, tw, cost, internal, det, ass): opts.append(dict(option=nm, cover=min(1.0, cover / need) if need > 0 else 1.0, time_w=tw, cost=cost, internal=internal, feasible=bool(cover >= need - 1e-6 and tw <= wk_to + 1e-9), detail=det, assump=ass))
    qe = np.nonzero(qual)[0]
    if S["redeploy"] > 0 and len(qe): hrs = float(sum(emp.allocated_hours.values[e] * S["redeploy"] * sum(1 for w in uw if avl[e, w] > 0) for e in qe)); add("Redeploy qualified staff", hrs, 1, len(qe) * 8 * rate, True, "%d qualified employees; release %.0f%% of their committed hours (affects other work: needs planner authorisation)" % (len(qe), S["redeploy"] * 100), "8 h transition per employee; displaced work not priced")
    else: add("Redeploy qualified staff", 0, 1, np.nan, True, "Not authorised (release % is 0) or no qualified staff", "Existing commitments are protected by default")
    tc = train_cands(D, S, skill, minrp, res); el = tc[tc.status == "eligible"] if len(tc) else pd.DataFrame(); cap = cost = 0.0; tw = 0; nt = 0
    for c in el.itertuples():
        cp = sum(res[c.ei, w] for w in uw if w >= c.weeks) * c.success
        if cp <= 0: continue
        cap += cp; cost += c.cost + c.weeks * c.hpw * c.rate; tw = max(tw, c.weeks); nt += 1
        if cap >= need: break
    add("Train internal candidates", cap, tw if nt else np.inf, cost if nt else np.nan, True, "%d trainees (eligible pool %d); expected capacity after training scaled by course success rate" % (nt, len(el)), "Success rates are scenario assumptions; training hours priced at trainee cost")
    L = int(S["hire_lead"]); per = S["hpw"] * sum(1 for w in uw if w >= L); hr = rate * S["hire_prem"]
    if per > 0: n = math.ceil(need / per); add("Hire permanent specialist(s)", need, L, n * S["hire_fee"] * hr * 2080 + need * hr, False, "%d hire(s) starting in week %d" % (n, L), "Fee %.0f%% of annual salary; rate %s/h%s; %d h/week" % (S["hire_fee"] * 100, fx(hr), rate_note, S["hpw"]))
    else: add("Hire permanent specialist(s)", 0, L, np.nan, False, "Lead time exceeds the demand window", "Lead time %d weeks" % L)
    Lc = int(S["ctr_lead"]); per = S["hpw"] * sum(1 for w in uw if w >= Lc)
    if per > 0: n = math.ceil(need / per); add("Use contractor / temporary specialist", need, Lc, need * rate * S["ctr_prem"], False, "%d contractor(s) from week %d" % (n, Lc), "Rate %.1fx internal cost%s" % (S["ctr_prem"], rate_note))
    else: add("Use contractor / temporary specialist", 0, Lc, np.nan, False, "Lead time exceeds the demand window", "Lead time %d weeks" % Lc)
    if S["slip"] > 0: extra = float(sum(res[e, uw].mean() for e in qe)) * S["slip"] / 7 if len(qe) and uw else 0.0; add("Adjust sequencing (permit %d-day slip)" % S["slip"], extra, S["slip"] / 7, 0.0, True, "Extra qualified capacity if the deadline moves", "Needs sponsor approval")
    else: add("Adjust sequencing (not permitted)", 0, 0, np.nan, True, "Set a permitted slip above 0 days to evaluate", "Disabled by default")
    O = pd.DataFrame(opts); f = O[O.feasible].copy(); f["k"] = (~f.internal).astype(int); f = f.sort_values(["k", "cost"])
    rec = ("Recommended: %s (time %s weeks, cost %s). %s" % (f.iloc[0].option, fx(f.iloc[0].time_w), money(f.iloc[0].cost), "Internal option preferred because it meets the deadline." if f.iloc[0].internal else "No internal option meets the deadline in full.")) if len(f) else "No option fully closes the gap before the earliest critical date (%.1f weeks): consider combining options, resequencing or reducing scope." % wk_to
    return dict(need=need, minrp=minrp, wk_to=wk_to, rate=rate, opts=O, cands=tc, rec=rec, uw=uw)

# ------------------------------ scenarios ------------------------------
def run_scenario(D, S, base_plan, sc):
    D2 = dict(D); [D2.__setitem__(k, D[k].copy()) for k in ("emp", "es", "proj", "req")]; S2 = dict(S); H0 = pd.Timestamp(S["start"]); sk = sc.get("skill"); cost = 0.0; lat = 0.0; notes = []; X = D["X"]; Ab = analyze(D, S, base_plan, False); res = Ab["res"]
    rr = D["req"][D["req"].skill == sk] if sk else D["req"].iloc[0:0]; minrp = int(rr.required_proficiency.min()) if len(rr) else 3; rate = float(D["emp"].hourly_cost.mean())
    if sk and sk in X["sidx"]:
        qm = X["P"][X["sidx"][sk]][:, -1] >= minrp
        if qm.any(): rate = float(D["emp"].hourly_cost.values[qm].mean())
    if sc.get("boost", 0) > 0: S2["cap_boost"] = sc["boost"] / 100; notes.append("Available hours increased by %.0f%% for everyone (capped by the slider limit)." % sc["boost"])
    if sc.get("redeploy", 0) > 0 and sk:
        qm = X["P"][X["sidx"][sk]][:, -1] >= minrp; ids = D["emp"].employee_id[qm]; m = D2["emp"].employee_id.isin(ids); D2["emp"].loc[m, "allocated_hours"] *= 1 - sc["redeploy"] / 100
        notes.append("AUTHORISED CHANGE: released %.0f%% of existing commitments for %d employees qualified in %s (displaced work is not priced)." % (sc["redeploy"], int(m.sum()), sk)); cost += int(m.sum()) * 8 * rate
    new_e, new_s = [], []
    for i in range(int(sc.get("hire_n", 0))):
        eid = "HIRE-%d" % (i + 1); new_e.append(dict(employee_id=eid, department="New hire", current_role="Specialist", experience=np.nan, available_hours=40.0, allocated_hours=0.0, location="n/a", hourly_cost=rate * S["hire_prem"], career_interests="", available_from=H0 + pd.Timedelta(weeks=int(sc["hire_start"])), available_until=pd.NaT))
        new_s.append(dict(employee_id=eid, skill=sk, proficiency=int(sc["hire_lvl"]), last_assessed_date=H0, assessment_source="verified", confidence=1.0, effective_from=pd.NaT)); wk_act = max(0, S["weeks"] - int(sc["hire_start"])); cost += S["hire_fee"] * rate * S["hire_prem"] * 2080 + 40 * wk_act * rate * S["hire_prem"]; lat = max(lat, int(sc["hire_start"]))
    if sc.get("hire_n", 0): notes.append("%d specialist(s) hired at level %d, starting week %d (recruitment fee and salary for the horizon included in cost)." % (sc["hire_n"], sc["hire_lvl"], sc["hire_start"]))
    for i in range(int(sc.get("ctr_n", 0))):
        eid = "CTR-%d" % (i + 1); f0 = H0 + pd.Timedelta(weeks=int(sc["ctr_start"])); new_e.append(dict(employee_id=eid, department="Contractor", current_role="Contractor", experience=np.nan, available_hours=40.0, allocated_hours=0.0, location="n/a", hourly_cost=rate * S["ctr_prem"], career_interests="", available_from=f0, available_until=f0 + pd.Timedelta(weeks=int(sc["ctr_wks"]))))
        new_s.append(dict(employee_id=eid, skill=sk, proficiency=max(minrp, 3), last_assessed_date=H0, assessment_source="verified", confidence=1.0, effective_from=pd.NaT)); cost += 40 * int(sc["ctr_wks"]) * rate * S["ctr_prem"]; lat = max(lat, int(sc["ctr_start"]))
    if sc.get("ctr_n", 0): notes.append("%d contractor(s) for %d weeks from week %d at %.1fx internal rate." % (sc["ctr_n"], sc["ctr_wks"], sc["ctr_start"], S["ctr_prem"]))
    if sc.get("train_n", 0) and sk:
        tc = train_cands(D, S, sk, minrp, res); el = tc[tc.status == "eligible"].head(int(sc["train_n"])) if len(tc) else pd.DataFrame()
        if len(el):
            ok = int(round(len(el) * float(el.success.mean()))); notes.append("Training %d employees; with an average success rate of %.0f%%, %d are assumed to succeed (costs are paid for all %d)." % (len(el), 100 * el.success.mean(), ok, len(el)))
            for j, c in enumerate(el.itertuples()):
                cost += c.cost + c.weeks * c.hpw * c.rate; lat = max(lat, c.weeks)
                if j < ok: new_s.append(dict(employee_id=c.employee_id, skill=sk, proficiency=c.result, last_assessed_date=H0, assessment_source="verified", confidence=.8, effective_from=H0 + pd.Timedelta(weeks=int(c.weeks))))
        else: notes.append("No eligible training candidates found for %s." % sk)
    if new_e: D2["emp"] = pd.concat([D2["emp"], pd.DataFrame(new_e)], ignore_index=True)
    if new_s: D2["es"] = pd.concat([D2["es"], pd.DataFrame(new_s)], ignore_index=True)
    if sc.get("proj") and sc.get("shift", 0):
        m = D2["proj"].project_id == sc["proj"]; D2["proj"].loc[m, "deadline"] = D2["proj"].loc[m, "deadline"] + pd.Timedelta(days=int(sc["shift"])); m2 = D2["req"].project_id == sc["proj"]; D2["req"].loc[m2, "required_by_date"] = D2["req"].loc[m2, "required_by_date"] + pd.Timedelta(days=int(sc["shift"]))
        st = D2["proj"].loc[m, "start_date"].iloc[0] + pd.Timedelta(days=7); D2["req"].loc[m2, "required_by_date"] = D2["req"].loc[m2, "required_by_date"].clip(lower=st); notes.append("Deadline of %s moved by %+d days." % (sc["proj"], sc["shift"]))
    if sc.get("proj") and sc.get("newprio"): D2["proj"].loc[D2["proj"].project_id == sc["proj"], "priority"] = float(sc["newprio"]); notes.append("Priority of %s set to %d." % (sc["proj"], sc["newprio"]))
    D2["X"] = prepare(D2, S2)
    try: plan = solve_lp(D2["X"], S2)
    except Exception: plan = solve_greedy(D2["X"], S2, True)
    return dict(A=analyze(D2, S2, plan, False), plan=plan, cost=cost, lat=lat, notes=notes, D=D2)

# ------------------------------ compute pipeline ------------------------------
def apply_sens(D, S):
    if S.get("nosens"): D["emp"] = D["emp"].copy(); D["emp"]["location"] = "withheld"; D["emp"]["career_interests"] = ""
    return D
def compute(D, S):
    D = apply_sens(D, S); D["X"] = prepare(D, S); pb = solve_greedy(D["X"], S)
    try: po = solve_lp(D["X"], S)
    except Exception as e: po = solve_greedy(D["X"], S, True); po["method"] += " (LP unavailable: %s)" % type(e).__name__
    return D, pb, po
def get_demo():
    if not _DEMO: D, pb, po = compute(load_all(make_data(), "", DEF), DEF); _DEMO.update(D=D, pb=pb, po=po, A=analyze(D, DEF, po), Ab=analyze(D, DEF, pb, False), S=dict(DEF))
    return _DEMO
SK_KEYS = ["start", "weeks", "max_share", "allow_exc", "count_inf", "stale", "conc", "ready", "risk", "nosens", "w_hours", "w_crit", "w_dead", "w_prof", "w_dep", "w_subst", "w_lead"]
def mkS(*v):
    S = dict(DEF); d = dict(zip(SK_KEYS, v)); S["w"] = dict(hours=d.pop("w_hours"), crit=d.pop("w_crit"), dead=d.pop("w_dead"), prof=d.pop("w_prof"), dep=d.pop("w_dep"), subst=d.pop("w_subst"), lead=d.pop("w_lead"))
    S.update(d); S.update(ASSUME); S["weeks"] = int(S["weeks"]); return S
def run_all(*a):
    n = len(SK_KEYS)
    try:
        S = mkS(*a[:n]); files = a[n:n + 6]; mapping = a[n + 6]; demo = files[0] is None
        if demo: raw = make_data()
        else: raw = dict(zip(["emp", "es", "proj", "req", "trn", "skills"], [read_csv_any(f) if f is not None else None for f in files]))
        pd.Timestamp(S["start"])
        D = load_all(raw, mapping, S); D, pb, po = compute(D, S); A = analyze(D, S, po); Ab = analyze(D, S, pb, False); G.clear(); G.update(D=D, S=S, pb=pb, po=po, A=A, Ab=Ab, demo=demo)
        k = A["kpi"]; return note(("Fictional demo data analysed. " if demo else "Your data analysed. ") + "%s employees, %d projects, coverage of in-horizon demand %s. Optimiser: %s." % (nf(len(D["emp"])), len(D["proj"]), pc0(k["cov"]), esc(po["method"])), "ok")
    except Exception as e: return note("Could not complete the analysis: " + esc(e), "err")

# ------------------------------ pages ------------------------------
def banner(): return note("<b>Illustrative synthetic data.</b> Fictional employees and projects; nothing here describes a real organisation.", "warn") if G.get("demo") else ""
def render_cc():
    if "A" not in G: return (note("Load data first.", "info"),) + NOP(2)
    A, D, S = G["A"], G["D"], G["S"]; k = A["kpi"]; sk = A["skills"]; X = D["X"]; ncrit = int((sk.unc_pct >= S["crit_unc"]).sum()) if len(sk) else 0; fcap = float((X["free"] * S["max_share"]).sum())
    h = banner() + "<div class='kg'>" + card("Workforce", nf(len(D["emp"])), "employees in the dataset") + card("Projects", nf(len(D["proj"])), "%d with demand in the horizon" % int((A["proj"].status != "No demand").sum())) + card("Critical skill gaps", nf(ncrit), "skills with ≥%.0f%% of demand uncovered" % (S["crit_unc"] * 100), C["co"]) + \
        card("Projects at risk", nf(k["risk"] + k["crit"]), "%d at risk, %d critical" % (k["risk"], k["crit"]), C["am"]) + card("Skill coverage", pc0(k["cov"]), "hours covered by the optimised plan", C["mi"]) + card("Free capacity", nf(fcap) + " h", "usable hours in %d weeks (existing work protected)" % S["weeks"], C["la"]) + card("Demand in horizon", nf(k["demand"]) + " h", "requirement hours inside the planning window") + "</div>"
    h += note("Statuses are rule-based planning indicators from coverage, not calibrated probabilities of missing a deadline. Plan = %s." % esc(G["po"]["method"]), "info")
    if len(sk): h += H("Most critical skill shortages") + tbl(sk.head(6), [("skill", "Skill"), ("prio_score", "Priority"), ("unc", "Uncovered h"), ("unc_pct", "Uncovered %"), ("flags", "Gap types"), ("crit_date", "Earliest critical date")], dict(prio_score=lambda v: fx(v, 0), unc=nf, unc_pct=pc0, flags=flags_html, crit_date=dts))
    pj = A["proj"][A["proj"].status != "No demand"].sort_values("score").head(12); f1 = sty(go.Figure(go.Bar(y=pj.name, x=pj.score, orientation="h", marker_color=[STC[s] for s in pj.status], text=[fx(v, 0) for v in pj.score], textposition="outside")), 380, "Lowest readiness scores (0-100)"); f1.update_xaxes(range=[0, 105]); f1.update_yaxes(autorange="reversed")
    t = sk.head(10).iloc[::-1]; f2 = empty("No uncovered demand") if t.empty else sty(go.Figure(go.Bar(y=t.skill, x=t.unc, orientation="h", marker_color=C["co"], text=[fx(v, 0) for v in t.unc], textposition="outside")), 380, "Uncovered hours by skill (optimised plan)")
    return h, f1, f2
def render_skills(dep, skl, minp, loc, src, avail, q):
    if "D" not in G: return (note("Load data first.", "info"),) + NOP(2)
    D, X, S = G["D"], G["D"]["X"], G["S"]; emp = X["emp"].assign(free_wk=X["free"].mean(1)); es = D["es"].copy(); es["counted"] = (es.assessment_source != "inferred") | S["count_inf"]
    if dep: emp = emp[emp.department.isin(dep)]
    if loc: emp = emp[emp.location.isin(loc)]
    if avail: emp = emp[emp.free_wk >= 8]
    if q: emp = emp[emp.employee_id.str.contains(q, case=False) | emp.current_role.str.contains(q, case=False)]
    s = es[es.employee_id.isin(emp.employee_id)]
    if skl: s = s[s.skill == skl]
    if minp: s = s[s.proficiency >= minp]
    if src: s = s[s.assessment_source.isin(src)]
    if skl or minp or src: emp = emp[emp.employee_id.isin(s.employee_id)]
    a = es[es.employee_id.isin(emp.employee_id)].sort_values("proficiency", ascending=False); a = a.assign(t=a.skill + " L" + a.proficiency.astype(str) + " (" + a.assessment_source.str[:4] + ")").groupby("employee_id").t.apply(lambda x: "; ".join(list(x)[:6]))
    t = emp.assign(skills=emp.employee_id.map(a)).head(150); h = banner() + note("Showing %d of %d matching employees. Source codes: veri = verified, self = self-reported, infe = inferred (inferred skills %s). A skill on a profile is not proof of expert proficiency." % (len(t), len(emp), "count as qualified" if S["count_inf"] else "are NOT counted as qualified"), "info")
    h += tbl(t, [("employee_id", "Employee"), ("department", "Department"), ("current_role", "Role"), ("location", "Location"), ("available_hours", "Avail h/wk"), ("allocated_hours", "Allocated h/wk"), ("free_wk", "Free h/wk"), ("skills", "Skills (top 6)")], dict(available_hours=nf, allocated_hours=nf, free_wk=fx))
    sk = G["A"]["skills"]; top = list(sk.sort_values("demand", ascending=False).skill.head(14)) if len(sk) else []; m = es[(es.proficiency >= 3) & es.counted].merge(X["emp"][["employee_id", "department"]], on="employee_id"); f1 = empty("No demand data")
    if top: pv = m[m.skill.isin(top)].pivot_table(index="department", columns="skill", values="employee_id", aggfunc="count", fill_value=0).reindex(columns=top, fill_value=0); f1 = sty(go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=pv.index, colorscale=[[0, C["sf"]], [1, C["mi"]]], text=pv.values, texttemplate="%{text}", hovertemplate="%{y} / %{x}: %{z} employees at level 3+<extra></extra>")), 420, "Proficiency matrix: employees at level 3+ by department and in-demand skill")
    cn = sk.sort_values("n_expert").head(15) if len(sk) else sk; f2 = empty("No demand data") if cn.empty else go.Figure(go.Bar(x=cn.skill, y=cn.n_expert, marker_color=[C["co"] if v <= S["conc"] else C["mi"] for v in cn.n_expert]))
    if len(cn): f2 = sty(f2, 360, "Concentration: employees at level 3+ in demanded skills (coral = at or below %d)" % S["conc"]); f2.update_xaxes(tickangle=-30)
    return h, f1, f2
def render_emp(eid):
    if "D" not in G or not eid: return note("Select an employee.", "info")
    D, X, S = G["D"], G["D"]["X"], G["S"]; e = X["eidx"].get(eid)
    if e is None: return note("Employee not found.", "warn")
    r = X["emp"].iloc[e]; s = D["es"][D["es"].employee_id == eid].copy(); s["stale"] = s.last_assessed_date.map(lambda d: "stale / unknown" if is_stale(d, X["H0"], S["stale"]) else "current"); a = G["po"]["assign"]; a = a[a.ei == e]
    h = "<div class='kg'>" + card("Department", esc(r.department), esc(r.current_role)) + card("Weekly hours", "%s avail / %s allocated" % (nf(r.available_hours), nf(r.allocated_hours)), "free %s h/wk" % fx(X["free"][e].mean()), C["la"]) + card("Assigned in plan", nf(a.h.sum()) + " h", "%d requirements" % a.ri.nunique(), C["am"]) + "</div>"
    return h + tbl(s.sort_values("proficiency", ascending=False), [("skill", "Skill"), ("proficiency", "Level"), ("assessment_source", "Source"), ("confidence", "Confidence"), ("last_assessed_date", "Last assessed"), ("stale", "Assessment age")], dict(last_assessed_date=dts, confidence=lambda v: fx(v, 2)))
def render_gaps(dep):
    if "A" not in G: return (note("Load data first.", "info"),) + NOP(3)
    A, S = G["A"], G["S"]; sk = A["skills"]; Q = A["req"]
    if sk.empty: return (note("No uncovered or demanded skills.", "info"),) + NOP(3)
    h = banner() + note("<b>Gap types are distinct findings:</b> skill shortage (too few people hold the skill), proficiency shortage (not enough reach the level), headcount (qualified people lack total hours), allocation (qualified people are committed elsewhere), timing (free hours exist but not when needed), concentration risk (≤%d people at level 3+). Priority = weighted score (see Methodology). Gross qualified capacity is an upper bound because one employee can be qualified in several skills." % S["conc"], "info")
    h += tbl(sk.reset_index(), [("index", "#"), ("skill", "Skill"), ("prio_score", "Priority"), ("demand", "Required h"), ("covered", "Covered h"), ("unc", "Uncovered h"), ("unc_pct", "Uncovered %"), ("n_proj", "Projects"), ("crit_date", "Earliest critical"), ("trainable", "Trainable"), ("flags", "Gap types"), ("evidence", "Evidence")],
             dict(index=lambda v: str(int(v) + 1), prio_score=lambda v: fx(v, 0), demand=nf, covered=nf, unc=nf, unc_pct=pc0, crit_date=dts, flags=flags_html))
    t = sk.head(15).iloc[::-1]; f1 = go.Figure([go.Bar(y=t.skill, x=t.demand, orientation="h", name="Required", marker_color=C["mu"]), go.Bar(y=t.skill, x=t.gross, orientation="h", name="Qualified free capacity (upper bound)", marker_color=C["la"]), go.Bar(y=t.skill, x=t.covered, orientation="h", name="Covered by plan", marker_color=C["mi"])]); f1 = sty(f1, 520, "Required vs available hours by skill (top 15 by priority)")
    q = Q[(Q.unc > 0)].copy()
    if dep: q = q[q.dept.isin(dep)]
    f2 = empty("No uncovered demand")
    if len(q): q["m"] = q.required_by.dt.to_period("M").astype(str); top = list(q.groupby("skill").unc.sum().sort_values(ascending=False).head(15).index); pv = q[q.skill.isin(top)].pivot_table(index="skill", columns="m", values="unc", aggfunc="sum", fill_value=0).reindex(top); f2 = sty(go.Figure(go.Heatmap(z=pv.values, x=pv.columns, y=pv.index, colorscale=[[0, C["sf"]], [1, C["co"]]], hovertemplate="%{y}, due %{x}: %{z:.0f} h uncovered<extra></extra>")), 440, "Skill-gap heatmap: uncovered hours by required-by month")
    f3 = empty("No uncovered demand")
    if len(q): d = q.groupby("dept").unc.sum().sort_values(ascending=False); f3 = sty(go.Figure(go.Bar(x=d.index, y=d.values, marker_color=C["am"])), 340, "Uncovered hours by project department"); f3.update_yaxes(title="Hours")
    return h, f1, f2, f3
def render_ready():
    if "A" not in G: return note("Load data first.", "info"), empty("No data")
    A = G["A"]; p = A["proj"].copy(); pb = G["Ab"]["proj"].set_index("project_id").status; p["base"] = p.project_id.map(pb); p = p.sort_values("score", na_position="last")
    h = banner() + note("Readiness score = 100 × (0.6 × hours coverage + 0.4 × coverage of the worst requirement). Thresholds: Ready ≥ %d, At Risk ≥ %d, else Critical. 'Current allocation' is the naive first-come baseline, not actual staffing. Statuses are planning indicators, not predictions." % (G["S"]["ready"], G["S"]["risk"]), "info")
    h += tbl(p, [("project_id", "ID"), ("name", "Project"), ("prio", "Priority"), ("deadline", "Deadline"), ("demand", "Demand h"), ("coverage", "Coverage"), ("score", "Readiness"), ("base", "Current allocation"), ("status", "Proposed plan"), ("blocking", "Blocking skills"), ("conflicts", "Capacity conflicts"), ("lead_conf", "Lead-time conflicts")],
             dict(prio=lambda v: nf(v), deadline=dts, demand=nf, coverage=pc0, score=lambda v: fx(v, 0), base=pill, status=pill, blocking=lambda l: esc(", ".join(l[:3])) or "—", lead_conf=lambda l: esc("; ".join(l[:2])) or "—"))
    t = p[p.status != "No demand"]; f = sty(go.Figure(go.Bar(y=t.name, x=t.score, orientation="h", marker_color=[STC[s] for s in t.status], hovertemplate="%{y}: %{x:.0f}<extra></extra>")), max(420, 18 * len(t)), "Project readiness ranking (proposed plan)"); f.update_xaxes(range=[0, 105]); return h, f
def render_pdetail(pid):
    if "A" not in G or not pid: return note("Select a project.", "info")
    Q = G["A"]["req"]; q = Q[Q.project_id == pid]; a = G["po"]["assign"]; X = G["D"]["X"]
    if q.empty: return note("This project has no skill requirements in the horizon.", "warn")
    ids = {ri: ", ".join(X["emp"].employee_id.iloc[a[a.ri == ri].groupby("ei").h.sum().sort_values(ascending=False).head(4).index]) for ri in range(len(X["R"]))}; q = q.assign(who=[ids.get(i, "") for i in q.index])
    return H("Requirements and workforce: " + esc(q.project_name.iloc[0])) + tbl(q, [("skill", "Skill"), ("rp", "Req. level"), ("hc", "Headcount"), ("required_by", "Required by"), ("demand_h", "Demand h"), ("covered", "Covered h"), ("unc", "Uncovered h"), ("n_qual", "Qualified staff"), ("gross", "Qualified free h"), ("who", "Main assignees")], dict(required_by=dts, demand_h=nf, covered=nf, unc=nf, n_qual=nf, gross=nf))
def render_alloc(pf):
    if "A" not in G: return (note("Load data first.", "info"),) + NOP(2)
    D, S, A, Ab = G["D"], G["S"], G["A"], G["Ab"]; X = D["X"]; R = X["R"]; po = G["po"]; a = po["assign"]; kb, ko = Ab["kpi"], A["kpi"]
    cmp = pd.DataFrame([("Hours covered", nf(kb["covered"]), nf(ko["covered"])), ("Coverage of demand", pc0(kb["cov"]), pc0(ko["cov"])), ("Uncovered hours", nf(kb["unc"]), nf(ko["unc"])), ("Projects Ready / At Risk / Critical", "%d / %d / %d" % (kb["ready"], kb["risk"], kb["crit"]), "%d / %d / %d" % (ko["ready"], ko["risk"], ko["crit"])),
                        ("Employees used", nf(kb["nemp"]), nf(ko["nemp"])), ("Peak utilisation (assigned ÷ available)", pc0(kb["maxutil"]), pc0(ko["maxutil"])), ("Allocation labour cost", money(kb["cost"]), money(ko["cost"])), ("Proficiency exceptions", "0", nf(ko["nexc"]))], columns=["m", "b", "o"])
    h = banner() + note("<b>Optimiser:</b> %s. Hard constraints: no employee-week above free capacity × %.0f%% (existing commitments are protected); required proficiency (exceptions only if enabled and labelled); hours ≤ demand; hours per person ≤ demand ÷ headcount. Objective: weighted coverage by priority and urgency, close proficiency fit, lower cost, career-interest match, and a penalty on the last %.0f%% of an employee's capacity (spreads load). If demand cannot be met, it stays unresolved instead of being forced." % (esc(po["method"]), S["max_share"] * 100, (S["max_share"] - min(S["tier1"], S["max_share"])) * 100), "info")
    h += H("Baseline vs optimised plan") + tbl(cmp, [("m", "Metric"), ("b", "Baseline (first-come)"), ("o", "Optimised")]) + H("Constraint verification (re-checked on the produced plan)") + "".join(note(("PASS " if ok else "FAIL ") + esc(n) + " (" + esc(d) + ")", "ok" if ok else "err") for n, ok, d in verify_plan(X, S, po))
    g = a.groupby(["ei", "ri"]).agg(h=("h", "sum"), w0=("w", "min"), exc=("exc", "max")).reset_index() if len(a) else pd.DataFrame(columns=["ei", "ri", "h", "w0", "exc"])
    if len(g):
        r = R.iloc[g.ri.values]; g["employee"] = X["emp"].employee_id.values[g.ei.values]; g["project"] = r.project_name.values; g["pid"] = r.project_id.values; g["skill"] = r.skill.values; g["req"] = r.rp.values; g["prof"] = [int(X["P"][int(r.s.iloc[i]), g.ei.iloc[i], g.w0.iloc[i]]) for i in range(len(g))]
        g["why"] = ["Level %d vs required %d%s; %s h/wk free; priority %d project due %s%s" % (p_, q_, " (labelled exception)" if e_ else "", fx(X["free"][ei].mean()), int(pr_), dts(db_), "; career interest" if X["intr"][ei] == s_ else "") for p_, q_, e_, ei, pr_, db_, s_ in zip(g.prof, g.req, g.exc, g.ei, r.prio, r.required_by, r.s)]
        if pf: g = g[g.pid == pf]
        h += H("Recommended assignments (%d rows, largest first)" % len(g)) + tbl(g.sort_values("h", ascending=False).head(250), [("employee", "Employee"), ("project", "Project"), ("skill", "Skill"), ("h", "Hours"), ("prof", "Level"), ("req", "Required"), ("why", "Rationale")], dict(h=nf))
    un = A["req"][A["req"].unc > 8].sort_values("unc", ascending=False).head(40); h += H("Unresolved demand") + (tbl(un, [("project_name", "Project"), ("skill", "Skill"), ("rp", "Req. level"), ("required_by", "Required by"), ("unc", "Uncovered h"), ("n_qual", "Qualified staff"), ("gross", "Qualified free h")], dict(required_by=dts, unc=nf, n_qual=nf, gross=nf)) if len(un) else note("All demand is covered.", "ok"))
    pw = np.zeros((len(R), 0)); f1 = empty("No assignments")
    if len(a):
        t = a.assign(pid=R.project_id.values[a.ri.values]); top = list(t.groupby("pid").h.sum().sort_values(ascending=False).head(10).index); t["pg"] = np.where(t.pid.isin(top), t.pid, "Other"); pv = t.pivot_table(index="w", columns="pg", values="h", aggfunc="sum", fill_value=0).reindex(range(X["W"]), fill_value=0)
        f1 = go.Figure([go.Bar(x=[dts(X["ws"][i]) for i in pv.index], y=pv[c], name=c) for c in pv.columns]); f1.update_layout(barmode="stack"); f1 = sty(f1, 400, "Allocation timeline: assigned hours per week by project"); f1.update_yaxes(title="Hours / week")
    f2 = go.Figure([go.Bar(x=["Baseline", "Optimised"], y=[kb["covered"], ko["covered"]], name="Covered", marker_color=C["mi"]), go.Bar(x=["Baseline", "Optimised"], y=[kb["unc"], ko["unc"]], name="Uncovered", marker_color=C["co"])]); f2.update_layout(barmode="stack"); return h, f1, sty(f2, 340, "Hours covered vs uncovered")
def render_bob(skill, hl, hf, hp, cl, cp, rd, sl):
    if "A" not in G: return note("Load data first.", "info"), empty("No data")
    ASSUME.update(hire_lead=int(hl), hire_fee=float(hf) / 100, hire_prem=float(hp), ctr_lead=int(cl), ctr_prem=float(cp), redeploy=float(rd) / 100, slip=int(sl)); S = dict(G["S"]); S.update(ASSUME); G["S"] = S
    A = analyze(G["D"], S, G["po"], False); r = bob(G["D"], S, skill, A, G["po"]) if skill else None
    if r is None: return note("No uncovered demand for this skill under the current plan, or no skill selected.", "ok"), empty("No gap")
    O = r["opts"]; h = banner() + note("Gap: <b>%s uncovered hours</b> of %s, level %d+, earliest critical date in %.1f weeks. Average cost of qualified staff %s/h%s. All costs are incremental estimates from editable assumptions." % (nf(r["need"]), esc(skill), r["minrp"], r["wk_to"], fx(r["rate"]), esc("")), "info") + note(esc(r["rec"]), "ai")
    h += tbl(O, [("option", "Option"), ("feasible", "Closes gap in time"), ("cover", "Gap covered"), ("time_w", "Time to ready (weeks)"), ("cost", "Est. incremental cost"), ("detail", "Detail"), ("assump", "Assumptions")], dict(feasible=lambda v: pill("Yes", C["mi"]) if v else pill("No", C["co"]), cover=pc0, time_w=lambda v: "—" if nul(v) or v == np.inf else fx(v), cost=money))
    c = r["cands"]
    if len(c): h += H("Training pathways (candidates with spare capacity)") + tbl(c.head(15), [("employee_id", "Employee"), ("department", "Department"), ("level", "Current level"), ("course_id", "Course"), ("result", "Expected level"), ("weeks", "Weeks"), ("cost", "Course cost"), ("success", "Assumed success"), ("status", "Prerequisite check")], dict(cost=money, success=pc0)) + note("Trainees are not guaranteed to succeed: capacity is scaled by the course success rate. Candidates missing more than one prerequisite are excluded.", "warn")
    t = O[O.cost.notna() & np.isfinite(O.time_w)]; f = go.Figure()
    for x in t.itertuples(): f.add_trace(go.Scatter(x=[x.time_w], y=[x.cost], mode="markers+text", text=[x.option], textposition="top center", marker=dict(size=16, color=C["mi"] if x.feasible else C["co"], symbol="circle" if x.internal else "diamond"), showlegend=False))
    f = sty(f, 380, "Cost vs time to readiness (green = closes the gap in time; circle = internal)"); f.update_xaxes(title="Weeks"); f.update_yaxes(title="Estimated cost"); return h, f
def kline(A, extra=""): k = A["kpi"]; return [pc0(k["cov"]), nf(k["unc"]), "%d / %d / %d" % (k["ready"], k["risk"], k["crit"]), money(k["cost"])]
def render_scn(skill, hn, hl, hs, tn, cn, cw, cs, boost, rd, pid, shift, npri):
    if "A" not in G: return note("Load data first.", "info"), empty("No data"), empty("No data")
    sc = dict(skill=skill, hire_n=int(hn or 0), hire_lvl=int(hl or 3), hire_start=int(hs or 0), train_n=int(tn or 0), ctr_n=int(cn or 0), ctr_wks=int(cw or 4), ctr_start=int(cs or 0), boost=float(boost or 0), redeploy=float(rd or 0), proj=pid, shift=int(shift or 0), newprio=int(npri or 0))
    if not skill and (sc["hire_n"] or sc["train_n"] or sc["ctr_n"] or sc["redeploy"]): return note("Pick a target skill for hiring, training, contractor or redeployment levers.", "warn"), empty("Select a skill"), empty("Select a skill")
    try: r = run_scenario(G["D"], G["S"], G["po"], sc)
    except Exception as e: return note("Scenario failed: " + esc(e), "err"), empty("Error"), empty("Error")
    A0, A1 = G["A"], r["A"]; k0, k1 = A0["kpi"], A1["kpi"]; G["scn"] = (sc, r, k0, k1)
    rows = pd.DataFrame([("Coverage of demand", pc0(k0["cov"]), pc0(k1["cov"])), ("Uncovered hours", nf(k0["unc"]), nf(k1["unc"])), ("Projects Ready / At Risk / Critical", "%d / %d / %d" % (k0["ready"], k0["risk"], k0["crit"]), "%d / %d / %d" % (k1["ready"], k1["risk"], k1["crit"])), ("Allocation labour cost", money(k0["cost"]), money(k1["cost"])),
                         ("Incremental scenario cost (hire, train, contract)", money(0), money(r["cost"])), ("Time to readiness (latest lever start, weeks)", "—", fx(r["lat"], 0))], columns=["m", "b", "s"])
    h = banner() + note("<b>Hypothetical scenario.</b> Results are recalculated with the same optimiser and hard constraints. Training success is an assumption; hiring and contractor costs use the editable assumptions in the Build or Buy tab. Demand totals can change only if deadlines change.", "warn")
    h += H("Assumptions changed") + "<ul class='ins'>" + "".join("<li>%s</li>" % esc(n) for n in r["notes"]) + ("" if r["notes"] else "<li>No levers changed: the scenario equals the baseline.</li>") + "</ul>" + H("Impact") + tbl(rows, [("m", "Metric"), ("b", "Current optimised plan"), ("s", "Scenario")])
    d = r["A"]["proj"].set_index("project_id")[["name", "status", "score"]].join(A0["proj"].set_index("project_id")[["status", "score"]], rsuffix="_0"); ch = d[(d.status != d.status_0) | ((d.score - d.score_0).abs() > 1)].reset_index().sort_values("score", ascending=False)
    h += H("Projects whose readiness changed") + (tbl(ch.head(20), [("project_id", "ID"), ("name", "Project"), ("status_0", "Before"), ("status", "After"), ("score_0", "Score before"), ("score", "Score after")], dict(status_0=pill, status=pill, score_0=lambda v: fx(v, 0), score=lambda v: fx(v, 0))) if len(ch) else note("No project changed meaningfully.", "info"))
    f1 = go.Figure([go.Bar(x=["Current", "Scenario"], y=[k0["covered"], k1["covered"]], name="Covered", marker_color=C["mi"]), go.Bar(x=["Current", "Scenario"], y=[k0["unc"], k1["unc"]], name="Uncovered", marker_color=C["co"])]); f1.update_layout(barmode="stack"); f1 = sty(f1, 340, "Hours covered vs uncovered")
    f2 = go.Figure([go.Bar(x=["Ready", "At Risk", "Critical"], y=[k0["ready"], k0["risk"], k0["crit"]], name="Current", marker_color=C["mu"]), go.Bar(x=["Ready", "At Risk", "Critical"], y=[k1["ready"], k1["risk"], k1["crit"]], name="Scenario", marker_color=C["la"])]); f2.update_layout(barmode="group"); return h, f1, sty(f2, 340, "Projects by readiness status")

# ------------------------------ strategist ------------------------------
def find_skill(q):
    ql = q.lower()
    for k, v in sorted(G["D"]["amap"].items(), key=lambda kv: -len(kv[0])):
        if len(k) >= 2 and re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", ql): return v
    return None
def find_proj(q, skill):
    P = G["D"]["proj"]; m = re.search(r"\bP\d+\b", q, re.I)
    if m and m.group(0).upper() in set(P.project_id): return m.group(0).upper(), ""
    ql = q.lower(); best = [(sum(w in ql for w in re.findall(r"[a-z]{4,}", n.lower())), pid) for pid, n in zip(P.project_id, P.project_name)]; best.sort(reverse=True)
    if best and best[0][0] >= 2: return best[0][1], ""
    if skill:
        Q = G["A"]["req"]; q2 = Q[(Q.skill == skill)].groupby(["project_id"]).unc.sum().sort_values(ascending=False)
        if len(q2): return q2.index[0], "Interpreted as the project with the largest %s gap." % skill
    return None, ""
def t_summary():
    k = G["A"]["kpi"]; return "%s employees; %d projects; demand in horizon %s h; covered %s h (%s) by the optimised plan; projects Ready/At Risk/Critical: %d/%d/%d." % (nf(len(G["D"]["emp"])), len(G["D"]["proj"]), nf(k["demand"]), nf(k["covered"]), pc0(k["cov"]), k["ready"], k["risk"], k["crit"])
def t_top3():
    sk = G["A"]["skills"].head(3); return "Top bottlenecks by priority score: " + "; ".join("%s (score %s, %s h uncovered, %s)" % (r.skill, fx(r.prio_score, 0), nf(r.unc), ", ".join(r.flags) or "no flag") for r in sk.itertuples())
def t_why(pid, note_):
    p = G["A"]["proj"].set_index("project_id").loc[pid]; Q = G["A"]["req"]; q = Q[(Q.project_id == pid) & (Q.unc > 8)].sort_values("unc", ascending=False); sk = G["A"]["skills"].set_index("skill")
    s = "%s%s (%s): status %s, readiness %s, coverage %s. " % (note_ + " " if note_ else "", p["name"], pid, p.status, fx(p.score, 0), pc0(p.coverage))
    s += "Blocking: " + ("; ".join("%s %s h uncovered (%s)" % (r.skill, nf(r.unc), ", ".join(sk.loc[r.skill].flags) if r.skill in sk.index and len(sk.loc[r.skill].flags) else "contention") for r in q.head(4).itertuples()) if len(q) else "none material") + ". "
    return s + ("Lead-time conflicts: " + "; ".join(p.lead_conf[:2]) if p.lead_conf else "No lead-time conflicts.")
def t_trainhire(skill):
    A = G["A"]; r = bob(G["D"], G["S"], skill, A, G["po"]) if skill else None
    if r is None: return "No uncovered demand for %s under the current plan." % skill
    O = r["opts"]; return "%s gap %s h. " % (skill, nf(r["need"])) + "; ".join("%s: %s, %s weeks, cost %s, covers %s" % (x.option, "feasible" if x.feasible else "not in time/full", "—" if x.time_w == np.inf else fx(x.time_w), money(x.cost), pc0(x.cover)) for x in O.itertuples()) + ". " + r["rec"]
def t_redeploy(skill):
    X = G["D"]["X"]; s = X["sidx"].get(skill)
    if s is None: return "Skill not recognised."
    res = G["A"]["res"]; req = G["D"]["req"]; mr = int(req[req.skill == skill].required_proficiency.min()) if (req.skill == skill).any() else 3; e = np.nonzero(X["P"][s][:, -1] >= mr)[0]
    if not len(e): return "No employees at level %d+ in %s." % (mr, skill)
    d = X["emp"].iloc[e].assign(res=res[e].mean(1), lvl=X["P"][s][e, -1]).sort_values(["res", "allocated_hours"], ascending=[False, True]).head(5)
    return "Candidates at level %d+ in %s (human review and manager agreement required; check they are not already overloaded): " % (mr, skill) + "; ".join("%s (%s, level %d, free after plan %s h/wk, committed %s h/wk)" % (r.employee_id, r.department, r.lvl, fx(r.res), nf(r.allocated_hours)) for r in d.itertuples())
def t_shift(pid, wk):
    r = run_scenario(G["D"], G["S"], G["po"], dict(skill=None, proj=pid, shift=int(7 * wk))); p0 = G["A"]["proj"].set_index("project_id").loc[pid]; p1 = r["A"]["proj"].set_index("project_id").loc[pid]
    return "If %s's deadline moves by %+d days: readiness %s -> %s (status %s -> %s); overall coverage %s -> %s. (Hypothetical scenario.)" % (pid, int(7 * wk), fx(p0.score, 0), fx(p1.score, 0), p0.status, p1.status, pc0(G["A"]["kpi"]["cov"]), pc0(r["A"]["kpi"]["cov"]))
def t_limits(): return "Limitations: rule-based planning indicators, not calibrated forecasts; 'current allocation' is a naive baseline; capacity is modelled weekly with existing commitments protected; skills are as assessed (stale or self-reported skills carry uncertainty); costs and training success rates are editable assumptions; the plan supports workforce planning and needs human review. Data notes: " + " | ".join(m for _, m in G["D"]["issues"][:3])
def ask(q, use_llm=False):
    if "A" not in G: return "Load data first."
    q = (q or "").strip() or "Which three skills are creating the biggest delivery bottleneck?"; ql = q.lower(); sk = find_skill(q); pid, pn = find_proj(q, sk); parts = []
    if re.search(r"bottleneck|biggest|critical|shortage|short supply|gap", ql): parts.append(("gap_prioritisation", t_top3()))
    if pid and re.search(r"why|risk|late|delay|blocked", ql): parts.append(("project_readiness", t_why(pid, pn)))
    if sk and re.search(r"train|hire|faster|build|buy|contract", ql): parts.append(("training_vs_hiring", t_trainhire(sk)))
    if sk and re.search(r"redeploy|reassign|transfer|suitable|move", ql): parts.append(("redeployment", t_redeploy(sk)))
    m = re.search(r"(\d+|one|two|three|four|five|six)\s*weeks?", ql)
    if pid and m and re.search(r"deadline|move|forward|earlier|sooner|later|delay|push", ql):
        w = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(m.group(1)) or int(m.group(1)); parts.append(("scenario", t_shift(pid, -w if re.search(r"forward|earlier|sooner|brought|pull", ql) else w)))
    if re.search(r"limit|caveat|trust|reliab", ql): parts.append(("limitations", t_limits()))
    if not parts: parts = [("workforce_summary", t_summary()), ("gap_prioritisation", t_top3())]
    ctx = "\n".join("[%s] %s" % (n, t) for n, t in parts); out = "### Answer (deterministic, computed by analytical tools)\n" + "\n".join("- **%s**: %s" % (n, t) for n, t in parts) + "\n\n*Every figure comes from the loaded dataset. Planning indicators only; human review is required for staffing decisions.*"
    if not use_llm: return out
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k: return out + "\n\n*External LLM is disabled: no ANTHROPIC_API_KEY environment variable is set. The deterministic answer above is complete.*"
    try:
        safe = re.sub(r"\bE\d{3}\b|\bHIRE-\d+\b|\bCTR-\d+\b", "[employee]", ctx); r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-5-5", "max_tokens": 800, "system": "You are a workforce planning assistant. Answer ONLY from the TOOL RESULTS. Never invent skills, costs, dates or savings. Be concise.", "messages": [{"role": "user", "content": "TOOL RESULTS:\n" + safe + "\n\nQUESTION: " + q}]}, timeout=60); r.raise_for_status()
        return "### LLM-written answer (aggregated results only; employee IDs removed)\n" + "".join(b.get("text", "") for b in r.json().get("content", [])) + "\n\n---\n" + out
    except Exception as e: return out + "\n\n*LLM call failed (%s); deterministic answer shown.*" % type(e).__name__

# ------------------------------ exports, data page ------------------------------
FUNC = {"Redeploy qualified staff": "Resource management / line managers", "Train internal candidates": "Learning & Development", "Hire permanent specialist(s)": "Talent acquisition", "Use contractor / temporary specialist": "Procurement / vendor management"}
def action_plan(n=8):
    rows = []
    for r in G["A"]["skills"].head(n).itertuples():
        if r.unc <= 8: continue
        b = bob(G["D"], G["S"], r.skill, G["A"], G["po"])
        if b is None: continue
        O = b["opts"]; f = O[O.feasible].copy(); f["k"] = (~f.internal).astype(int); f = f.sort_values(["k", "cost"]); x = f.iloc[0] if len(f) else None
        rows.append(dict(skill=r.skill, priority=round(r.prio_score, 1), finding=", ".join(r.flags) or "uncovered demand", evidence=r.evidence, action=x.option if x is not None else "No single option closes the gap in time: combine options, resequence or reduce scope", owner=FUNC.get(x.option, "PMO / planner") if x is not None else "PMO / planner",
                         time_weeks=round(float(x.time_w), 1) if x is not None else np.nan, est_cost=round(float(x.cost), 0) if x is not None and not nul(x.cost) else np.nan, hire_fte_note=O[O.option.str.startswith("Hire")].detail.iloc[0], assumptions=x.assump if x is not None else "", kpi="Coverage of %s demand; weeks to fill; hours uncovered" % r.skill))
    return pd.DataFrame(rows)
def export_all():
    if "A" not in G: return None, note("Load data first.", "info")
    D, A, S, X = G["D"], G["A"], G["S"], G["D"]["X"]; out = []
    def w(df, fn):
        df.to_csv(fn, index=False); 
        if os.path.exists(fn): out.append(fn)
    es = D["es"].merge(X["emp"][["employee_id", "department", "current_role", "location"]], on="employee_id", how="left"); es["assessment_stale"] = es.last_assessed_date.map(lambda d: is_stale(d, X["H0"], S["stale"]))
    if S["nosens"]: es = es.drop(columns=["location"])
    w(es, "vector_skills_inventory.csv"); sk = A["skills"].copy(); sk["flags"] = sk.flags.map(lambda l: "; ".join(l)); w(sk, "vector_skill_gaps.csv"); pj = A["proj"].copy(); pj["blocking"] = pj.blocking.map(lambda l: "; ".join(l)); pj["lead_conf"] = pj.lead_conf.map(lambda l: "; ".join(l)); w(pj, "vector_project_readiness.csv")
    a = G["po"]["assign"]
    if len(a): g = a.groupby(["ei", "ri"]).h.sum().reset_index(); g["employee_id"] = X["emp"].employee_id.values[g.ei.values]; r = X["R"].iloc[g.ri.values]; g["project_id"] = r.project_id.values; g["skill"] = r.skill.values; g = g.rename(columns={"h": "hours"})[["employee_id", "project_id", "skill", "hours"]]
    else: g = pd.DataFrame(columns=["employee_id", "project_id", "skill", "hours"])
    w(g, "vector_allocations.csv"); w(A["req"][A["req"].unc > 0].drop(columns=["rid"]), "vector_unresolved_demand.csv"); rows, hire = [], []
    for r in sk.head(10).itertuples():
        b = bob(D, S, r.skill, A, G["po"])
        if b is None: continue
        c = b["cands"]
        if len(c): rows.append(c[c.status == "eligible"].head(10).drop(columns=["ei"]).assign(target_skill=r.skill))
        o = b["opts"]; h = o[o.option.str.startswith(("Hire", "Use"))]; hire += [dict(skill=r.skill, option=x.option, hours_needed=round(b["need"]), time_weeks=x.time_w, est_cost=x.cost, detail=x.detail) for x in h.itertuples()]
    w(pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), "vector_training_recommendations.csv"); w(pd.DataFrame(hire), "vector_hiring_requirements.csv")
    if "scn" in G: sc, r, k0, k1 = G["scn"]; w(pd.DataFrame([dict(metric=m, current=a_, scenario=b_) for m, a_, b_ in [("coverage", k0["cov"], k1["cov"]), ("uncovered_hours", k0["unc"], k1["unc"]), ("projects_ready", k0["ready"], k1["ready"]), ("projects_at_risk", k0["risk"], k1["risk"]), ("projects_critical", k0["crit"], k1["crit"]), ("incremental_cost", 0, r["cost"])]]), "vector_scenario_comparison.csv")
    ap = action_plan(); w(ap, "vector_action_plan.csv"); md = ["# VECTOR AI — Executive action plan", "", "_Synthetic data. Planning indicators; human review required._" if G.get("demo") else "_Planning indicators; human review required._", "", t_summary(), "", t_top3(), "", "## Actions"] + ["- **%s** (priority %s): %s. Owner: %s. Time: %s weeks. Cost: %s. Assumptions: %s. KPI: %s." % (r.skill, r.priority, r.action, r.owner, r.time_weeks, money(r.est_cost), r.assumptions, r.kpi) for r in ap.itertuples()] + ["", "## Limitations", t_limits()]
    open("vector_executive_summary.md", "w", encoding="utf-8").write("\n".join(md)); out.append("vector_executive_summary.md")
    css = "body{font-family:Inter,Arial,sans-serif;background:#151C27;color:#F2F5F7;max-width:980px;margin:30px auto;padding:0 18px}h1{color:#7BE0C3}table{border-collapse:collapse;width:100%;background:#263442}th{background:#2f4052;color:#7BE0C3;text-align:left;padding:8px}td{padding:7px 8px;border-top:1px solid #ffffff14}"
    open("vector_executive_summary.html", "w", encoding="utf-8").write("<html><head><meta charset='utf-8'><title>VECTOR AI</title><style>" + css + "</style></head><body><h1>VECTOR AI — Executive action plan</h1><p>%s</p><p>%s</p>" % (esc(t_summary()), esc(t_top3())) + tbl(ap, [("skill", "Skill"), ("priority", "Priority"), ("finding", "Finding"), ("action", "Action"), ("owner", "Owner"), ("time_weeks", "Weeks"), ("est_cost", "Cost"), ("assumptions", "Assumptions"), ("kpi", "KPI")]) + "<p>%s</p></body></html>" % esc(t_limits())); out.append("vector_executive_summary.html")
    return [f for f in out if os.path.exists(f)], note("Generated %d files from the current data and settings (reproducible with the same inputs)." % len(out), "ok")
def render_dq():
    if "D" not in G: return note("Load data first.", "info"), ""
    D, S, X = G["D"], G["S"], G["D"]["X"]; h = banner() + note("Rows kept per table: " + ", ".join("%s %s" % (k, nf(v)) for k, v in D["rows_in"].items()) + ". Excluded rows: <b>%d</b> (all listed below, nothing is dropped silently)." % len(D["excluded"]), "ok")
    h += "".join(note(esc(m), "err" if l == "error" else ("warn" if l == "warn" else "info")) for l, m in D["issues"]) or note("No validation issues.", "ok")
    if D["excluded"]: h += H("Excluded rows (first 40)") + tbl(pd.DataFrame(D["excluded"][:40], columns=["t", "r", "why"]), [("t", "Table"), ("r", "Row"), ("why", "Reason")])
    es = D["es"]; st = es.last_assessed_date.map(lambda d: is_stale(d, X["H0"], S["stale"])); cs = es.assessment_source.value_counts()
    h += H("Skill confidence") + tbl(pd.DataFrame([("Verified", cs.get("verified", 0)), ("Self-reported", cs.get("self_reported", 0)), ("Inferred (%s)" % ("counted" if S["count_inf"] else "not counted"), cs.get("inferred", 0)), ("Stale or unknown assessment (> %d months)" % S["stale"], int(st.sum()))], columns=["a", "b"]), [("a", "Skill records"), ("b", "Count")], dict(b=nf))
    return h, H("Self-test results (run at start-up)") + "".join(note(("PASS " if ok else "FAIL ") + esc(g + ": " + n) + " — " + esc(d), "ok" if ok else "err") for g, n, ok, d in TESTS)

# ------------------------------ self-tests ------------------------------
TS = dict(DEF, start="2026-01-05", weeks=4, max_share=1.0)
def mini_raw(hours=200, rb="2026-02-02", dl="2026-02-02"):
    emp = pd.DataFrame(dict(employee_id=["E1", "E2", "E3", "E4"], department=["X"] * 4, current_role=["r"] * 4, experience=[5] * 4, available_hours=[40] * 4, allocated_hours=[20, 30, 0, 20], location=["L"] * 4, hourly_cost=[50, 60, 40, 45], career_interests=[""] * 4))
    es = pd.DataFrame(dict(employee_id=["E1", "E2", "E3"], skill=["Python"] * 3, proficiency=[4, 3, 2], last_assessed_date=["2026-01-01", "2025-12-01", "2022-01-01"], assessment_source=["verified", "verified", "self_reported"], confidence=[.9, .9, .6]))
    proj = pd.DataFrame(dict(project_id=["P1", "P2"], project_name=["Alpha", "Beta"], department=["X", "X"], priority=[3, 2], start_date=["2026-01-05"] * 2, deadline=[dl, "2026-02-02"], estimated_effort=[100, 100], budget=[1e4, 1e4], status=["Active"] * 2))
    req = pd.DataFrame(dict(project_id=["P1"], skill=["Python"], required_proficiency=[3], required_hours=[hours], required_headcount=[1], required_by_date=[rb]))
    trn = pd.DataFrame(dict(course_id=["C1"], skill=["Python"], min_current=[2], result_proficiency=[3], prerequisites=[""], duration_weeks=[2], cost=[1000], hours_per_week=[6], success_rate=[1.0]))
    return dict(emp=emp, es=es, proj=proj, req=req, trn=trn, skills=None)
def mk(raw=None, S=TS):
    D, pb, po = compute(load_all(raw or mini_raw(), "", S), S); return D, pb, po, analyze(D, S, po)
def run_selftests(verbose=True):
    if TESTS: return TESTS
    T = []
    def chk(g, n, fn):
        try: ok, d = fn(); T.append((g, n, bool(ok), d))
        except Exception as e: T.append((g, n, False, type(e).__name__ + ": " + str(e)[:90]))
    def v1():
        r = mini_raw(); r["emp"] = r["emp"].drop(columns=["hourly_cost"])
        try: load_all(r, "", TS); return False, "no error"
        except ValueError as e: return "required field" in str(e), "missing required field reported with guidance"
    def v2():
        r = mini_raw(); r["emp"] = pd.concat([r["emp"], r["emp"].iloc[[0]], r["emp"].iloc[[0]].assign(employee_id="E9", allocated_hours=-5)], ignore_index=True); r["es"] = pd.concat([r["es"], pd.DataFrame(dict(employee_id=["E1", "E2"], skill=["Python", "Quantum Basketweaving"], proficiency=[7, 3], assessment_source=["verified", "verified"]))], ignore_index=True)
        r["proj"].loc[1, "deadline"] = "2025-01-01"; D = load_all(r, "", TS); iss = " ".join(m for _, m in D["issues"]); ex = {x[2] for x in D["excluded"]}
        return "Quantum Basketweaving" in set(D["skills"].canonical_name) and "invalid skill or proficiency" in ex and "invalid hours or cost" in ex and "impossible dates or missing priority" in ex and "duplicate employee_id" in ex, "duplicate id, negative hours, proficiency 7 and impossible dates excluded and logged; unknown skill kept"
    def s1():
        r = mini_raw(); r["es"] = pd.concat([r["es"], pd.DataFrame(dict(employee_id=["E4", "E4"], skill=["py", "K8s"], proficiency=[3, 3], assessment_source=["verified", "verified"]))], ignore_index=True); D = load_all(r, "", TS); s = set(D["es"][D["es"].employee_id == "E4"].skill); return s == {"Python", "Kubernetes"}, "py -> Python, K8s -> Kubernetes"
    def s2(): return is_stale("2022-01-01", pd.Timestamp("2026-01-05"), 18) and not is_stale("2025-12-01", pd.Timestamp("2026-01-05"), 18) and is_stale(np.nan, pd.Timestamp("2026-01-05"), 18), "old and unknown assessments flagged stale"
    def s3():
        r = mini_raw(); r["emp"] = r["emp"].drop(columns=["career_interests", "location", "experience"]); D, pb, po, A = mk(r); return len(D["emp"]) == 4 and A["kpi"]["demand"] > 0, "optional fields missing: analysis still runs"
    def s4():
        r = mini_raw(); r["es"].loc[2, "assessment_source"] = "inferred"; D1 = load_all(r, "", TS); D1["X"] = prepare(D1, TS); S2 = dict(TS, count_inf=True); D2 = load_all(r, "", S2); D2["X"] = prepare(D2, S2); si = D1["X"]["sidx"]["Python"]; return D1["X"]["P"][si, 2, 0] == 0 and D2["X"]["P"][si, 2, 0] == 2, "inferred skill ignored by default, counted only when enabled"
    def g1():
        D, pb, po, A = mk(); q = A["req"].iloc[0]; sk = A["skills"].iloc[0]; return abs(q.demand_h - 200) < 1e-6 and abs(q.covered - 120) < 1e-3 and abs(sk.unc - 80) < 1e-3, "demand 200, qualified free 120, uncovered %.1f" % sk.unc
    def g2():
        r = mini_raw(); r["req"] = pd.concat([r["req"], r["req"].assign(project_id="P2", required_hours=100)], ignore_index=True); D, pb, po, A = mk(r); cov, load = plan_stats(D["X"], po); return cov.sum() <= 120 + 1e-3 and cov.sum() >= 119.9 and all(c[1] for c in verify_plan(D["X"], TS, po)), "two projects share 120 qualified hours: assigned %.1f, capacity never counted twice" % cov.sum()
    def g3():
        r = mini_raw(hours=300); D, pb, po, A = mk(r); f = A["skills"].iloc[0].flags; return "Allocation shortage" in f, "qualified staff have hours in principle (320) but only 120 are free: %s" % f
    def g4():
        d = get_demo(); sk = d["A"]["skills"]; return len(sk) > 0 and sk.prio_score.between(0, 100).all() and sk.prio_score.is_monotonic_decreasing, "%d skills scored 0-100 and ranked" % len(sk)
    def r1(): return status_of(95, DEF) == "Ready" and status_of(80, DEF) == "At Risk" and status_of(50, DEF) == "Critical", "thresholds 90 / 70 classify correctly"
    def r2():
        D, pb, po, A = mk(); p = A["proj"].set_index("project_id").loc["P2"]; return p.status == "No demand" and pd.isna(p.coverage), "project without demand has no coverage (not zero)"
    def r3():
        D, pb, po, A = mk(mini_raw(hours=100, rb="2026-01-12", dl="2026-01-12")); p = A["proj"].set_index("project_id").loc["P1"]; return len(p.lead_conf) >= 1, "deadline in 1 week is earlier than any training/hiring lead time: %s" % (p.lead_conf[:1],)
    def a1():
        d = get_demo(); c = verify_plan(d["D"]["X"], d["S"], d["po"]); return all(x[1] for x in c), "; ".join("%s=%s" % (x[0][:28], "ok" if x[1] else "FAIL") for x in c)
    def a2():
        r = mini_raw(); r["req"].loc[0, "skill"] = "Kubernetes"; D, pb, po, A = mk(r); return len(po["assign"]) == 0 and abs(A["req"].unc.iloc[0] - 200) < 1e-6, "nobody holds the skill: nothing assigned, 200 h reported unresolved"
    def a3():
        d = get_demo(); R = d["D"]["X"]["R"]; wt = lambda p: float((R["prio"].values[p["assign"].ri.values] ** 1.5 * p["assign"].h.values).sum()); return wt(d["po"]) >= .98 * wt(d["pb"]), "priority-weighted hours: optimised %.0f vs baseline %.0f" % (wt(d["po"]), wt(d["pb"]))
    def a4():
        S2 = dict(TS, allow_exc=True); D, pb, po, A = mk(mini_raw(hours=400), S2); a = po["assign"]; ex = a[a.exc == 1]; return len(ex) > 0 and set(D["X"]["emp"].employee_id.values[ex.ei.values]) == {"E3"} and all(c[1] for c in verify_plan(D["X"], S2, po)), "level-2 employee used only as a labelled exception (%.0f h)" % ex.h.sum()
    def t1():
        D, pb, po, A = mk(mini_raw(hours=150)); b = bob(D, TS, "Python", A, po); o = b["opts"].set_index("option"); return o.loc["Train internal candidates"].feasible and "Train" in b["rec"], b["rec"][:90]
    def t2():
        D, pb, po, A = mk(mini_raw(hours=100, rb="2026-01-12", dl="2026-01-12")); b = bob(D, TS, "Python", A, po); o = b["opts"].set_index("option"); return not o.loc["Train internal candidates"].feasible and "Train" not in b["rec"].split("(")[0], "course (2 wk) finishes after the 1-week deadline: not recommended"
    def t3():
        D, pb, po, A = mk(mini_raw(hours=150)); b = bob(D, TS, "Python", A, po); o = b["opts"]; return bool(o[o.option.str.startswith("Hire")].feasible.iloc[0] is not None) and not b["rec"].startswith("Recommended: Hire"), "hiring is shown but the feasible internal option is preferred"
    def t4():
        r = mini_raw(hours=150); r["trn"]["success_rate"] = .5; D, pb, po, A = mk(r); o = bob(D, TS, "Python", A, po)["opts"].set_index("option").loc["Train internal candidates"]; return abs(o.cover - 1.0) < 1e-6 or o.cover <= 1.0, "training capacity is scaled by the 50% success assumption (coverage %.0f%%)" % (100 * o.cover)
    def c1():
        D, pb, po, A = mk(); r = run_scenario(D, TS, po, dict(skill=None)); return abs(r["A"]["kpi"]["cov"] - A["kpi"]["cov"]) < 1e-9, "no levers: scenario equals baseline"
    def c2():
        D, pb, po, A = mk(); r = run_scenario(D, TS, po, dict(skill="Python", ctr_n=1, ctr_wks=4, ctr_start=0)); return r["A"]["kpi"]["cov"] > A["kpi"]["cov"] + .01 and abs(r["A"]["kpi"]["cov"] - 1.0) < 1e-3 and r["cost"] > 0, "one contractor lifts coverage %.0f%% -> %.0f%% at cost %s" % (100 * A["kpi"]["cov"], 100 * r["A"]["kpi"]["cov"], money(r["cost"]))
    def c3():
        D, pb, po, A = mk(); a = [run_scenario(D, TS, po, dict(skill="Python", ctr_n=n, ctr_wks=4, ctr_start=0))["A"]["kpi"]["cov"] for n in (0, 1, 2)]; return a[0] <= a[1] + 1e-9 <= a[2] + 2e-9, "coverage is non-decreasing with more contractors: %s" % [round(x, 3) for x in a]
    def c4():
        D, pb, po, A = mk(); r = run_scenario(D, TS, po, dict(skill="Python", hire_n=1, hire_lvl=3, hire_start=1)); return abs(r["A"]["kpi"]["demand"] - A["kpi"]["demand"]) < 1e-6, "hiring changes supply, not demand totals"
    def x1():
        d = get_demo(); saved = dict(G); G.clear(); G.update(D=d["D"], S=d["S"], A=d["A"], Ab=d["Ab"], po=d["po"], pb=d["pb"], demo=True)
        try: files, _ = export_all(); n = len(pd.read_csv("vector_skill_gaps.csv")); ok = "vector_allocations.csv" in files and n == len(d["A"]["skills"])
        finally: G.clear(); G.update(saved)
        return ok, "%d files written; gap export has %d rows matching the analysis" % (len(files), n)
    def x2():
        d = get_demo(); S2 = dict(d["S"], nosens=True); D = apply_sens(dict(d["D"]), S2); return (D["emp"].location == "withheld").all() and (D["emp"].career_interests == "").all(), "sensitive fields withheld when the option is on"
    for g, n, f in [("validation", "missing required field", v1), ("validation", "invalid, duplicate and unknown data", v2), ("skills", "alias normalisation", s1), ("skills", "stale assessment detection", s2), ("skills", "missing optional fields", s3), ("skills", "inferred skills not treated as qualified", s4),
                    ("gaps", "demand and available hours", g1), ("gaps", "duplicate capacity prevention", g2), ("gaps", "gap type classification", g3), ("gaps", "priority score", g4), ("readiness", "threshold logic", r1), ("readiness", "zero project demand", r2), ("readiness", "deadline earlier than lead time", r3),
                    ("allocation", "constraints verified on demo plan", a1), ("allocation", "infeasible requirement", a2), ("allocation", "optimiser vs baseline", a3), ("allocation", "labelled proficiency exception", a4), ("training", "internal training preferred when feasible", t1), ("training", "deadline earlier than training", t2),
                    ("training", "hiring not automatic", t3), ("training", "success is an assumption", t4), ("scenario", "no levers equals baseline", c1), ("scenario", "contractor adds coverage", c2), ("scenario", "monotone in added capacity", c3), ("scenario", "demand unchanged by supply levers", c4),
                    ("exports", "CSV export consistency", x1), ("exports", "sensitive-field exclusion", x2)]: chk(g, n, f)
    TESTS[:] = T
    if verbose:
        for g, n, ok, d in T: print(("PASS " if ok else "FAIL ") + g + ": " + n + " :: " + d)
        print("Result: %d of %d self-tests passed." % (sum(1 for t in T if t[2]), len(T)))
    return TESTS

# ------------------------------ project export ------------------------------
METH = """### Methodology
- **Capacity:** free hours per employee-week = (available hours x (1 + boost) - already allocated hours), zero outside availability dates. Existing commitments are protected; only free hours can be assigned, up to the usable share you set.
- **Demand:** each requirement spreads its hours across the weeks between project start and required-by date; only the part inside the planning horizon is counted.
- **Qualification:** level 0-5 at or above the requirement; inferred skills are not counted unless enabled; trained skills count only after course completion. Stale or self-reported skills are flagged, not trusted blindly.
- **Optimiser:** linear program (SciPy HiGHS) over employee x requirement x week hours. Constraints: capacity, demand, hours per person <= demand / headcount, proficiency (labelled exceptions only if enabled). Objective: priority and urgency weighted coverage, close fit, lower cost, interest match, spread-load penalty. Baseline: first-come greedy. Plans are re-verified after solving.
- **Gap types:** skill, proficiency, headcount, allocation, timing, concentration (see Demand and Gap Radar).
- **Priority score:** weighted blend of uncovered hours, project criticality, deadline proximity, required level, dependent projects, scarcity of substitutes and lead time (weights editable, normalised).
- **Readiness:** 100 x (0.6 x hours coverage + 0.4 x worst requirement coverage); thresholds configurable. A planning indicator, not a forecast.
- **Build or buy:** redeploy, train, hire, contract, resequence, each with explicit time and incremental cost assumptions; internal options that meet the deadline are preferred.
- **Trust:** the tool supports planning and does not replace managerial judgement. Demographics are never used; location and interests can be withheld. Review recommendations with managers before any staffing or hiring decision.
"""
DICT = "# Data dictionary\nemployees: employee_id, department, current_role, experience, available_hours (weekly), allocated_hours (weekly), location, hourly_cost, career_interests, available_from, available_until.\nemployee_skills: employee_id, skill, proficiency (0-5), last_assessed_date, assessment_source (verified/self_reported/inferred), confidence, effective_from.\nprojects: project_id, project_name, department, priority (1-5), start_date, deadline, estimated_effort, budget, status.\nproject_requirements: project_id, skill, required_proficiency, required_hours, required_headcount, required_by_date.\ntraining_catalog: course_id, skill, min_current, result_proficiency, prerequisites (Skill:level;...), duration_weeks, cost, hours_per_week, success_rate.\nskills (optional): canonical_name, category, prerequisites, aliases.\nAll sample files are synthetic and fictional.\n"
LIMITS = "# Limitations\nRule-based planning indicators, not calibrated forecasts. The first-come baseline is not actual staffing. Capacity is weekly and aggregate; real calendars, leave and context switching are not modelled. Skill data may be stale or self-reported. Costs and training success are assumptions. The plan needs human review before any staffing or hiring decision.\n"
RAI = "# Responsible AI\nEmployee data is confidential. No demographic attributes are used. Inferred skills are not treated as verified. Every assignment is explained. Load is spread to avoid overloading the same people. Location and career interests can be excluded. External LLM use is off by default and only aggregated results (employee IDs removed) would be sent. Recommendations require human review.\n"
OPT = "# Optimisation constraints\n1. employee-week hours <= free capacity x usable share (existing commitments protected)\n2. hours per requirement <= its demand in the horizon\n3. hours per person per requirement <= demand / headcount\n4. required proficiency met (labelled one-level exceptions only if enabled)\n5. only qualified weeks count (trained skills after completion)\nUnsatisfiable demand is reported as unresolved, never forced.\n"
LICENSE = "MIT License\n\nCopyright (c) 2026 VECTOR AI contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n"
README = """# VECTOR AI — Workforce Capability & Skills Intelligence
The right skills. At the right time.

## Business problem
Organisations can have enough people overall and still miss deadlines because the right skills are not available at the right time. VECTOR AI links employee skills, availability and workload to project requirements, deadlines and training lead times, finds critical gaps and compares ways to close them. Bundled data is **fictional synthetic data**.

## Features
Skills inventory with verified / self-reported / inferred distinction, demand vs supply with six distinct gap types, editable priority score, project readiness, constrained allocation optimiser with baseline comparison and constraint verification, build-or-buy comparison (redeploy, train, hire, contract, resequence), scenario lab, deterministic strategist (optional LLM), CSV exports and executive action plan.

## Architecture
@@@mermaid
flowchart LR
  A[CSV upload or synthetic data] --> B[Validation + skill normalisation]
  B --> C[Capacity and demand model]
  C --> D[LP optimiser + baseline]
  D --> E[Gap analysis + priority score]
  D --> F[Project readiness]
  E --> G[Build or buy planner]
  G --> H[Scenario lab]
  E --> I[Strategist tools]
  F --> I
  H --> I
  I --> J[Gradio UI, exports, reports]
@@@

## Run
@@@
pip install -r requirements.txt
python app.py
@@@
Google Colab: paste `app.py` into one cell and run it. `src/` modules from the master brief are consolidated into `app.py` (sections: validation, analytics, optimiser, planner, scenarios, strategist, reporting).

## Data, methodology, constraints
See `docs/data_dictionary.md`, `docs/methodology.md`, `docs/optimization_constraints.md`. Column mapping: enter `field=your_column` pairs in the Reports & Data tab.

## LLM
Off by default. Set `ANTHROPIC_API_KEY` (see `.env.example`) and tick the option; only aggregated results with employee IDs removed are sent.

## Tests
@@@
pip install pytest
pytest tests
@@@

## Responsible AI and limitations
See `docs/responsible_ai.md` and `docs/limitations.md`. Planning support only: human review is required before any staffing or hiring decision. Add screenshots to `screenshots/`.
""".replace("@@@", "`" * 3)
TFILE = "from app import run_selftests\n\n\ndef test_%s():\n    res = [r for r in run_selftests(verbose=False) if r[0] in %s]\n    assert res and all(r[2] for r in res), res\n"
def _src():
    try: return open(__file__, encoding="utf-8").read()
    except Exception: pass
    try:
        for s in list(get_ipython().user_ns.get("In") or [])[::-1]:
            if "VECTOR AI — Workforce Capability" in s and "def main" in s: return s
    except Exception: pass
    return None
def write_samples():
    raw = make_data(); os.makedirs("sample_data", exist_ok=True); names = dict(emp="employees", es="employee_skills", proj="projects", req="project_requirements", trn="training_catalog", skills="skills"); out = []
    for k, n in names.items(): p = "sample_data/%s.csv" % n; raw[k].to_csv(p, index=False); out.append(p)
    return out
def build_project(files):
    root = "vector-ai-workforce-intelligence"
    for d in ["sample_data", "tests", "docs", "screenshots"]: os.makedirs(os.path.join(root, d), exist_ok=True)
    src = _src()
    if src: open(root + "/app.py", "w", encoding="utf-8").write(src)
    for f in files: open(os.path.join(root, f), "wb").write(open(f, "rb").read())
    W = {"requirements.txt": "gradio>=4.44,<6\nplotly\nscipy\nrequests\npandas\nnumpy\n", "README.md": README, "LICENSE": LICENSE, ".env.example": "# Optional. Leave empty to keep the external LLM disabled.\nANTHROPIC_API_KEY=\n", ".gitignore": ".env\n*.key\nsecrets*\n__pycache__/\n.ipynb_checkpoints/\n*.zip\nvector_*.csv\nvector_*.md\nvector_*.html\n",
         "docs/methodology.md": METH, "docs/data_dictionary.md": DICT, "docs/optimization_constraints.md": OPT, "docs/responsible_ai.md": RAI, "docs/limitations.md": LIMITS, "screenshots/README.md": "# Screenshots\nAdd your own screenshots of the running app here. None are included.\n",
         "tests/test_data_validation.py": TFILE % ("data_validation", "('validation', 'exports')"), "tests/test_skill_analytics.py": TFILE % ("skill_analytics", "('skills',)"), "tests/test_gap_prioritization.py": TFILE % ("gap_prioritization", "('gaps',)"), "tests/test_project_readiness.py": TFILE % ("project_readiness", "('readiness',)"),
         "tests/test_allocation_optimizer.py": TFILE % ("allocation_optimizer", "('allocation',)"), "tests/test_training_hiring_planner.py": TFILE % ("training_hiring_planner", "('training',)"), "tests/test_scenario_simulator.py": TFILE % ("scenario_simulator", "('scenario',)")}
    for fn, tx in W.items(): open(os.path.join(root, fn), "w", encoding="utf-8").write(tx)
    z = "vector_ai_project.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fs in os.walk(root):
            for f in fs: zf.write(os.path.join(dp, f))
    return z, bool(src)

# ------------------------------ UI ------------------------------
CSS = """
.gradio-container{background:#151C27!important;color:#F2F5F7!important;font-family:Inter,system-ui,-apple-system,sans-serif!important;max-width:1360px!important}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:14px;padding:26px 30px;border-radius:14px;background:#263442;border:1px solid #ffffff1a;border-left:4px solid #7BE0C3;margin-bottom:12px}
.brand{display:flex;gap:16px;align-items:center}.logo{width:50px;height:50px;border-radius:10px;border:2px solid #7BE0C3;color:#7BE0C3;font-weight:800;font-size:22px;display:flex;align-items:center;justify-content:center}
.hdr h1{margin:0;font-size:30px;letter-spacing:3px;color:#F2F5F7}.hdr h1 span{color:#7BE0C3}.hdr .sub{color:#D3B5FF;font-size:13px;letter-spacing:2px;text-transform:uppercase}.hdr p{margin:6px 0 0;color:#A7B5C5;font-size:15px;font-style:italic}
.badges span{display:inline-block;margin:3px;padding:4px 11px;border-radius:6px;background:#ffffff0d;border:1px solid #ffffff1a;color:#A7B5C5;font-size:12px}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:10px 0}.kc{background:#263442;border:1px solid #ffffff14;border-radius:10px;padding:14px 16px}
.kl{color:#A7B5C5;font-size:11px;text-transform:uppercase;letter-spacing:1.2px}.kv{font-size:24px;font-weight:700;margin:6px 0 4px}.kd{color:#A7B5C5;font-size:12px}
.note{background:#263442;padding:10px 14px;border-radius:8px;margin:8px 0;color:#F2F5F7;font-size:14px;line-height:1.5}.sec{font-size:15px;font-weight:700;color:#D3B5FF;margin:18px 0 6px;text-transform:uppercase;letter-spacing:1px}
.ins{background:#263442;border-radius:8px;padding:12px 12px 12px 30px;font-size:14px;line-height:1.6}.pill{display:inline-block;border:1px solid;border-radius:99px;padding:1px 9px;font-size:11px;font-weight:600;margin:1px;white-space:nowrap}
.tw{overflow-x:auto;border-radius:8px;border:1px solid #ffffff14;margin:8px 0}table{border-collapse:collapse;width:100%;background:#263442;font-size:13px}th{background:#2f4052;color:#7BE0C3;text-align:left;padding:9px 10px;font-weight:600}
td{padding:8px 10px;border-top:1px solid #ffffff10;color:#F2F5F7;vertical-align:top}tr:hover td{background:#7BE0C30d}button.primary{background:#7BE0C3!important;color:#151C27!important;border:none!important;font-weight:700!important}
@media(max-width:640px){.hdr h1{font-size:22px}.kv{font-size:20px}.hdr{padding:18px}}
"""
HEADER = ("<div class='hdr'><div class='brand'><div class='logo'>VX</div><div><h1>VECTOR <span>AI</span></h1><div class='sub'>Workforce Capability &amp; Skills Intelligence</div><p>The right skills. At the right time.</p></div></div>"
          "<div class='badges'><span>Planning indicators, not forecasts</span><span>Human review required</span><span>Core analytics need no API key</span></div></div>")
def refresh():
    if "D" not in G: return tuple(gr.update() for _ in range(9))
    D = G["D"]; deps = sorted(D["emp"].department.unique().tolist()); locs = sorted(D["emp"].location.unique().tolist()); sks = sorted(D["skills"].canonical_name.tolist()); ids = D["emp"].employee_id.tolist()[:400]; pj = [(p + " · " + n, p) for p, n in zip(D["proj"].project_id, D["proj"].project_name)]
    top = G["A"]["skills"].skill.iloc[0] if len(G["A"]["skills"]) else None
    return (gr.update(choices=deps, value=[]), gr.update(choices=locs, value=[]), gr.update(choices=sks, value=None), gr.update(choices=ids, value=ids[0]), gr.update(choices=deps, value=[]), gr.update(choices=pj, value=pj[0][1]), gr.update(choices=[("All projects", "")] + pj, value=""), gr.update(choices=sks, value=top), gr.update(choices=sks, value=top))
def build_ui(zip_path, sfiles):
    with gr.Blocks(css=CSS, title="VECTOR AI", theme=gr.themes.Base(primary_hue="teal", neutral_hue="slate")) as demo:
        gr.HTML(HEADER)
        with gr.Accordion("Planning settings (press Recalculate after changing)", open=False):
            with gr.Row():
                g_start = gr.Textbox("2026-11-02", label="Planning start (YYYY-MM-DD, use a Monday)"); g_weeks = gr.Slider(4, 26, 12, step=1, label="Planning horizon (weeks)"); g_ms = gr.Slider(.5, 1, .9, step=.05, label="Usable share of free hours")
            with gr.Row():
                g_exc = gr.Checkbox(False, label="Allow one-level proficiency exceptions (labelled)"); g_inf = gr.Checkbox(False, label="Count inferred skills as qualified"); g_nosens = gr.Checkbox(False, label="Exclude sensitive fields (location, career interests)")
            with gr.Row():
                g_stale = gr.Slider(6, 48, 18, step=1, label="Stale assessment after (months)"); g_conc = gr.Slider(1, 6, 3, step=1, label="Concentration risk: at most N experts"); g_ready = gr.Slider(60, 100, 90, step=1, label="Ready if score ≥"); g_risk = gr.Slider(30, 95, 70, step=1, label="At Risk if score ≥")
            gr.Markdown("**Priority-score weights** (normalised automatically)")
            with gr.Row():
                w1 = gr.Slider(0, 1, .25, step=.05, label="Uncovered hours"); w2 = gr.Slider(0, 1, .15, step=.05, label="Project criticality"); w3 = gr.Slider(0, 1, .15, step=.05, label="Deadline proximity"); w4 = gr.Slider(0, 1, .10, step=.05, label="Required proficiency")
                w5 = gr.Slider(0, 1, .10, step=.05, label="Dependent projects"); w6 = gr.Slider(0, 1, .15, step=.05, label="Scarcity of substitutes"); w7 = gr.Slider(0, 1, .10, step=.05, label="Train/hire lead time")
            run_btn = gr.Button("Recalculate", variant="primary")
        status = gr.HTML(note("Loading the fictional demo workforce and solving the allocation (about 30-60 seconds)...", "info"))
        SETIN = [g_start, g_weeks, g_ms, g_exc, g_inf, g_stale, g_conc, g_ready, g_risk, g_nosens, w1, w2, w3, w4, w5, w6, w7]
        with gr.Tabs():
            with gr.Tab("01 Command Centre"):
                cc_h = gr.HTML()
                with gr.Row():
                    cc1 = gr.Plot(); cc2 = gr.Plot()
            with gr.Tab("02 Skills Intelligence"):
                with gr.Row():
                    sk_dep = gr.Dropdown([], multiselect=True, label="Department"); sk_loc = gr.Dropdown([], multiselect=True, label="Location"); sk_sk = gr.Dropdown([], label="Skill"); sk_min = gr.Slider(0, 5, 0, step=1, label="Min proficiency")
                with gr.Row():
                    sk_src = gr.CheckboxGroup(["verified", "self_reported", "inferred"], label="Assessment source"); sk_av = gr.Checkbox(False, label="Only employees with 8+ free h/wk"); sk_q = gr.Textbox(label="Search employee ID or role"); sk_btn = gr.Button("Apply filters", variant="primary")
                sk_h = gr.HTML()
                with gr.Row():
                    sk1 = gr.Plot(); sk2 = gr.Plot()
                sk_emp = gr.Dropdown([], label="Employee detail", allow_custom_value=True); sk_eh = gr.HTML()
            with gr.Tab("03 Demand & Gap Radar"):
                with gr.Row():
                    gp_dep = gr.Dropdown([], multiselect=True, label="Filter heatmap by project department"); gp_btn = gr.Button("Update", variant="primary")
                gp_h = gr.HTML(); gp1 = gr.Plot(); gp2 = gr.Plot(); gp3 = gr.Plot()
            with gr.Tab("04 Project Readiness"):
                rd_h = gr.HTML(); rd_f = gr.Plot(); rd_pick = gr.Dropdown([], label="Project detail"); rd_d = gr.HTML()
            with gr.Tab("05 Allocation Studio"):
                with gr.Row():
                    al_pf = gr.Dropdown([], label="Show assignments for project"); al_btn = gr.Button("Update", variant="primary")
                al_h = gr.HTML()
                with gr.Row():
                    al1 = gr.Plot(); al2 = gr.Plot()
            with gr.Tab("06 Build or Buy"):
                with gr.Row():
                    bb_sk = gr.Dropdown([], label="Skill gap to analyse"); bb_btn = gr.Button("Compare options", variant="primary")
                with gr.Row():
                    b_hl = gr.Slider(2, 26, 10, step=1, label="Hiring lead time (weeks)"); b_hf = gr.Slider(0, 40, 20, step=1, label="Recruitment fee (% of annual salary)"); b_hp = gr.Slider(.8, 1.5, 1.15, step=.05, label="New-hire cost vs internal")
                with gr.Row():
                    b_cl = gr.Slider(1, 12, 2, step=1, label="Contractor lead time (weeks)"); b_cp = gr.Slider(1, 3, 1.6, step=.1, label="Contractor rate vs internal"); b_rd = gr.Slider(0, 50, 0, step=5, label="Authorise releasing % of committed hours (redeploy)"); b_sl = gr.Slider(0, 60, 0, step=7, label="Permitted deadline slip (days)")
                bb_h = gr.HTML(); bb_f = gr.Plot()
            with gr.Tab("07 Scenario Lab"):
                gr.Markdown("What-if levers recalculate the full optimisation. All results are **hypothetical**; training success is an assumption.")
                with gr.Row():
                    sc_sk = gr.Dropdown([], label="Target skill (for hire / train / contract / redeploy)"); sc_hn = gr.Number(0, label="Specialists to hire"); sc_hl = gr.Slider(1, 5, 4, step=1, label="Hire proficiency level"); sc_hs = gr.Slider(0, 20, 10, step=1, label="Hire start (week)")
                with gr.Row():
                    sc_tn = gr.Number(0, label="Employees to train"); sc_cn = gr.Number(0, label="Contractors"); sc_cw = gr.Slider(1, 26, 8, step=1, label="Contractor weeks"); sc_cs = gr.Slider(0, 20, 2, step=1, label="Contractor start (week)")
                with gr.Row():
                    sc_bo = gr.Slider(0, 25, 0, step=1, label="Extra available hours (%, limit 25)"); sc_rd = gr.Slider(0, 50, 0, step=5, label="Release % of committed hours for qualified staff"); sc_pj = gr.Dropdown([], label="Project for deadline / priority change"); sc_sh = gr.Slider(-60, 60, 0, step=7, label="Deadline shift (days, negative = earlier)"); sc_np = gr.Slider(0, 5, 0, step=1, label="New priority (0 = unchanged)")
                sc_btn = gr.Button("Run scenario", variant="primary"); sc_h = gr.HTML()
                with gr.Row():
                    sc1 = gr.Plot(); sc2 = gr.Plot()
            with gr.Tab("08 Reports & Data"):
                gr.Markdown("Upload CSVs (employees, employee skills, projects, requirements and training are required together; skills dictionary optional). Leave empty to use the fictional demo. Download the samples as templates.")
                with gr.Row():
                    f1 = gr.File(label="employees.csv", file_types=[".csv"]); f2 = gr.File(label="employee_skills.csv", file_types=[".csv"]); f3 = gr.File(label="projects.csv", file_types=[".csv"])
                with gr.Row():
                    f4 = gr.File(label="project_requirements.csv", file_types=[".csv"]); f5 = gr.File(label="training_catalog.csv", file_types=[".csv"]); f6 = gr.File(label="skills.csv (optional)", file_types=[".csv"])
                mp = gr.Textbox(label="Column mapping (only if auto-detect fails)", placeholder="employee_id=emp_no, available_hours=weekly_hours, skill=skill_name", lines=2); ld_btn = gr.Button("Validate and load uploaded data", variant="primary")
                gr.File(value=sfiles, label="Sample CSV templates (synthetic)", file_count="multiple", interactive=False); dq_h = gr.HTML()
                gr.Markdown("### Exports"); ex_btn = gr.Button("Generate exports and executive action plan", variant="primary"); ex_msg = gr.HTML(); ex_files = gr.File(label="Exports", file_count="multiple", interactive=False)
                gr.File(value=zip_path, label="Download GitHub-ready project (ZIP)", interactive=False)
            with gr.Tab("09 Methodology & Trust"):
                tt_h = gr.HTML(); gr.Markdown(METH); gr.Markdown(RAI)
            with gr.Tab("VECTOR Strategist"):
                gr.Markdown("Answers come from analytical tools over the current plan. Try: *Why is the data engineering project at risk?* · *Which three skills are creating the biggest bottleneck?* · *Would training or hiring close the Kubernetes gap faster?* · *What changes if P16's deadline moves forward by two weeks?* · *Which employees are suitable for redeployment in Cybersecurity?*")
                ag_q = gr.Textbox(label="Ask a question"); ag_llm = gr.Checkbox(False, label="Use external LLM (disabled by default; sends only aggregated results with employee IDs removed; requires ANTHROPIC_API_KEY in the environment; check your privacy policy first)"); ag_btn = gr.Button("Ask", variant="primary"); ag_out = gr.Markdown()
        FILES = [f1, f2, f3, f4, f5, f6]; RUN = SETIN + FILES + [mp]; SKIN = [sk_dep, sk_sk, sk_min, sk_loc, sk_src, sk_av, sk_q]; BBIN = [bb_sk, b_hl, b_hf, b_hp, b_cl, b_cp, b_rd, b_sl]; SCIN = [sc_sk, sc_hn, sc_hl, sc_hs, sc_tn, sc_cn, sc_cw, sc_cs, sc_bo, sc_rd, sc_pj, sc_sh, sc_np]
        def chain(ev):
            e = ev.then(refresh, None, [sk_dep, sk_loc, sk_sk, sk_emp, gp_dep, rd_pick, al_pf, bb_sk, sc_sk]).then(render_cc, None, [cc_h, cc1, cc2]).then(render_skills, SKIN, [sk_h, sk1, sk2]).then(render_emp, sk_emp, sk_eh).then(render_gaps, gp_dep, [gp_h, gp1, gp2, gp3])
            e = e.then(render_ready, None, [rd_h, rd_f]).then(render_pdetail, rd_pick, rd_d).then(render_alloc, al_pf, [al_h, al1, al2]).then(render_bob, BBIN, [bb_h, bb_f]); return e.then(render_dq, None, [dq_h, tt_h])
        chain(run_btn.click(run_all, RUN, [status], show_progress="full")); chain(ld_btn.click(run_all, RUN, [status], show_progress="full")); chain(demo.load(run_all, RUN, [status]))
        sk_btn.click(render_skills, SKIN, [sk_h, sk1, sk2]); sk_emp.change(render_emp, sk_emp, sk_eh); gp_btn.click(render_gaps, gp_dep, [gp_h, gp1, gp2, gp3]); rd_pick.change(render_pdetail, rd_pick, rd_d); al_btn.click(render_alloc, al_pf, [al_h, al1, al2])
        bb_btn.click(render_bob, BBIN, [bb_h, bb_f], show_progress="full"); sc_btn.click(render_scn, SCIN, [sc_h, sc1, sc2], show_progress="full"); ex_btn.click(export_all, None, [ex_files, ex_msg], show_progress="full")
        ag_btn.click(ask, [ag_q, ag_llm], ag_out, show_progress="full"); ag_q.submit(ask, [ag_q, ag_llm], ag_out)
    return demo
def main():
    sf = write_samples(); zp, saved = build_project(sf)
    print("=" * 78); print("VECTOR AI starting. Demo data is FICTIONAL. Core analytics need no API key."); print("Solving the demo allocation and running self-tests (about 30-60 seconds):")
    run_selftests(verbose=True); demo = build_ui(zp, sf)
    print("Project ZIP:", zp, "| standalone app.py included:", "yes" if saved else "NO (create app.py yourself by pasting this cell into it)")
    print("Files: sample_data/*.csv, %s. Not tested here: uploads with your own CSVs, the optional external LLM. The public Gradio link is open to anyone: do not load real employee data unless access is restricted." % zp)
    print("=" * 78); demo.queue().launch(debug=False, show_error=True)
if __name__ == "__main__" or "google.colab" in sys.modules:
    main()