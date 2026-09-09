"""Local, explicit adapters. No implicit downloads, label-derived prompts or pickles."""
from __future__ import annotations

import ast
import csv
import gzip
import json
import random
import re
from pathlib import Path

from .config import Dataset, digest
from .models import Case, Evidence


TASKS = {
    "department_guide": ("Which department should receive this patient?", "clinical_department"),
    "preliminary_diagnosis": ("What preliminary diagnoses are supported by the available evidence?", "preliminary_diagnosis"),
    "diagnostic_basis": ("Identify the observations and inferences supporting the leading diagnosis.", "diagnostic_basis"),
    "differential_diagnosis": ("Give a differential diagnosis, including evidence for and against alternatives.", "differential_diagnosis"),
    "final_diagnosis": ("Determine the principal diagnosis using the available case evidence.", "principal_diagnosis"),
    "treatment_principle": ("State the treatment principles supported by the available case evidence.", "therapeutic_principle"),
    "treatment_plan": ("Propose a treatment plan justified by the available case evidence.", "treatment_plan"),
    "imaging_diagnosis": ("Interpret the available imaging findings.", "imaging_impressions"),
}


def read_records(path: Path):
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq
        for batch in pq.ParquetFile(path).iter_batches():
            yield from batch.to_pylist()
        return
    opener = gzip.open if path.suffix == ".gz" else open
    suffix = path.with_suffix("").suffix if path.suffix == ".gz" else path.suffix
    with opener(path, "rt", encoding="utf-8") as f:
        if suffix == ".csv":
            yield from csv.DictReader(f)
        elif suffix == ".jsonl":
            for line in f:
                if line.strip():
                    yield json.loads(line)
        elif suffix == ".json":
            data = json.load(f)  # Do not silently repair escapes or malformed releases.
            if isinstance(data, list):
                yield from data
            elif isinstance(data, dict) and "clinical_case_uid" in data:
                yield data
            else:
                raise ValueError("Expected a JSON array or one ClinicalBench record")
        else:
            raise ValueError("Use JSON, JSONL, CSV(.gz), or Parquet; executable pickle is not an import format")


def reports(value):
    if isinstance(value, dict):
        yield from value.items()
    elif isinstance(value, list):
        for i, row in enumerate(value):
            if not isinstance(row, dict):
                raise ValueError("Report entries must be objects")
            yield str(row.get("name", i)), row
    elif value not in (None, ""):
        raise ValueError("Report field must be an object or array")


def clinical(row, cfg):
    if cfg.task not in TASKS:
        raise ValueError(f"Unknown ClinicalBench task: {cfg.task}")
    if cfg.task == "imaging_diagnosis" and cfg.clinical_include_impressions:
        raise ValueError("Imaging impressions are this task's gold, never its input")
    uid = str(row.get("clinical_case_uid") or row["id"])
    ev = []
    summary = str(row.get("clinical_case_summary") or "")
    truncated = False
    if cfg.clinical_summary_stop:
        parts = re.split(re.escape(cfg.clinical_summary_stop), summary, maxsplit=1, flags=re.I)
        summary, truncated = parts[0], len(parts) == 2
    if summary.strip():
        ev.append(Evidence(id="history-exam", text=summary.strip(), category="history",
                           source_field="clinical_case_summary"))
    impressions = {}
    for field, category in (("imageological_examination", "imaging"), ("laboratory_examination", "laboratory")):
        for i, (name, report) in enumerate(reports(row.get(field))):
            if not isinstance(report, dict):
                raise ValueError(f"{field}/{name}: expected an object")
            text = report.get("findings") or report.get("result")
            # Never fall back to an abnormal-only summary: it drops pertinent negatives.
            if not text and report:
                raise ValueError(f"{field}/{name}: missing findings/result; review source schema")
            if report.get("impression"):
                impressions[f"{field}/{name}"] = report["impression"]
                if cfg.clinical_include_impressions:
                    text += "\nImpression: " + report["impression"]
            if text:
                ev.append(Evidence(id=f"{category}-{i}", text=f"{name}\n{text}", category=category,
                                   source_field=f"{field}/{name}"))
    path = row.get("pathological_examination")
    if path and str(path).strip().lower().rstrip(".") not in {"none", "n/a", "not available"}:
        ev.append(Evidence(id="pathology", text=str(path), category="pathology", source_field="pathological_examination"))
    question, key = TASKS[cfg.task]
    gold = impressions if key == "imaging_impressions" else row.get(key)
    if gold in (None, "", {}, []):
        raise ValueError(f"ClinicalBench {uid}: missing ground truth for {cfg.task}")
    return Case(id=uid, question=question, evidence=ev,
                reference={"answer": gold, "task": cfg.task, "impressions": impressions},
                metadata={"adapter": "clinicalbench", "summary_cut_at_marker": truncated,
                          "review_required": "Audit summary cutoff, report completeness and answer leakage before experiments"})


