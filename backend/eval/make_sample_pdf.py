"""Builds eval/sample.pdf: a fictional 4-page handbook with facts the eval questions can check."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

PAGES = [
    ("Working hours and remote work", [
        "Northwind Labs core hours are 10:00 to 16:00 IST. Outside core hours, employees may "
        "organise their day freely as long as agreed deadlines are met.",
        "Employees may work remotely up to 3 days per week. Employees in their first 90 days "
        "(the probation period) must work on-site 5 days per week so they can be onboarded properly.",
        "New joiners receive a one-time home-office stipend of Rs 15,000 for a desk and chair. "
        "Northwind also reimburses internet costs up to Rs 1,000 per month on submission of the bill.",
        "Team leads may approve a temporary extra remote day for medical or family reasons. Such "
        "exceptions are recorded by HR and do not change the standard remote work limit.",
        "Employees working from a different city for more than 2 weeks must inform HR in advance "
        "because tax and insurance rules can change with the work location.",
        "Meeting-free Wednesdays are encouraged so that people can do focused work. Recurring "
        "meetings should have an agenda circulated at least one day before.",
    ]),
    ("Leave policy", [
        "Every employee gets 24 days of paid annual leave per calendar year. Up to 10 unused days "
        "can be carried over to the next year; the rest lapse on 31 March.",
        "Sick leave is 12 days per year. A medical certificate is required when sick leave lasts "
        "more than 2 consecutive days. There is no certificate requirement for one or two days.",
        "Maternity leave is 26 weeks and paternity leave is 2 weeks. Northwind observes 14 public "
        "holidays each year; the list is published every January on the intranet.",
        "Bereavement leave is 5 days for the loss of an immediate family member. Unpaid leave of "
        "up to 30 days can be taken once per year with written approval from the manager.",
        "Employees who work on a public holiday at the company's request receive a compensatory "
        "day off, which must be used within 60 days of the holiday worked.",
        "Leave requests of 5 or more consecutive days should be submitted at least 2 weeks ahead "
        "so that project handovers can be planned.",
    ]),
    ("Expenses and travel", [
        "During business travel, employees receive a meal allowance of Rs 1,500 per day. Flights "
        "shorter than 6 hours must be booked in economy class.",
        "All expense claims must be filed within 30 days of the expense, with original receipts. "
        "Any single expense above Rs 10,000 needs approval from both the manager and the finance team.",
        "Laptops are refreshed every 3 years. Damaged equipment should be reported to IT within "
        "2 working days.",
        "Hotel stays are capped at Rs 6,000 per night in metro cities and Rs 4,000 elsewhere. "
        "Employees who find a cheaper option may keep no part of the difference.",
        "Local travel by cab is reimbursed for client visits only. Daily commuting to the office "
        "is not reimbursed under any circumstances.",
        "Advance payments for travel can be requested up to 80 percent of the estimated cost and "
        "must be settled within 15 days of returning.",
    ]),
    ("Security, learning and exits", [
        "Passwords must be at least 14 characters long and multi-factor authentication is mandatory "
        "on every company account. Personal USB drives must not be connected to company laptops.",
        "Any suspected security incident must be reported within 24 hours to "
        "security@northwindlabs.example. Late reporting is treated as a policy violation.",
        "Each employee has a learning budget of Rs 40,000 per year for courses and certifications. "
        "The notice period for resignation is 60 days for all employees.",
        "Performance reviews happen twice a year, in April and October. Each review produces a "
        "rating from 1 to 5 that is discussed with the employee in a one-to-one meeting.",
        "Access to production systems is reviewed every quarter. Access that has not been used in "
        "90 days is removed automatically and must be requested again.",
        "On the last working day, employees return all equipment and complete an exit interview "
        "with HR. Final settlement is processed within 45 days of the last working day.",
    ]),
]

if __name__ == "__main__":
    styles = getSampleStyleSheet()
    story = []
    for n, (title, paras) in enumerate(PAGES):
        if n:
            story.append(PageBreak())
        story.append(Paragraph(f"Northwind Labs Employee Handbook: {title}", styles["Heading1"]))
        for p in paras:
            story += [Spacer(1, 12), Paragraph(p, styles["BodyText"])]
    out = Path(__file__).with_name("sample.pdf")
    SimpleDocTemplate(str(out), pagesize=A4).build(story)
    print("wrote", out)
