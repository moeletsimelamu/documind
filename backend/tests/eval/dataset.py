"""A small retrieval evaluation set: four fictional documents and 30 questions.

All text is original and fictional. Each question names the document that answers it and an
``anchor``: a phrase that the passage containing the answer must include. Questions are labelled
``keyword`` when they share important words with the answer, and ``paraphrase`` when they ask the
same thing in different words, which keyword search is expected to handle less well. The labels
are the author's judgement.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class EvalDocument:
    name: str
    text: str | None = None  # a text file
    pages: tuple[str, ...] | None = None  # a PDF, one string per page


@dataclass(frozen=True)
class EvalQuestion:
    question: str
    document: str
    anchor: str
    kind: Literal["keyword", "paraphrase"]


HANDBOOK = EvalDocument(
    name="northwind-staff-handbook.txt",
    text="""Northwind Trading - Staff Handbook
Version 4, effective 1 February 2026

1. Working hours
Core hours are 09:30 to 15:30, Monday to Friday. Outside core hours you may arrange your day with your team lead.
Overtime must be approved in advance by a manager and is paid at 1.5 times the normal hourly rate.

2. Leave
Full-time staff receive 21 working days of paid vacation per year. Part-time staff receive a pro-rata share.
Up to five unused vacation days can be carried over, but they must be taken before 31 March of the following year.
Sick leave of more than two consecutive days requires a medical certificate.
Parents may take 16 weeks of paid parental leave, which can be split into two blocks.

3. Remote work
Employees may work from home up to three days per week after completing their probation period.
Remote work from another country requires written approval from People Operations, for no more than 20 days a year.

4. Expenses
Expense claims must be submitted within 30 days of purchase, with itemised receipts.
Meals while travelling are reimbursed up to R450 per day. Alcohol is never reimbursed.
Mileage for private vehicles is paid at R4.84 per kilometre.

5. Equipment
Each new employee receives a laptop and a headset. Lost or stolen equipment must be reported to IT within 24 hours.
Equipment must be returned on the last working day; unreturned laptops are deducted from the final salary at their depreciated value.

6. Conduct and complaints
Concerns about misconduct can be raised with any manager or anonymously through the Speak Up line.
Retaliation against anyone who raises a concern in good faith is treated as gross misconduct.
""",
)

SECURITY = EvalDocument(
    name="it-security-policy.txt",
    text="""Information Security Policy
Owner: IT Security, reviewed every twelve months

Passwords
Passwords must be at least 14 characters long. Passphrases made of several unrelated words are recommended.
Passwords must not be reused across systems and must be stored only in the approved password manager, Vaultline.
Passwords are not changed on a fixed schedule; they are changed immediately if a compromise is suspected.

Multi-factor authentication
MFA is mandatory for email, the VPN and all finance systems. Authenticator apps or hardware keys are allowed; SMS codes are not.

Devices
Laptops must use full-disk encryption and lock automatically after 5 minutes of inactivity.
Personal phones may access email only if they are enrolled in device management.
USB storage devices are blocked on company laptops unless an exception is approved by IT Security.

Reporting incidents
Suspected phishing emails must be reported with the Report Phish button, not forwarded.
Any security incident must be reported to the service desk within one hour of discovery, by phone on extension 4400.

