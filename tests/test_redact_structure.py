"""Structure + accuracy tests for the redacted payload, on messy resume layouts.

    .venv/bin/python -m pytest tests/test_redact_structure.py -q
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shortlister.redact import redact, to_items, to_roles, to_skill_list  # noqa: E402

TODAY = date(2026, 11, 20)


def red(text: str, mode: str = "full"):
    return redact("R-TEST", text, today=TODAY, mode=mode)


BULLETS = """Priya Menon
priya.menon@gmail.com | +91 90000 12345 | Kochi
Experience
Senior Product Manager at Zomato | Jan 2021 - Present
• Led the checkout squad of 8 engineers and designers
• Raised conversion by 12% through
  an A/B tested redesign
- Owned the pricing roadmap
Product Analyst, Razorpay, Bengaluru
Jun 2018 - Dec 2020
* Built SQL dashboards used by 40 people
Skills
Languages: Python, SQL | Tools: Mixpanel, JIRA, A/B testing, CI/CD
Certifications
• CSPO (Scrum Alliance)
• Google Analytics
Projects
• Budgeting app: 2k users
"""


def test_roles_are_separate_entries_with_clean_fields():
    p, _ = red(BULLETS)
    roles = p["experience"]["roles"]
    assert [r["title"] for r in roles] == ["Senior Product Manager", "Product Analyst"]
    assert [r["company"] for r in roles] == ["Zomato", "Razorpay"]  # trailing city dropped, not kept
    assert roles[0]["years"] == 5.9 and roles[1]["years"] == 2.6
    assert p["experience"]["total_years"] == 8.5


def test_bullets_cleaned_and_wrapped_lines_rejoined():
    p, _ = red(BULLETS)
    hl = p["experience"]["roles"][0]["highlights"]
    assert hl == ["Led the checkout squad of 8 engineers and designers",
                  "Raised conversion by 12% through an A/B tested redesign",
                  "Owned the pricing roadmap"]
    assert p["certifications"] == ["CSPO (Scrum Alliance)", "Google Analytics"]
    assert p["projects"] == [{"name": None, "highlights": ["Budgeting app: 2k users"]}]


def test_skills_flattened_and_slash_terms_kept():
    p, _ = red(BULLETS)
    assert p["skills"] == ["Python", "SQL", "Mixpanel", "JIRA", "A/B testing", "CI/CD"]
    assert to_skill_list("Java, java, SQL;  Java") == ["Java", "SQL"]  # deduped, case-insensitive
    assert to_skill_list(None) == []


def test_date_range_on_own_line_and_leading_dates():
    roles = to_roles("Account Manager, Acme\n(2.0 years)\nHandled 30 accounts.\n(1.5 years) Intern at Beta\nFiled reports.")
    assert {k: roles[0][k] for k in ("title", "company", "years", "highlights")} == {
        "title": "Account Manager", "company": "Acme", "years": 2.0, "highlights": ["Handled 30 accounts."]}
    assert (roles[1]["title"], roles[1]["company"], roles[1]["years"]) == ("Intern", "Beta", 1.5)


def test_undated_experience_is_kept_not_dropped():
    p, a = red("Rahul Jain\nExperience\nWorked on payments APIs.\nMentored two interns.\nSkills\nJava")
    roles = p["experience"]["roles"]
    assert len(roles) == 1 and roles[0]["years"] is None
    assert roles[0]["highlights"] == ["Worked on payments APIs.", "Mentored two interns."]
    assert p["experience"]["total_years"] is None and not a["needs_human_review"]


def test_role_boundaries_survive_with_no_blank_lines():
    """Regression: the date regex used to swallow the newline, gluing roles together."""
    p, _ = red("A B\nExperience\nEngineer, Foo Mar 2020 - Mar 2022\nDid X.\nManager, Bar Apr 2022 - Present\nDid Y.")
    assert [r["title"] for r in p["experience"]["roles"]] == ["Engineer", "Manager"]
    assert p["experience"]["roles"][0]["highlights"] == ["Did X."]


def test_empty_sections_are_empty_lists_and_review_flag():
    p, a = red("Just A Name\nHobbies\nChess")
    assert p["skills"] == [] and p["projects"] == [] and p["experience"]["roles"] == []
    assert a["needs_human_review"] is True


def test_sentence_case_after_pronoun_swap():
    p, _ = red("Asha Rao\nSummary\nPM with 3 years. She led onboarding. He and she shipped it.\nSkills\nSQL")
    assert p["summary"].startswith("PM with 3 years. The candidate led onboarding.")
    assert "the candidate and the candidate" in p["summary"] or "The candidate and" in p["summary"]


def test_education_fields_from_abbreviations():
    p, _ = red("A B\nExperience\nX, Y Jan 2020 - Jan 2021\nEducation\nB.Com, Some College 2015\nMCA, Other Institute 2017\nBBA 2012")
    fields = {(d["level"], d["field"]) for d in p["education"]["degrees"]}
    assert ("Bachelors", "commerce") in fields and ("Masters", "computer applications") in fields
    assert ("Bachelors", "business") in fields


def test_structuring_never_reintroduces_redacted_details():
    """Names, contact, city, college, gender words must not appear anywhere in the JSON."""
    text = BULLETS + "\nEducation\nB.Tech, Government College of Engineering Kochi 2014 - 2018\n"
    blob = json.dumps(red(text)[0]).lower()
    for leaked in ["priya", "menon", "@gmail", "90000", "kochi", "bengaluru", "government college"]:
        assert leaked not in blob, leaked
    blob2 = json.dumps(red("Ananya Rao\nSummary\nShe is a mother of two, female, Hindu, aged 34.\nSkills\nSQL")[0]).lower()
    for leaked in ["mother", "female", "hindu", "aged 34", " she "]:
        assert leaked not in blob2, leaked


def test_to_items_basics():
    assert to_items("• a\n• b") == ["a", "b"]
    assert to_items("1. one\n2) two") == ["one", "two"]
    assert to_items("") == [] and to_items(None) == []


# A fictional resume in the common Indian PM layout: heading with a duration, several
# roles under one company line, Company – Title internships, education bullets and an
# "Additional information" block. (Regression for a real resume that lost its main section.)
GROUPED = """Kavya Iyer
kavya.iyer@gmail.com | +91-9000011111 | LinkedIn: kavya-iyer
PROFESSIONAL EXPERIENCE 3 years 2 months
Paylater (formerly QuickCredit) Pune, India
Product Manager Apr 2025 – Present
Owning onboarding and AI support products
• Generated 10K leads/month with an LLM assistant, from 100K conversations/month at
21% monthly retention, by building a bureau-report explainer
• Cut support tickets by 30% at ~4,000 queries/day
Associate Product Manager Oct 2023 – Mar 2025
• Raised disbursal rate by 2% by redesigning the journey around the drop-off points found
through funnel analysis
Product Intern Apr 2023 – Jun 2023
• Gamified the credit score module; earned a pre-placement offer
PROJECTS
Newsbot – An AI agent for daily news briefs | Read on Medium Independent
• Attracted 3,000+ visitors
Habit app | Personal
• 500 users on Play Store
INTERNSHIPS
Cars24 – Market Research Intern Jan 2023 – Mar 2023
• Built the Ahmedabad go-to-market plan from 300 surveys
Campus Club – Co-Founder Apr 2021 – May 2022
• Grew a community to 1,000+ members
EDUCATION
IIM Ahmedabad Ahmedabad, India
Post Graduate Diploma in Management, Marketing 2021 – 2023
• National Semifinalist, Flipkart Wired 7.0
Nirma University Ahmedabad, India
Bachelor of Technology, Information and Communication Technology 2017 – 2021
ADDITIONAL INFORMATION
Skills: SQL, Excel, Mixpanel, A/B testing
Interests: Carnatic music, temple choir
"""


def test_heading_with_duration_is_not_dropped():
    p, a = red(GROUPED)
    assert "experience" in a["sections_found"] and a["header_lines_dropped"] == 2 and not a["warnings"]
    assert [r["title"] for r in p["experience"]["roles"]][:3] == [
        "Product Manager", "Associate Product Manager", "Product Intern"]


def test_roles_under_one_company_line_inherit_it():
    roles = red(GROUPED)[0]["experience"]["roles"]
    assert {r["company"] for r in roles[:3]} == {"Paylater (formerly QuickCredit)"}
    assert roles[0]["highlights"][0] == "Owning onboarding and AI support products"
    assert roles[0]["highlights"][1].endswith("at 21% monthly retention, by building a bureau-report explainer")
    assert len(roles[0]["highlights"]) == 3 and len(roles[1]["highlights"]) == 1


def test_company_dash_title_order_and_internship_years():
    p, _ = red(GROUPED)
    interns = [r for r in p["experience"]["roles"] if r["internship"]]
    assert [(r["title"], r["company"]) for r in interns] == [
        ("Product Intern", "Paylater (formerly QuickCredit)"),
        ("Market Research Intern", "Cars24"), ("Co-Founder", "Campus Club")]
    # Apr 2025-Nov 2026 and Oct 2023-Mar 2025 only: internships are not counted as work.
    assert p["experience"]["total_years"] == 3.2
    assert p["experience"]["internship_years"] is not None


def test_additional_information_and_education_bullets():
    p, _ = red(GROUPED)
    assert p["skills"] == ["SQL", "Excel", "Mixpanel", "A/B testing"]
    assert p["achievements"] == ["National Semifinalist, Flipkart Wired 7.0"]
    assert {(d["level"], d["field"]) for d in p["education"]["degrees"]} == {
        ("Masters", "marketing"), ("Bachelors", "information and communication technology")}
    blob = json.dumps(p).lower()
    for leaked in ["kavya", "iyer", "carnatic", "temple", "iim", "nirma", "ahmedabad", "pune", "9000011111"]:
        assert leaked not in blob, leaked


def test_projects_grouped_with_their_bullets():
    assert red(GROUPED)[0]["projects"] == [
        {"name": "Newsbot – An AI agent for daily news briefs | Read on Medium Independent",
         "highlights": ["Attracted 3,000+ visitors"]},
        {"name": "Habit app | Personal", "highlights": ["500 users on Play Store"]}]


def test_unknown_caps_heading_is_dropped_and_reported():
    p, a = red("A B\nSKILLS\nSQL\nVOLUNTEER WORK\nTaught at a temple school\nEDUCATION\nB.Tech 2015")
    assert "temple" not in json.dumps(p) and any("Volunteer Work" in w for w in a["warnings"])


def test_all_caps_name_is_still_scrubbed():
    p, _ = red("RAVI KUMAR\nravi@x.com\nSUMMARY\nRavi Kumar is a PM.\nSkills\nSQL")
    assert "ravi" not in json.dumps(p).lower()


# ------------------------------------------------------------------ name-only mode (default)
def test_name_only_hides_name_and_contact_but_keeps_the_rest():
    p, a = red(GROUPED, mode="name")
    blob = json.dumps(p, ensure_ascii=False)
    for hidden in ["Kavya", "Iyer", "kavya.iyer", "9000011111", "kavya-iyer"]:
        assert hidden.lower() not in blob.lower(), hidden
    for kept in ["IIM Ahmedabad", "Nirma University", "Carnatic music", "Apr 2025 – Present", "Ahmedabad"]:
        assert kept in blob, kept
    assert a["mode"] == "name"


def test_name_only_roles_keep_dates_and_split_location():
    roles = red(GROUPED, mode="name")[0]["experience"]["roles"]
    assert roles[0]["company"] == "Paylater (formerly QuickCredit)" and roles[0]["location"] == "Pune, India"
    assert roles[0]["dates"] == "Apr 2025 – Present" and roles[1]["dates"] == "Oct 2023 – Mar 2025"


def test_name_only_keeps_career_break_but_not_in_totals():
    text = ("Asha Rao\nExperience\nPM, Foo Jan 2022 - Dec 2022\nCareer break (maternity) Jan 2023 - Dec 2023\n"
            "PM, Bar Jan 2024 - Dec 2024\nSkills\nSQL")
    p, _ = red(text, mode="name")
    roles = p["experience"]["roles"]
    assert [r.get("career_break", False) for r in roles] == [False, True, False]
    assert p["experience"]["total_years"] == 2.0
    assert "Asha" not in json.dumps(p)


def test_name_only_keeps_personal_and_other_sections():
    p, _ = red("Ravi Kumar\nravi@x.com | Lucknow\nSkills\nSQL\nPersonal Details\nGender: Male\nHobbies\nCricket", mode="name")
    assert p["header"] == ["Lucknow"]
    assert p["other"] == ["Gender: Male", "Cricket"]
    assert "ravi" not in json.dumps(p).lower()


def test_name_only_warns_when_name_not_found():
    _, a = red("Experience\nPM, Foo Jan 2022 - Dec 2022", mode="name")
    assert any("name" in w for w in a["warnings"])
