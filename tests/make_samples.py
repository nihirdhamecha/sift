"""Generate a few synthetic resume PDFs that deliberately contain leaky details
(DOB, gender, address, religion, women's college, maternity break) so the
redaction can be checked. Fictional people only."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SAMPLES = {
    "sample_ananya.pdf": """Ananya Kulkarni
ananya.k@gmail.com | +91 98765 43210 | Pune, Maharashtra | linkedin.com/in/ananyak
Professional Summary
Product manager with 4 years of experience. She has led growth and onboarding for a consumer app.
Work Experience
Product Manager, Swiftpay  Jan 2022 - Present
Owned onboarding funnel; shipped KYC revamp to 2M users; ran A/B tests that lifted activation.
Career break (maternity)  Mar 2021 - Dec 2021
Associate Product Manager, Cartly  Jul 2019 - Feb 2021
Wrote specs, worked with engineering on checkout; tracked funnel metrics in SQL and Mixpanel.
Skills
SQL, Mixpanel, Figma, A/B testing, JIRA
Education
MBA, Marketing, Symbiosis Institute of Business Management, Pune  2017 - 2019
B.Com, Lady Shri Ram College for Women, Delhi  2014 - 2017
12th CBSE, Kendriya Vidyalaya  2014
Personal Details
Date of Birth: 12 March 1996 | Gender: Female | Marital Status: Married | Religion: Hindu
Hobbies
Kathak, cooking, temple volunteering
""",
    "sample_imran.pdf": """Mohammed Imran Qureshi
imran.q@yahoo.com  9123456789  Hyderabad
Profile
Software engineer moving into product. He has 3 years of backend experience.
Experience
Software Engineer, Datanest  06/2021 - 11/2024
Built payment APIs in Java; worked with PM on specs for merchant dashboard.
Projects
Side project: habit tracker app, 500 users, designed and launched on Play Store.
Technical Skills
Java, Spring, SQL, Python
Education
B.Tech, Computer Science, Indian Institute of Technology Hyderabad  2017 - 2021
Languages Known
English, Hindi, Urdu, Telugu
""",
    "sample_rohit.pdf": """Rohit Verma
rohit.verma@outlook.com | 8899776655
Summary
Sales executive, 26 years old, looking for opportunities in product.
Employment History
Sales Executive, Bright Motors, Lucknow  2020 - 2025
Met monthly targets; managed dealer relationships.
Key Skills
Negotiation, MS Excel, CRM
Education
BBA, Lucknow University  2017 - 2020
Declaration
I hereby declare that the above information is true. Mr. Rohit Verma
""",
}


def write_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in text.strip().splitlines():
        c.setFont("Helvetica-Bold" if len(line) < 25 and line.istitle() else "Helvetica", 10)
        c.drawString(40, y, line)
        y -= 16
    c.save()


if __name__ == "__main__":
    out = Path(__file__).parent / "sample_resumes"
    out.mkdir(exist_ok=True)
    for name, text in SAMPLES.items():
        write_pdf(out / name, text)
    print(f"Wrote {len(SAMPLES)} sample PDFs to {out}")
