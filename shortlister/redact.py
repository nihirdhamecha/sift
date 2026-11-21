"""Turn raw resume text into structured JSON for Jev.

Two redaction modes (env BLINDFOLD_REDACTION, or the `mode` argument):

* "name" (default): only the candidate's name is hidden, plus email, phone and profile
  links (they contain or lead to the name). Everything else, including city, college,
  dates, gender and personal details, is sent as written.
* "full": the original blind mode described below.

Full mode has two layers of protection:
1. Section allowlist: only Summary, Experience, Skills, Projects, Certifications,
   Achievements and Education (degree level only) are copied. The header
   (name, contact, address, photo text) and sections like Personal Details,
   Hobbies, Languages and Declaration are never copied.
2. Text scrubbing inside the kept sections: names, contact details, gendered
   words, age, institutions, cities and calendar years are removed. Date
   ranges become durations, so career gaps are not visible.

The output schema is fixed (see `redact`). Anything not in it never reaches Jev.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import date

REDACTION_MODE = os.environ.get("BLINDFOLD_REDACTION", "name").strip().lower()
NAME_ONLY_PATTERNS = {"email", "url", "phone"}  # these contain or lead to the name

# ---------------------------------------------------------------- sections
SECTION_ALIASES = {
    "summary": ["summary", "profile", "professional summary", "about me", "objective",
                "career objective", "profile summary"],
    "experience": ["experience", "work experience", "professional experience",
                   "employment", "employment history", "work history", "career history",
                   "relevant experience", "work & experience"],
    # Kept apart so internship time is not counted as full-time experience.
    "internships": ["internships", "internship", "internship experience"],
    # Catch-all blocks of "Label: values" lines. Only skills/certifications/awards
    # lines are kept; interests, languages etc. are dropped.
    "_misc": ["additional information", "other information", "miscellaneous",
              "additional details", "skills & interests", "skills and interests", "others",
              "other details"],
    "skills": ["skills", "technical skills", "key skills", "core skills", "tools",
               "core competencies", "competencies", "skills & tools", "skills and tools"],
    "projects": ["projects", "key projects", "academic projects", "personal projects"],
    "education": ["education", "academic qualifications", "qualifications",
                  "educational qualifications", "academics"],
    "certifications": ["certifications", "certificates", "courses", "licenses"],
    "achievements": ["achievements", "awards", "accomplishments", "awards & achievements",
                     "honors", "honours"],
    # Sections below are recognised so they can be DROPPED, never copied.
    "_drop": ["personal details", "personal information", "personal profile", "hobbies",
              "interests", "hobbies & interests", "languages", "languages known",
              "declaration", "references", "extracurricular", "extra-curricular activities",
              "extracurricular activities", "volunteering", "contact", "contact details",
              "social", "positions of responsibility"],
}
_HEADING_LOOKUP = {alias: key for key, aliases in SECTION_ALIASES.items() for alias in aliases}


# "PROFESSIONAL EXPERIENCE 2 years 8 months", "Work Experience (5+ yrs)"
_HEADING_TAIL = re.compile(
    r"[\s:|\-–—(]*(?:\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|months?|mos?)\b[\s,&]*(?:and\s+)?)+\)?\s*$", re.I)
# An unrecognised ALL-CAPS line like "ADDITIONAL INFO" or "VOLUNTEER WORK" is still a
# heading; without this its content would silently land in the previous section.
_CAPS_HEADING = re.compile(r"^[A-Z][A-Z&]+(?:\s+[A-Z&]+){1,4}$")


def _heading_key(line: str) -> str | None:
    clean = re.sub(r"[^a-z& \-]", "", _HEADING_TAIL.sub("", line.lower())).strip(" -:")
    if not clean or len(clean) > 40:
        return None
    key = _HEADING_LOOKUP.get(clean)
    if key is None and len(line.strip()) >= 8 and _CAPS_HEADING.match(line.strip()):
        return "_unknown"
    return key


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return (header_lines, {section_key: lines}). Header = text before first heading.
    Unrecognised headings go to "_unknown" (dropped, but reported in the audit)."""
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        key = _heading_key(line)
        if key == "_unknown" and current is None:
            key = None  # an ALL-CAPS name at the top is header, not a section
        if key:
            current = key
            sections.setdefault(key, [])
            if key == "_unknown":
                sections.setdefault("_unknown_headings", []).append(line)
            continue
        if current is None:
            header.append(line)
        else:
            sections[current].append(line)
    return header, sections


