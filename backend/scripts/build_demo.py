"""Rebuild a clearly labelled fictional fixture. No external AI calls are made."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schemas import SkillAssessment, AnalysisResponse
from services.scoring import calculate_scores

sample_skills = [
    ('Python', 'Programming Languages', 'required', 'Python for customer analytics and automated reporting.'),
    ('SQL', 'Databases', 'required', 'SQL queries to combine customer and sales data.'),
    ('Data cleaning', 'Data Analysis', 'required', 'Data cleaning and validation for weekly reports.'),
    ('Data visualization', 'Data Analysis', 'required', 'Data visualization in Tableau for stakeholder reporting.'),
    ('Communication', 'Soft Skills', 'required', 'Communication of findings to product and business stakeholders.'),
    ('Power BI', 'Tools', 'required', ''),
    ('Excel', 'Tools', 'preferred', 'Excel pivot tables and lookup functions.'),
    ('Git', 'Tools', 'preferred', ''),
    ('dbt', 'Tools', 'preferred', '')
]
skills = [SkillAssessment(name=name, category=category, priority=priority,
    status='matched' if evidence else 'missing', evidence=evidence,
    job_evidence=('Required skills: Python, SQL, data cleaning, data visualization, communication, and Power BI.' if priority=='required' else 'Preferred skills: Excel, Git, and dbt.'))
    for name, category, priority, evidence in sample_skills]
data = {
  'job_title':'Data Analyst',
  'enriched_description':'A Data Analyst role focused on preparing reliable datasets, interpreting performance trends, building dashboards, and communicating business insights. Python, SQL, data cleaning, data visualization, communication, and Power BI are required. Excel, Git, and dbt are preferred.',
  'scores':calculate_scores(skills,81.6).model_dump(),
  'skills':[skill.model_dump() for skill in skills],
  'profile':{'name':'Alex Morgan','headline':'Data Analyst · Turning business questions into clear insights','summary':'An early-career data analyst with experience in Python, SQL, Tableau, and Excel. Skilled in preparing reliable datasets, exploring customer behavior, and communicating findings to business teams.'},
  'education':[{'title':'BSc in Statistics','subtitle':'Example University · 2021–2025','detail':'Coursework in statistical modeling, database systems, and business analytics.','evidence':'BSc in Statistics, Example University, 2021–2025.'}],
  'experience':[{'title':'Data Analyst Intern','subtitle':'Example Analytics Studio · 2024–2025','detail':'Prepared customer and sales datasets, built Tableau dashboards, and shared weekly insights with product stakeholders.','evidence':'Data Analyst Intern, Example Analytics Studio. Built Tableau dashboards and automated weekly reporting using Python and SQL.'}],
  'achievements':[{'title':'Analytics showcase finalist','subtitle':'University project showcase · 2024','detail':'Presented a customer-retention analysis and dashboard to an academic review panel.','evidence':'Finalist, university analytics project showcase, 2024.'}],
  'recommendations':{
    'narrative':'Your Python, SQL, and analysis experience give you a solid foundation for this role. The clearest opportunity is to demonstrate the same dashboard skills in Power BI. Start there, then make your workflow easier to reproduce with Git and build familiarity with dbt. A focused, end-to-end portfolio project can connect all three.',
    'strengths':['Python and SQL for analytical workflows','Clear data visualization and stakeholder communication'],
    'action_plan':[
      {'skill':'Power BI','priority':'high','horizon':'Weeks 1–2','action':'Rebuild a Tableau project in Power BI. Practice relationships, measures, and interactive filters around a business question.','deliverable':'A sales dashboard with a data model and a short insights summary.'},
      {'skill':'Git','priority':'medium','horizon':'Week 3','action':'Track your project with Git. Use clear commits and a README explaining the data, approach, and results.','deliverable':'A versioned repository that someone else can follow.'},
      {'skill':'dbt','priority':'low','horizon':'Week 4','action':'Turn your SQL transformations into dbt models. Add basic data quality tests and document the model dependencies.','deliverable':'A small, tested transformation project feeding your dashboard.'}],
    'related_roles':[
      {'title':'Business Intelligence Analyst','reason':'Your dashboard and stakeholder communication experience supports a reporting-focused path.'},
      {'title':'Product Data Analyst','reason':'Your customer analytics experience can translate into product behavior and engagement analysis.'},
      {'title':'Reporting Analyst','reason':'Your Python, SQL, and Excel skills provide a foundation for reliable business reporting.'}]},
  'notes':['This sample uses fictional resume information and precomputed values. It is not the result of an AI call or a live MiniLM comparison.'],
  'metadata':{'mode':'demo','filename':'Alex-Morgan-Example.pdf','pages':1,'elapsed_ms':0,'analyzed_at':datetime.now(timezone.utc).isoformat(),'gemini_model':'sample-only','embedding_model':'sample-only'}
}
validated = AnalysisResponse.model_validate(data)
(ROOT/'data').mkdir(exist_ok=True)
(ROOT/'data'/'demo.json').write_text(validated.model_dump_json(indent=2),encoding='utf-8')
print('Created the fictional demo fixture.')
