"""Official source material used to render correction routes."""

UIDAI_CENTRE = ("UIDAI Aadhaar Seva Kendra and fee schedule", "https://www.uidai.gov.in/en/aadhaar-seva-kendra")
UIDAI_STATUS = ("Check Aadhaar update status", "https://myaadhaar.uidai.gov.in/CheckAadhaarStatus")
UIDAI_TIMING = ("UIDAI update timing and support", "https://uidai.gov.in/hi/enrolment-and-update")
UIDAI_FORMS = ("UIDAI forms and accepted supporting documents", "https://uidai.gov.in/en/enrolment-documents")
UIDAI_SOP = ("UIDAI date-of-birth update SOP", "https://www.uidai.gov.in/images/SOP_for_DOB_update.pdf")
UIDAI_CORRIGENDUM = (
    "UIDAI updated date-of-birth SOP annexures",
    "https://backend.uidai.gov.in/get/files/media/document/2026-09/SOP_for_DOB_update.pdf",
)
BIRTH_ACT = (
    "Registration of Births and Deaths Act, Section 15",
    "https://upload.indiacode.nic.in/showfile?actid=AC_CEN_5_40_00006_196918_1517807324141&filename=a1969-18.pdf&type=actfile",
)
SARAL = ("Haryana government SARAL services", "https://www.haryana.gov.in/project/e-services-saral-haryana/")
GURUGRAM = ("Gurugram district e-services", "https://gurugram.gov.in/service/e-services/")


def aadhaar_dob():
    return {
        "title": "If Aadhaar has the incorrect date",
        "online_offline": "Visit an Aadhaar enrolment or update centre for the date-of-birth change. UIDAI Aadhaar Seva Kendras offer both online appointment booking and walk-in tokens.",
        "where": "UIDAI Aadhaar Seva Kendra or Aadhaar enrolment/update centre offering demographic updates. Use UIDAI’s centre information to find a location. For UIDAI support, call 1947.",
        "mandatory": ["Aadhaar details for the centre visit.", "An original proof of date of birth accepted by UIDAI for your case."],
        "conditional": [
            "If UIDAI previously verified the date using a birth certificate and the underlying birth record needed correction, ask about the corrected certificate from the same registrar with the same birth registration number and the applicable affidavit.",
            "If a previous date-of-birth update was made, ask the centre about UIDAI’s exception process and the current annexures.",
        ],
        "steps": [
            "Check with the centre which proof was used previously and whether the existing date is recorded as declared, approximate or verified.",
            "Bring the applicable proof and complete the update request and authentication at the centre.",
            "Keep the receipt and use your update reference to check status through UIDAI.",
            "Check the date on the updated Aadhaar after the change appears.",
        ],
        "fees_timing": "UIDAI lists ₹75 for a separately requested demographic update. Check the current fee schedule for combined services. UIDAI gives a typical update range of 30 to 90 days, depending on the update and verification. Use the update reference to track your request and ask the centre about exception cases.",
        "sources": [UIDAI_CENTRE, UIDAI_SOP, UIDAI_CORRIGENDUM, UIDAI_FORMS, UIDAI_STATUS, UIDAI_TIMING],
    }


def birth_dob(state, district):
    sources = [BIRTH_ACT]
    local = ""
    if state == "haryana":
        sources.append(SARAL)
        local = " If the birth was registered in Haryana, use the state’s SARAL service directory to check the available route."
        if district in {"gurugram", "gurgaon"}:
            sources.append(GURUGRAM)
            local += " Gurugram’s district service page lists birth certificate services and forms."
    return {
        "title": "If the birth register has the incorrect date",
        "online_offline": "Ask the registrar for the original registration area whether a correction can be submitted online and whether originals must be presented in person." + local,
        "where": "Registrar of Births and Deaths responsible for the original entry. Ask the issuing municipal or local registration office which registrar holds the register.",
        "mandatory": ["Evidence that establishes the error to the registrar’s satisfaction under the applicable rules."],
        "conditional": [
            "Existing certificate or registration details to help locate the entry.",
            "Ask whether the registrar needs contemporaneous hospital records, identity proof, a local correction form, or declarations.",
        ],
        "steps": [
            "Locate the registration entry and ask whether the discrepancy is in the issued copy or the register itself.",
            "If the entry is incorrect, request correction under Section 15 and follow the procedure prescribed for the original registration area.",
            "Submit the supporting evidence and ask how to track the request. Keep a receipt or reference if issued.",
            "After approval, obtain the corrected extract and verify its details before asking another issuer to update its record.",
        ],
        "fees_timing": "Forms, visit requirements, fees and turnaround depend on the registration area and the evidence needed. Ask the registrar for the official schedule and tracking method.",
        "sources": sources,
    }


def issuer_route(label):
    return {
        "title": f"If {label} contains the error",
        "online_offline": "Confirm the supported correction channel directly with the issuer of this record.",
        "where": "Start with the authority or institution printed on the document and confirm the responsible office through its official directory.",
        "mandatory": [],
        "conditional": ["Current copy of the record, verified evidence of the correct information, and any form or proof the issuer requests."],
        "steps": [
            "Ask the issuer to confirm the information in its underlying record.",
            "Request its current correction procedure, acceptable evidence, application form, and tracking instructions.",
            "Submit the request only after identifying the error. Check the corrected copy before reusing it.",
        ],
        "fees_timing": "No fee or processing time has been verified for this document and location. Confirm both with the issuer.",
        "sources": [],
    }



def profile_route():
    return {
        "title": "If your saved profile contains the error",
        "online_offline": "Open your profile in Yojna Connect to edit the corresponding answer.",
        "where": "Your Yojna Connect profile.",
        "mandatory": [],
        "conditional": ["Refer to your confirmed evidence before changing the answer."],
        "steps": ["Correct the profile field and save your changes.", "Run the document check again."],
        "fees_timing": "There is no charge to edit your profile.",
        "sources": [],
    }