# ---------------------------------------------------------------- dates -> durations
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_POINT = rf"(?:{_MON}\.?\s*'?\s*(?:\d{{4}}|\d{{2}})|\d{{1,2}}[/\-.]\d{{4}}|\d{{4}})"
_END = rf"(?:{_POINT}|present|current|now|till date|to date|ongoing)"
DATE_RANGE = re.compile(rf"\(?[ \t]*({_POINT})[ \t]*(?:-|–|—|to|till)[ \t]*({_END})[ \t]*\)?", re.I)


def _to_month_index(token: str, today: date) -> int | None:
    t = token.lower().strip().replace(".", " ")
    if t in {"present", "current", "now", "till date", "to date", "ongoing"}:
        return today.year * 12 + today.month
    m = re.match(rf"({_MON})\s*'?\s*(\d{{4}}|\d{{2}})", t)
    if m:
        year = int(m.group(2))
        year = year + 2000 if year < 100 else year
        return year * 12 + MONTHS[m.group(1)[:3]]
    m = re.match(r"(\d{1,2})[/\-\s](\d{4})", t)
    if m:
        return int(m.group(2)) * 12 + int(m.group(1))
    m = re.match(r"(\d{4})", t)
    if m:
        return int(m.group(1)) * 12 + 1
    return None


def replace_ranges_with_durations(text: str, today: date, labels: list[str] | None = None,
                                  ) -> tuple[str, list[tuple[int, int]]]:
    """Swap every date range for '(N.N years)'. Returns new text and the intervals.
    If `labels` is given, the original range text ('Apr 2024 – Mar 2026') is appended to it."""
    intervals: list[tuple[int, int]] = []

    def _sub(m: re.Match) -> str:
        start, end = _to_month_index(m.group(1), today), _to_month_index(m.group(2), today)
        if start is None or end is None or end < start:
            return " "
        intervals.append((start, end))
        if labels is not None:
            labels.append(f"{m.group(1).strip()} – {m.group(2).strip()}")
        years = (end - start + 1) / 12
        return f" ({years:.1f} years) "

    return DATE_RANGE.sub(_sub, text), intervals


def total_years(intervals: list[tuple[int, int]]) -> float:
    """Total experience with overlapping roles merged (gaps are NOT reported)."""
    merged: list[list[int]] = []
    for s, e in sorted(intervals):
        if merged and s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return round(sum(e - s + 1 for s, e in merged) / 12, 1)


# ---------------------------------------------------------------- scrubbers
CITIES = ["mumbai", "bombay", "delhi", "new delhi", "noida", "gurgaon", "gurugram",
          "bangalore", "bengaluru", "hyderabad", "secunderabad", "chennai", "madras",
          "kolkata", "calcutta", "pune", "ahmedabad", "surat", "vadodara", "rajkot",
          "jaipur", "lucknow", "kanpur", "nagpur", "indore", "bhopal", "patna", "ranchi",
          "bhubaneswar", "guwahati", "chandigarh", "ludhiana", "amritsar", "kochi", "cochin",
          "trivandrum", "thiruvananthapuram", "coimbatore", "madurai", "mysore", "mysuru",
          "mangalore", "visakhapatnam", "vizag", "vijayawada", "goa", "dehradun", "srinagar",
          "jammu", "varanasi", "agra", "allahabad", "prayagraj", "raipur", "nashik", "thane",
          "navi mumbai", "faridabad", "ghaziabad", "manipal", "kharagpur", "roorkee",
          "pilani", "warangal", "trichy", "tiruchirappalli", "kozhikode", "calicut", "gandhinagar"]

