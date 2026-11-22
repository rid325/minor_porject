"""Document categories and types shown in the account's saved document picker."""

CATALOGUE = {
    "Identity Proof": (
        ("aadhaar", "Aadhaar Card", "identity"), ("pan", "PAN Card", "identity"),
        ("voter_id", "Voter ID Card", "identity"), ("passport", "Passport", "identity"),
        ("driving_licence", "Driving Licence", "identity"),
    ),
    "Address Proof": (
        ("domicile", "Domicile Certificate", "residence"), ("residence", "Residence Certificate", "residence"),
        ("ration_card", "Ration Card", "residence"), ("electricity_bill", "Electricity Bill", "residence"),
        ("rent_agreement", "Rent Agreement", "residence"),
    ),
    "Income and Financial Documents": (
        ("income", "Income Certificate", "income"), ("bpl", "BPL Certificate", "other"),
        ("bank_passbook", "Bank Passbook", "bank"), ("bank_statement", "Bank Statement", "bank"),
        ("salary_slip", "Salary Slip", "other"), ("itr", "ITR", "other"),
    ),
    "Caste and Category Certificates": (
        ("sc", "SC Certificate", "category"), ("st", "ST Certificate", "category"),
        ("obc", "OBC Certificate", "category"), ("obc_ncl", "OBC Non-Creamy Layer Certificate", "category"),
        ("ews", "EWS Certificate", "category"),
    ),
    "Education Documents": (
        ("student_id", "Student ID Card", "identity"),
        ("marksheet_10", "10th Marksheet", "age"), ("marksheet_12", "12th Marksheet", "other"),
        ("graduation", "Graduation Certificate", "other"), ("bonafide", "Bonafide Certificate", "other"),
        ("school_leaving", "School Leaving Certificate", "age"),
        ("transfer", "Transfer Certificate", "other"),
    ),
    "Family Documents": (
        ("birth", "Birth Certificate", "age"), ("marriage", "Marriage Certificate", "other"),
        ("death", "Death Certificate", "other"), ("widow", "Widow Certificate", "other"),
        ("family_id", "Family ID", "family_id"),
    ),
    "Agriculture and Land Documents": (
        ("land_ownership", "Land Ownership Certificate", "other"), ("khasra", "Khasra / Khatauni", "other"),
        ("jamabandi", "Jamabandi", "other"), ("farmer_registration", "Farmer Registration Certificate", "other"),
    ),
    "Medical and Disability Documents": (
        ("disability", "Disability Certificate", "disability"), ("udid", "UDID Card", "disability"),
        ("medical", "Medical Certificate", "other"), ("ayushman", "Ayushman Bharat Card", "other"),
    ),
    "Employment Documents": (
        ("labour", "Labour Card", "other"), ("mgnrega", "MGNREGA Job Card", "other"),
        ("employment", "Employment Certificate", "other"), ("udyam", "Udyam Registration Certificate", "other"),
    ),
    "Other Important Documents": (
        ("photo", "Passport Size Photograph", "unknown"), ("signature", "Signature", "unknown"),
        ("affidavit", "Affidavit", "other"), ("declaration", "Self-Declaration Form", "other"),
        ("scheme_letter", "Government Scheme Application / Approval Letter", "other"),
        ("supporting", "Other Supporting Document", "other"),
    ),
}

DOCUMENT_TYPES = {
    code: {"label": label, "category": category, "evidence_type": evidence_type}
    for category, entries in CATALOGUE.items()
    for code, label, evidence_type in entries
}