def ddxplus(row, cfg, dictionary, index):
    if cfg.task != "final_diagnosis":
        raise ValueError("DDxPlus adapter currently supports final_diagnosis")
    values = row["EVIDENCES"]
    values = ast.literal_eval(values) if isinstance(values, str) else values
    ev = [Evidence(id="demographics", text=f"Age: {row['AGE']}. Sex: {row['SEX']}.",
                   category="history", source_field="AGE,SEX")]
    for i, code in enumerate(values):
        name, _, value = code.partition("_@_")
        info = dictionary[name]
        if value:
            meaning = info.get("value_meaning", {}).get(value, {})
            answer = meaning.get("en", value)
        else:
            answer = "Yes"
        ev.append(Evidence(id=f"evidence-{i}", text=f"{info['question_en']} Answer: {answer}.",
                           category="history" if info["is_antecedent"] else "symptoms",
                           source_field=f"EVIDENCES/{code}"))
    dd = row.get("DIFFERENTIAL_DIAGNOSIS", [])
    dd = ast.literal_eval(dd) if isinstance(dd, str) else dd
    return Case(id=str(row.get("id", index)), question="Determine the principal diagnosis.", evidence=ev,
                reference={"answer": row["PATHOLOGY"], "accepted_answers": [row["PATHOLOGY"]], "differential": dd},
                metadata={"adapter": "ddxplus", "synthetic": True,
                          "missing_evidence_policy": "unobserved; no invented negative findings"})


def medcase(row, cfg):
    if cfg.task != "final_diagnosis":
        raise ValueError("MedCaseReasoning adapter currently supports final_diagnosis")
    # Full article, title and diagnostic_reasoning often reveal the answer.
    return Case(id=str(row["pmcid"]), question="Determine the principal diagnosis.",
                evidence=[Evidence(id="presentation", text=row["case_prompt"], category="presentation", source_field="case_prompt")],
                reference={"answer": row["final_diagnosis"], "diagnostic_reasoning": row["diagnostic_reasoning"]},
                metadata={"adapter": "medcasereasoning", "pmcid": row["pmcid"],
                          "source_url": row.get("article_link"), "partition_review_required": True})


def load_cases(cfg: Dataset) -> list[Case]:
    dictionary = json.loads(cfg.resolve_path("evidence_dictionary").read_text()) if cfg.evidence_dictionary else {}
    selected = []
    rng = random.Random(cfg.selection_seed)
    # Reservoir sampling avoids holding a million DDxPlus patients in memory.
    wanted = set(cfg.case_ids) if cfg.case_ids is not None else None
    seen_ids = set()
    for i, row in enumerate(read_records(cfg.resolve_path())):
        if cfg.adapter == "canonical":
            case = Case.model_validate(row)
        elif cfg.adapter == "clinicalbench":
            case = clinical(row, cfg)
        elif cfg.adapter == "ddxplus":
            if not dictionary:
                raise ValueError("DDxPlus requires evidence_dictionary")
            case = ddxplus(row, cfg, dictionary, i)
        else:
            case = medcase(row, cfg)
        if case.id in seen_ids:
            raise ValueError(f"Duplicate case ID: {case.id}")
        seen_ids.add(case.id)
        if wanted is not None:
            if case.id in wanted:
                selected.append(case)
        elif cfg.limit is None or len(selected) < cfg.limit:
            selected.append(case)
        else:
            j = rng.randrange(i + 1)
            if j < cfg.limit:
                selected[j] = case
    if wanted is not None:
        if wanted - {x.id for x in selected}:
            raise ValueError(f"Missing selected case IDs: {wanted - {x.id for x in selected}}")
        selected.sort(key=lambda c: cfg.case_ids.index(c.id))
        if cfg.limit and cfg.limit < len(selected):
            raise ValueError("case_ids and limit conflict; list the exact intended cohort")
    else:
        selected.sort(key=lambda c: c.id)
    if not selected:
        raise ValueError("Empty cohort")
    return selected


def allocate(case, agents, context):
    ids = [a.id for a in agents]
    if context.distribution == "shared":
        return {a: [x.id for x in case.evidence] for a in ids}
    if context.distribution == "round_robin":
        return {a: [x.id for i,x in enumerate(case.evidence) if i % len(ids) == k] for k,a in enumerate(ids)}
    key = (lambda e: e.category) if context.distribution == "by_category" else (lambda e: e.id)
    present = {key(e) for e in case.evidence}
    selectors = {v for vs in context.assignments.values() for v in vs}
    if context.distribution == "explicit" and selectors - present:
        raise ValueError(f"Assignment references absent evidence: {selectors - present}")
    if present - selectors:
        raise ValueError(f"Unassigned evidence would be silently lost: {present - selectors}")
    return {a: [e.id for e in case.evidence if key(e) in context.assignments[a]] for a in ids}