SCRUB_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    ("url", re.compile(r"(?:https?://|www\.)\S+|\b(?:linkedin|github)\.com/\S*", re.I), "[LINK]"),
    ("phone", re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b"), "[PHONE]"),
    ("age", re.compile(r"\b(?:age[d]?\s*[:\-]?\s*\d{2}|\d{2}\s*(?:years?|yrs?)\s*old)\b", re.I), "[AGE]"),
    ("dob", re.compile(r"\b(?:d\.?o\.?b\.?|date of birth|born)\b[^\n]*", re.I), "[DOB]"),
    ("honorific", re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Shri|Smt|Kumari|Dr)\.?\s+(?=[A-Z])"), ""),
    ("gender_terms", re.compile(
        r"\b(?:male|female|man|woman|women|men|girls?|boys?|"
        r"married|unmarried|spouse|husband|wife|maternity|paternity|pregnan\w*|"
        r"mother|father|daughter|son|gender|sex|marital status)\b\.?", re.I), "[REDACTED]"),
    ("pronouns", re.compile(r"\b(?:he|she)\b", re.I), "the candidate"),
    ("pronouns", re.compile(r"\b(?:his|her|hers)\b", re.I), "their"),
    ("pronouns", re.compile(r"\b(?:him|himself|herself)\b", re.I), "them"),
    ("religion_caste", re.compile(
        r"\b(?:hindu|muslim|islam\w*|christian|sikh|jain|buddhist|parsi|religion|caste|"
        r"category\s*[:\-]?\s*(?:general|obc|sc|st|ews)|obc|ews)\b", re.I), "[REDACTED]"),
    ("institution", re.compile(
        r"\b(?:IIT|IIM|IIIT|NIT|BITS|ISB|XLRI|MICA|NMIMS|SRCC|VIT|SRM|DTU|NSUT)\b[\w ,\-]*|"
        r"(?:[A-Z][\w.&'\-]*\s+){0,6}(?:University|College|Institute|Vidyalaya|Vidyapeeth|"
        r"School|Academy|Polytechnic)\b(?:\s+of(?:\s+[A-Z][\w.&'\-]*){1,5})?", 0), "[INSTITUTION]"),
    ("city", re.compile(r"\b(?:" + "|".join(re.escape(c) for c in CITIES) + r")\b", re.I), "[LOCATION]"),
    ("month_year", re.compile(rf"\b{_MON}\.?\s*[,']?\s*(?:\d{{4}}|'\d{{2}})\b", re.I), ""),
    ("year", re.compile(r"\b(?:19[5-9]\d|20[0-4]\d)\b"), ""),
]


CAREER_BREAK = re.compile(r"\b(?:career\s*break|sabbatical|gap\s*year|break\s*from\s*work|"
                          r"maternity|paternity|parental\s*leave)\b", re.I)