Data classification
Data is classified as Public, Internal, Confidential or Restricted.
Restricted data, such as payroll and medical records, may not be stored on personal devices or sent by email without encryption.
Customer data must be deleted 24 months after the end of the contract unless the law requires longer retention.
""",
)

REPORT = EvalDocument(
    name="q3-operations-report.pdf",
    pages=(
        "Northwind Trading\nQ3 2026 Operations Report\n"
        "Prepared by the Operations Office, 14 October 2026\n\nSummary\n"
        "Revenue for the quarter was R38.2 million, up 8 percent on Q2.\n"
        "Gross margin narrowed to 31 percent because of higher freight costs.\n"
        "On-time delivery fell to 87 percent, below the 95 percent target.",
        "Logistics\n"
        "Congestion at the Durban container terminal delayed inbound shipments by an average of "
        "11 days.\n"
        "The main packaging supplier, Kestrel Boxes, missed four delivery windows in August.\n"
        "A second packaging supplier, Ridgeway Pack, was contracted on 22 August to reduce "
        "dependence on a single vendor.\n"
        "Air freight was used for urgent orders, adding R1.4 million in unplanned costs.",
        "Warehouse and people\n"
        "The Midrand warehouse reached 96 percent capacity in September.\n"
        "A lease for an additional 2,000 square metres in Pomona was signed and takes effect in "
        "January.\n"
        "Staff turnover in the warehouse was 6 percent for the quarter.\n"
        "There were two lost-time injuries; both involved manual lifting, and forklift refresher "
        "training was scheduled.",
        "Outlook\n"
        "On-time delivery is expected to recover to 93 percent in Q4 as port congestion eases.\n"
        "The Q4 revenue forecast is R41 million.\n"
        "Key risks are a possible strike at the port and further increases in diesel prices.",
    ),
)

MINUTES = EvalDocument(
    name="falcon-steering-minutes.pdf",
    pages=(
        "Project Falcon Steering Committee\n"
        "Minutes of the meeting held on 9 September 2026\n"
        "Present: N. Dlamini (chair), P. Osei, R. Naidoo, L. van Wyk\n\n1. Budget\n"
        "The committee approved a total budget of R4.5 million for Project Falcon, including a "
        "10 percent contingency.\nSpending to date is R1.1 million.",
        "2. Timeline\n"
        "The customer portal will launch on 15 February 2027, two weeks later than planned, "
        "because the payments integration needs more testing.\n"
        "User acceptance testing runs from 5 to 29 January 2027.\n\n3. Vendor\n"
        "The committee chose Lumen Systems as the implementation partner after comparing three "
        "proposals.\n"
        "The contract includes a penalty of 2 percent per week for late delivery, capped at "
        "10 percent.",
        "4. Risks and actions\n"
        "The biggest risk is the availability of the two payments specialists, who are shared "
        "with another project.\n"
        "Action: R. Naidoo to confirm specialist availability by 30 September.\n"
        "Action: P. Osei to prepare a data migration plan for the November meeting.\n"
        "The next meeting is on 14 October 2026.",
    ),
)

DOCUMENTS = (HANDBOOK, SECURITY, REPORT, MINUTES)

_H, _S, _R, _M = HANDBOOK.name, SECURITY.name, REPORT.name, MINUTES.name

QUESTIONS = (
    EvalQuestion(
        "How many days of paid vacation do full-time staff get?",
        _H,
        "21 working days of paid vacation",
        "keyword",
    ),
    EvalQuestion(
        "What is the annual leave entitlement?",
        _H,
        "21 working days of paid vacation",
        "paraphrase",
    ),
    EvalQuestion(
        "Until when can unused vacation days be carried over?", _H, "before 31 March", "keyword"
    ),
    EvalQuestion(
        "How long is paid parental leave?", _H, "16 weeks of paid parental leave", "keyword"
    ),
    EvalQuestion(
        "How many days a week can I work from home?", _H, "up to three days per week", "keyword"
    ),
    EvalQuestion(
        "What is the overtime pay rate?", _H, "1.5 times the normal hourly rate", "keyword"
    ),
    EvalQuestion(
        "What is the daily meal allowance when travelling?", _H, "R450 per day", "keyword"
    ),
    EvalQuestion(
        "How much do we get per km for driving our own car?",
        _H,
        "R4.84 per kilometre",
        "paraphrase",
    ),
    EvalQuestion(
        "What happens if I don't give back my laptop when I leave the company?",
        _H,
        "unreturned laptops are deducted",
        "paraphrase",
    ),
    EvalQuestion(
        "How can I report wrongdoing without giving my name?", _H, "Speak Up line", "paraphrase"
    ),
    EvalQuestion(
        "What is the minimum password length?", _S, "at least 14 characters long", "keyword"
    ),
    EvalQuestion("Which password manager is approved?", _S, "Vaultline", "keyword"),
    EvalQuestion("Are SMS codes allowed for MFA?", _S, "SMS codes are not", "keyword"),
    EvalQuestion(
        "Can I plug a memory stick into my work computer?",
        _S,
        "USB storage devices are blocked",
        "paraphrase",
    ),
    EvalQuestion(
        "Which phone extension do I call to report a security incident?",
        _S,
        "extension 4400",
        "keyword",
    ),
    EvalQuestion(
        "How long is customer data kept after a contract ends?",
        _S,
        "deleted 24 months after the end of the contract",
        "keyword",
    ),
    EvalQuestion(
        "After how many minutes of inactivity must laptops lock?",
        _S,
        "lock automatically after 5 minutes",
        "keyword",
    ),
    EvalQuestion("What was revenue for the quarter?", _R, "R38.2 million", "keyword"),
    EvalQuestion("Why did profitability go down?", _R, "higher freight costs", "paraphrase"),
    EvalQuestion(
        "Which packaging supplier missed delivery windows?", _R, "Kestrel Boxes", "keyword"
    ),
    EvalQuestion(
        "How long were inbound shipments delayed at Durban?", _R, "average of 11 days", "keyword"
    ),
    EvalQuestion(
        "When can we start using the extra storage space?",
        _R,
        "takes effect in January",
        "paraphrase",
    ),
    EvalQuestion("What is the Q4 revenue forecast?", _R, "R41 million", "keyword"),
    EvalQuestion(
        "How many workplace accidents were there?", _R, "two lost-time injuries", "paraphrase"
    ),
    EvalQuestion(
        "What budget was approved for Project Falcon?",
        _M,
        "total budget of R4.5 million",
        "keyword",
    ),
    EvalQuestion(
        "When will the customer portal go live?", _M, "launch on 15 February 2027", "paraphrase"
    ),
    EvalQuestion("Which company is the implementation partner?", _M, "Lumen Systems", "keyword"),
    EvalQuestion("What is the penalty for late delivery?", _M, "2 percent per week", "keyword"),
    EvalQuestion(
        "Who will confirm specialist availability?", _M, "R. Naidoo to confirm", "keyword"
    ),
    EvalQuestion(
        "When is the next steering committee meeting?",
        _M,
        "next meeting is on 14 October",
        "keyword",
    ),
)
