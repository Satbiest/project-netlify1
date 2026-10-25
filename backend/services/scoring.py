"""Ground skill matches in source quotes; compute transparent, reproducible scores."""
import re
import unicodedata
from schemas import Coverage, ParsedContext, Scores, SkillAssessment


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip().casefold()


def quote_exists(quote: str, source: str) -> bool:
    return len(quote.strip()) >= 3 and normalize(quote) in normalize(source)


def assess_skills(context: ParsedContext, resume: str, job: str) -> tuple[list[SkillAssessment], list[str]]:
    skills: dict[str, SkillAssessment] = {}
    rejected = 0
    for requirement in context.requirements:
        if not quote_exists(requirement.job_evidence, job):
            rejected += 1
            continue
        matched = quote_exists(requirement.resume_evidence, resume)
        key = normalize(requirement.name)
        row = SkillAssessment(name=requirement.name, category=requirement.category,
            priority=requirement.priority, status='matched' if matched else 'missing',
            evidence=requirement.resume_evidence if matched else '', job_evidence=requirement.job_evidence)
        existing = skills.get(key)
        if existing:
            # Do not double-count a skill that appears as both required and preferred.
            row.priority = 'required' if 'required' in {existing.priority, row.priority} else 'preferred'
            if existing.status == 'matched' and row.status != 'matched':
                row.status, row.evidence = existing.status, existing.evidence
        skills[key] = row
    notes = []
    if rejected:
        notes.append('Requirements without a verifiable quote in your job description were excluded from skill coverage.')
    if not skills:
        notes.append('No explicit, source-backed skill requirements were found. Skill coverage is unavailable; the overall score uses semantic similarity only.')
    return list(skills.values()), notes


def calculate_scores(skills: list[SkillAssessment], semantic: float) -> Scores:
    def coverage(priority: str) -> Coverage:
        group = [skill for skill in skills if skill.priority == priority]
        matched = sum(skill.status == 'matched' for skill in group)
        return Coverage(score=round(matched / len(group) * 100, 2) if group else None,
                        matched=matched, total=len(group))
    required, preferred = coverage('required'), coverage('preferred')
    semantic = round(max(0.0, min(100.0, semantic)), 2)
    components = {'required': (required.score, .5), 'preferred': (preferred.score, .2), 'semantic': (semantic, .3)}
    active = {key: (value, weight) for key, (value, weight) in components.items() if value is not None}
    denominator = sum(weight for _, weight in active.values())
    weights = {key: weight / denominator for key, (_, weight) in active.items()}
    total = sum(value * weights[key] for key, (value, _) in active.items())
    return Scores(total=round(total, 2), required=required, preferred=preferred,
                  semantic=semantic, weights=weights)