def scrub(text: str, name_tokens: list[str], counts: Counter, only: set[str] | None = None) -> str:
    """Apply the scrub patterns (all, or just the labels in `only`), then the name."""
    for label, pattern, repl in SCRUB_PATTERNS:
        if only is not None and label not in only:
            continue
        text, n = pattern.subn(repl, text)
        counts[label] += n
    for tok in name_tokens:
        text, n = re.subn(rf"\b{re.escape(tok)}\b", "[NAME]", text, flags=re.I)
        counts["name"] += n
    # "[NAME] [NAME] [NAME]" would still reveal how many words the name has.
    text = re.sub(r"\[NAME\](?:[\s\-.']*\[NAME\])+", "[NAME]", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\(\s*\)|\[\s*\]|\s+([,.;:])", lambda m: m.group(1) or "", text)
    # "She led X" -> "the candidate led X" must still start the sentence with a capital.
    text = re.sub(r"(^|[.!?]\s+)the candidate\b", lambda m: m.group(1) + "The candidate", text)
    return text.strip()


def guess_name(header: list[str]) -> str:
    """Candidate name = first header line that looks like a name (used ONLY for
    scrubbing and for the private ID map; never sent to Jev)."""
    for line in header[:4]:
        cand = re.sub(r"^(?:name\s*[:\-]\s*)", "", line, flags=re.I).strip()
        words = cand.split()
        if 1 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z.'\-]+", w) for w in words):
            return cand
    return ""


# ---------------------------------------------------------------- education
DEGREE_LEVELS = [
    ("Doctorate", r"\b(?:ph\.?\s?d|doctorate)\b"),
    ("Masters", r"\b(?:m\.?\s?tech|m\.?\s?e\b|mba|pgdm|pgp|post\s*graduate|m\.?\s?sc|mca|m\.?\s?com|"
                r"m\.?\s?a\b|master'?s?|ms\b|m\.?\s?des)\b"),
    ("Bachelors", r"\b(?:b\.?\s?tech|b\.?\s?e\b|b\.?\s?sc|bca|b\.?\s?com|bba|bms|b\.?\s?a\b|"
                  r"bachelor'?s?|b\.?\s?des|b\.?\s?arch)\b"),
    ("Diploma", r"\bdiploma\b"),
]
FIELD_ABBREVIATIONS = [  # degree abbreviations that imply a field
    (r"\b(?:b\.?\s?com|m\.?\s?com)\b", "commerce"),
    (r"\b(?:bba|mba|pgdm|pgp)\b", "business"),
    (r"\b(?:bca|mca)\b", "computer applications"),
]
FIELD_HINTS = ["computer science", "information and communication technology",
               "information technology", "ict", "electronics", "electrical",
               "mechanical", "civil", "chemical", "economics", "finance", "marketing", "commerce",
               "management", "business", "statistics", "mathematics", "physics", "design",
               "data science", "communications", "psychology", "engineering"]


def summarise_education(lines: list[str]) -> dict:
    """Keep degree level + field only. Institution, year, marks and school (10th/12th) dropped."""
    degrees = []
    institution = next(p for lbl, p, _ in SCRUB_PATTERNS if lbl == "institution")
    for line in lines:
        # Remove the institution name first, so "Govt Engineering College" can't
        # turn into field="engineering" (caught by the swap test).
        low = institution.sub(" ", line).lower()
        if re.search(r"\b(?:10th|12th|ssc|hsc|cbse|icse|class x|class xii|matric)\b", low):
            continue
        for level, pat in DEGREE_LEVELS:
            if re.search(pat, low):
                field = next((f for f in FIELD_HINTS if f in low), None)
                if field is None:
                    field = next((f for pat2, f in FIELD_ABBREVIATIONS if re.search(pat2, low)), None)
                degrees.append({"level": level, "field": field})
                break
    order = [lvl for lvl, _ in DEGREE_LEVELS]
    highest = min((d["level"] for d in degrees), key=order.index, default=None)
    unique = [dict(t) for t in {tuple(d.items()) for d in degrees}]
    return {"highest_degree": highest, "degrees": unique}


# ---------------------------------------------------------------- structure
# Everything below runs on text that has ALREADY been scrubbed, so structuring can
# only rearrange what survived redaction; it can never reintroduce removed details.
_DURATION = re.compile(r"\((\d+\.\d) years\)")  # the marker replace_ranges_with_durations writes
_BULLET = re.compile(r"^\s*(?:[•●▪◦‣⁃∙·*\-–—>➢✓]|\d{1,2}[.)])\s+")
_TITLE_SPLIT = re.compile(r"\s+at\s+|\s*[|–—@]\s*|\s*,\s*|\s+-\s+", re.I)
_PLACEHOLDER = r"\[(?:LOCATION|INSTITUTION|NAME|LINK|EMAIL|PHONE)\]"
# "[LOCATION]", "[LOCATION], India", "| [LINK]" at the end of a header line
_PLACEHOLDER_TAIL = re.compile(rf"(?:[,|\-–—\s]*{_PLACEHOLDER}(?:\s*,\s*[A-Z][A-Za-z ]{{1,20}})?)+\s*$")
_ROLE_WORD = re.compile(
    r"\b(?:intern|internship|manager|engineer|developer|founder|co-founder|cofounder|analyst|associate|"
    r"lead|head|director|consultant|designer|scientist|specialist|executive|officer|architect|"
    r"president|vp|coordinator|administrator|assistant|trainee|fellow|researcher|strategist|"
    r"owner|partner|advisor|adviser|representative|marketer|writer|editor|apprentice|volunteer|"
    r"programmer|technician|accountant|auditor|teacher|tutor|product|sde)\b", re.I)
_INTERN = re.compile(r"\b(?:intern|internship|trainee|apprentice)\b", re.I)
_TITLE_LIKE = re.compile(r"\s[–—|]\s|\s-\s")


def _entries(text: str | None) -> list[tuple[bool, str]]:
    """Lines -> [(is_bullet, text)], with bullet glyphs removed and wrapped lines re-joined.

    A line continues the previous entry when it starts lowercase after an unfinished line,
    or when the previous entry is a long bullet that was cut at the page margin.
    """
    out: list[tuple[bool, str]] = []
    prev_raw_len = 0
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        is_bullet = bool(_BULLET.match(line))
        line = _BULLET.sub("", line).strip()
        if not line:
            continue
        if out and not is_bullet:
            prev_bullet, prev = out[-1]
            unfinished = not prev.endswith((".", ";", ":", "!", "?"))
            long_prev = prev_raw_len >= 70  # the previous line ran to the page margin
            wrapped = unfinished and (
                line[0].islower()
                # "...achieved a / 2% jump in disbursal rate": digit or symbol continuation
                or (long_prev and not line[0].isalpha())
                or (prev_bullet and long_prev and not _TITLE_LIKE.search(line)))
            if wrapped:
                joiner = "" if prev.endswith("-") and line[0].islower() else " "  # "peer-" + "driven"
                out[-1] = (prev_bullet, f"{prev}{joiner}{line}")
                prev_raw_len = len(raw.strip())
                continue
        out.append((is_bullet, line))
        prev_raw_len = len(raw.strip())
    return out


def to_items(text: str | None) -> list[str]:
    """Lines -> flat list of items."""
    return [t for _, t in _entries(text)]


def to_groups(text: str | None) -> list[dict]:
    """Projects-style blocks -> [{name, highlights}]: a plain line names an entry and the
    bullets under it are its highlights. A list of bare bullets becomes one entry each."""
    groups: list[dict] = []
    for is_bullet, line in _entries(text):
        if is_bullet and groups and groups[-1]["name"] is not None:
            groups[-1]["highlights"].append(line)
        elif is_bullet:
            groups.append({"name": None, "highlights": [line]})
        else:
            groups.append({"name": _PLACEHOLDER_TAIL.sub("", line).strip(" |") or line, "highlights": []})
    return groups


def to_skill_list(text: str | None) -> list[str]:
    """'Languages: Java, SQL | Tools: JIRA' -> ['Java', 'SQL', 'JIRA'] (deduped, order kept)."""
    out: list[str] = []
    for line in (text or "").splitlines():
        line = _BULLET.sub("", line.strip())
        # Split on separators outside parentheses: "Office (Word, Excel), Canva" is 2 skills.
        parts, depth, cur = [], 0, ""
        for ch in line:
            depth += (ch == "(") - (ch == ")")
            if depth <= 0 and ch in ",;|•●·":  # not "/": A/B, CI/CD
                parts.append(cur)
                cur, depth = "", 0
            else:
                cur += ch
        parts.append(cur)
        for part in parts:
            if ":" in part and len(part.split(":", 1)[0].split()) <= 3:  # drop "Languages:" labels
                part = part.split(":", 1)[1]
            part = part.strip(" .-–")
            if 1 < len(part) <= 60 and part.lower() not in {x.lower() for x in out}:
                out.append(part)
    return out[:80]


_CITY_TAIL = re.compile(
    r"[\s,|\-\u2013\u2014]*\b((?:" + "|".join(re.escape(c) for c in CITIES) + r")"
    r"(?:\s*,\s*[A-Z][A-Za-z ]{1,25})?)\s*$", re.I)


def _split_location(s: str | None) -> tuple[str | None, str | None]:
    """'Fibe (formerly EarlySalary) Pune, India' -> ('Fibe (formerly EarlySalary)', 'Pune, India')."""
    if not s:
        return s, None
    m = _CITY_TAIL.search(s)
    if not m or m.start() == 0:
        return s, None
    return s[:m.start()].strip(" ,|-\u2013\u2014") or None, m.group(1).strip()


def _clean(s: str | None) -> str | None:
    s = _PLACEHOLDER_TAIL.sub("", s or "").strip(" ,|-–—")
    return s or None


def _split_title_company(head: str) -> tuple[str | None, str | None]:
    head = _clean(head) or ""
    if not head:
        return None, None
    parts = [x.strip() for x in _TITLE_SPLIT.split(head, maxsplit=1) if x and x.strip()]
    if len(parts) < 2:
        return _clean(parts[0]) if parts else None, None
    title, company = _clean(parts[0]), _clean(parts[1])
    # "Spinny – Market Research Intern" is Company – Title.
    if company and _ROLE_WORD.search(company) and not (title and _ROLE_WORD.search(title)):
        title, company = company, title
    return title, company


def _is_company_line(line: str, nxt: str | None, prev: str | None) -> bool:
    """'Fibe (formerly EarlySalary) [LOCATION], India' followed by a dated, title-only line
    ('Product Manager (0.7 years)') is a company heading for the roles under it."""
    if not nxt or not _DURATION.search(nxt) or _DURATION.search(line) or _BULLET.match(line):
        return False
    # "...drop-off points found / through funnel analysis": the tail of a wrapped bullet.
    if prev and _BULLET.match(prev) and not prev.rstrip().endswith((".", ";", "!", "?")) and line[:1].islower():
        return False
    _, nxt_company = _split_title_company(_DURATION.sub(" ", nxt))
    words = line.split()
    first = words[0].lower() if words else ""
    return (nxt_company is None and 1 <= len(words) <= 10 and not line.rstrip().endswith(".")
            and not first.endswith(("ed", "ing")))


def to_roles(exp_text: str, intervals: list[tuple[int, int]] | None = None,
             internship: bool = False, labels: list[str] | None = None) -> list[dict]:
    """Scrubbed experience text (date ranges already turned into '(N.N years)') -> one entry
    per role: {title, company, years, internship, highlights}. A dated line starts a role.

    `intervals` are the date intervals in the order their markers appear; they are attached
    to each role (as "_interval", removed before sending) so totals can skip internships.
    """
    lines = [l.strip() for l in exp_text.splitlines() if l.strip()]
    merged: list[str] = []
    carry: str | None = None  # a lone date waiting for the title line below it
    for i, line in enumerate(lines):
        if _DURATION.fullmatch(line):
            prev = merged[-1] if merged else ""
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            # A lone date belongs to the title above it, unless the line above is body text
            # (a bullet or a wrapped tail); then it belongs to the title below.
            prev_is_title = (prev and not _DURATION.search(prev) and not _BULLET.match(prev)
                             and prev[:1].isupper() and len(prev) <= 70 and not prev.endswith("."))
            if prev_is_title:
                merged[-1] = f"{prev} {line}"
            elif nxt and not _DURATION.search(nxt) and not _BULLET.match(nxt):
                carry = line
            else:
                merged.append(line)
            continue
        if carry:
            line, carry = f"{line} {carry}", None
        merged.append(line)

    queue = list(intervals or [])
    label_queue = list(labels or [])
    roles: list[dict] = []
    current: dict | None = None
    body: list[str] = []
    company_ctx: str | None = None
    ctx_location: str | None = None

    def close() -> None:
        if current is not None:
            current["highlights"] = to_items("\n".join(body))
            roles.append(current)

    for i, line in enumerate(merged):
        m = _DURATION.search(line)
        if m:
            close()
            body = []
            title, company = _split_title_company(_DURATION.sub(" ", line))
            company, location = _split_location(company or company_ctx)
            title, title_loc = _split_location(title)
            current = {"title": title, "company": company}
            if location or title_loc or ctx_location:
                current["location"] = location or title_loc or ctx_location
            if labels is not None:  # name-only mode: real dates are kept
                current["dates"] = label_queue.pop(0) if label_queue else None
            current.update({"years": float(m.group(1)),
                            "internship": internship or bool(_INTERN.search(title or "")), "highlights": []})
            if CAREER_BREAK.search(line):  # only reachable in name-only mode
                current["career_break"] = True
            current["_interval"] = queue.pop(0) if queue else None
        elif _is_company_line(line, merged[i + 1] if i + 1 < len(merged) else None,
                              merged[i - 1] if i else None):
            close()
            current, body = None, []
            company_ctx, ctx_location = _split_location(_clean(line))
        else:
            if current is None:  # text before any dated role (e.g. undated experience)
                current = {"title": None, "company": company_ctx, "years": None,
                           "internship": internship, "highlights": [], "_interval": None}
            body.append(line)
    close()
    return roles


def _route_misc(lines: list[str]) -> dict[str, list[str]]:
    """'Skills: SQL, Excel' / 'Certifications: X' / 'Interests: Y' -> kept or dropped by label."""
    routes = {"skills": ("skill", "tool", "technolog", "tech stack", "software", "platform"),
              "certifications": ("certif", "course", "license"),
              "achievements": ("achievement", "award", "honour", "honor")}
    out: dict[str, list[str]] = {"skills": [], "certifications": [], "achievements": [], "other": []}
    for line in lines:
        label, sep, rest = _BULLET.sub("", line).partition(":")
        low = label.lower()
        key = next((k for k, needles in routes.items() if any(n in low for n in needles)), None)
        if sep and len(label.split()) <= 4 and key:
            out[key].append(rest.strip())
        else:
            out["other"].append(line)  # interests, activities...: kept only in name-only mode
    return out


_CONTACT_WORDS = re.compile(r"\b(?:linkedin|github|email|e-mail|phone|mobile|tel|portfolio|website)\b\s*:?", re.I)


def _header_info(lines: list[str]) -> list[str]:
    """Header lines minus contact placeholders: keeps a headline or city, drops '[EMAIL] | [PHONE]'."""
    out = []
    for line in lines:
        rest = _CONTACT_WORDS.sub(" ", re.sub(r"\[(?:EMAIL|PHONE|LINK|NAME)\][\w\-]*", " ", line))
        rest = re.sub(r"\s*[|,\u2022\u00b7]\s*(?=[|,\u2022\u00b7]|$)|^[\s|,\u2022\u00b7]+", "", rest)
        rest = re.sub(r"\s{2,}", " ", rest).strip(" |,-\u2022\u00b7")
        if re.search(r"[A-Za-z]{2,}", rest):
            out.append(rest)
    return out


# ---------------------------------------------------------------- main entry
def redact(resume_id: str, text: str, today: date | None = None,
           mode: str | None = None) -> tuple[dict, dict]:
    """Return (jev_payload, audit). jev_payload is the ONLY thing sent to Jev."""
    today = today or date.today()
    full = (mode or REDACTION_MODE) == "full"
    only = None if full else NAME_ONLY_PATTERNS
    header, sections = split_sections(text)
    name = guess_name(header)
    name_tokens = [t for t in re.split(r"\s+", name) if len(t) > 2]
    counts: Counter = Counter()

    def scrub_lines(lines: list[str]) -> str | None:
        if not lines:
            return None
        joined = "\n".join(lines)
        if full:  # dates -> durations so gaps are invisible
            joined, _ = replace_ranges_with_durations(joined, today)
        return scrub(joined, name_tokens, counts, only) or None

    def block(key: str) -> str | None:
        return scrub_lines(sections.get(key, []))

    def roles_from(key: str, internship: bool) -> list[dict]:
        # Career breaks are dropped entirely (line + its dates), so gaps are invisible
        # and do not inflate total experience.
        # (full mode only; name-only mode keeps them, flagged, and leaves them out of totals).
        src = sections.get(key, [])
        kept = [l for l in src if not CAREER_BREAK.search(l)] if full else src
        counts["career_break"] += len(src) - len(kept)
        labels: list[str] | None = None if full else []
        text_d, ivs = replace_ranges_with_durations("\n".join(kept), today, labels)
        return to_roles(scrub(text_d, name_tokens, counts, only), ivs, internship=internship, labels=labels)

    roles = roles_from("experience", False) + roles_from("internships", True)
    counted = [r for r in roles if r["_interval"] and not r.get("career_break")]
    work_iv = [r["_interval"] for r in counted if not r["internship"]]
    intern_iv = [r["_interval"] for r in counted if r["internship"]]
    for r in roles:
        r.pop("_interval", None)

    misc = _route_misc(sections.get("_misc", []))
    edu_lines = sections.get("education", [])
    # Bullets under a degree are achievements (case competitions, ranks). In full mode the
    # degree lines only ever yield level + field.
    edu_bullets = [l for l in edu_lines if _BULLET.match(l)]
    edu_degrees = [l for l in edu_lines if not _BULLET.match(l)]

    skills = to_skill_list("\n".join(filter(None, [block("skills"), scrub_lines(misc["skills"])])))
    certs = to_items("\n".join(filter(None, [block("certifications"), scrub_lines(misc["certifications"])])))
    awards = to_items("\n".join(filter(None, [block("achievements"), scrub_lines(misc["achievements"]),
                                              scrub_lines(edu_bullets)])))

    payload = {
        "id": resume_id,
        "summary": block("summary"),
        "experience": {
            "total_years": total_years(work_iv) if work_iv else None,
            "internship_years": total_years(intern_iv) if intern_iv else None,
            "roles": roles,
        },
        "skills": skills,
        "projects": to_groups(block("projects")),
        "certifications": certs,
        "achievements": awards,
        "education": summarise_education(edu_degrees),
    }
    if not full:
        payload["education"]["details"] = to_items(scrub_lines(edu_degrees))
        other_lines = misc["other"] + sections.get("_drop", []) + sections.get("_unknown", [])
        payload["header"] = _header_info([scrub(l, name_tokens, counts, only) for l in header if l.strip() != name])
        payload["other"] = to_items(scrub_lines(other_lines))

    warnings = []
    if not name:
        warnings.append("Could not detect the candidate's name, so it may not be hidden. Check what Jev saw.")
    if full and len(header) > 6:  # name, title, email, phone, links on separate lines is normal
        warnings.append(f"{len(header)} lines before the first recognised heading were dropped "
                        "as name/contact details. Check that no section was missed.")
    for h in sections.get("_unknown_headings", []) if full else []:
        warnings.append(f"Unrecognised section '{h.title()}' was not sent to Jev.")
    if not roles:
        warnings.append("No work experience was found.")

    hidden = {"_drop", "_unknown", "_unknown_headings", "_misc"}
    audit = {
        "id": resume_id,
        "mode": "full" if full else "name",
        "candidate_name_guess": name,
        "sections_found": sorted(k for k in sections if k not in hidden),
        "dropped_sections": "_drop" in sections,
        "header_lines_dropped": len(header),
        "warnings": warnings,
        "redactions": dict(counts),
        "needs_human_review": not (roles or skills),
    }
    return payload, audit
