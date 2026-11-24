"""Source-keyed translations. A changed source cannot reuse an older translation."""
import re
from functools import lru_cache

TRANSLATIONS = {
    "Aadhaar; Aadhaar-linked mobile for OTP; bank account and IFSC; land ownership/revenue record or mutation details; mobile; declaration/consent.": (
        "आधार, ओटीपी के लिए आधार से जुड़ा मोबाइल, बैंक खाता और IFSC, भूमि स्वामित्व या राजस्व रिकॉर्ड अथवा नामांतरण का विवरण, मोबाइल और घोषणा या सहमति।",
        "ਆਧਾਰ, ਓਟੀਪੀ ਲਈ ਆਧਾਰ ਨਾਲ ਜੁੜਿਆ ਮੋਬਾਈਲ, ਬੈਂਕ ਖਾਤਾ ਅਤੇ IFSC, ਜ਼ਮੀਨ ਦੀ ਮਾਲਕੀ ਜਾਂ ਮਾਲ ਰਿਕਾਰਡ ਜਾਂ ਇੰਤਕਾਲ ਦਾ ਵੇਰਵਾ, ਮੋਬਾਈਲ ਅਤੇ ਘੋਸ਼ਣਾ ਜਾਂ ਸਹਿਮਤੀ।"),
    "For assisted eKYC carry Aadhaar to CSC/State Seva Kendra. State may request extra land/family verification. Ensure bank-Aadhaar/NPCI mapping.": (
        "सहायता से eKYC कराने के लिए आधार लेकर CSC या राज्य सेवा केंद्र जाएँ। राज्य भूमि या परिवार का अतिरिक्त सत्यापन माँग सकता है। बैंक खाते की आधार और NPCI से मैपिंग जाँचें।",
        "ਸਹਾਇਤਾ ਨਾਲ eKYC ਲਈ ਆਧਾਰ ਲੈ ਕੇ CSC ਜਾਂ ਰਾਜ ਸੇਵਾ ਕੇਂਦਰ ਜਾਓ। ਰਾਜ ਜ਼ਮੀਨ ਜਾਂ ਪਰਿਵਾਰ ਦੀ ਵਾਧੂ ਪੜਤਾਲ ਮੰਗ ਸਕਦਾ ਹੈ। ਬੈਂਕ ਖਾਤੇ ਦੀ ਆਧਾਰ ਅਤੇ NPCI ਨਾਲ ਮੈਪਿੰਗ ਜਾਂਚੋ।"),
    "Parivar Pehchan Patra / Family ID; Age proof (normally the age record in PPP or an accepted government age document); Haryana domicile/residence evidence if the PPP record is incomplete; Bank account/passbook and consent for PFMS validation": (
        "परिवार पहचान पत्र (PPP), आयु का प्रमाण (आमतौर पर PPP में दर्ज आयु या सरकार द्वारा स्वीकृत आयु प्रमाणपत्र), और PPP का रिकॉर्ड अधूरा होने पर हरियाणा के मूल निवास या निवास का प्रमाण रखें। PFMS सत्यापन के लिए बैंक खाता या पासबुक और सहमति भी चाहिए।",
        "ਪਰਿਵਾਰ ਪਛਾਣ ਪੱਤਰ (PPP), ਉਮਰ ਦਾ ਸਬੂਤ (ਆਮ ਤੌਰ ’ਤੇ PPP ਵਿੱਚ ਦਰਜ ਉਮਰ ਜਾਂ ਸਰਕਾਰ ਵੱਲੋਂ ਮੰਨਿਆ ਉਮਰ ਦਾ ਦਸਤਾਵੇਜ਼), ਅਤੇ ਜੇ PPP ਦਾ ਰਿਕਾਰਡ ਅਧੂਰਾ ਹੈ ਤਾਂ ਹਰਿਆਣਾ ਦੇ ਪੱਕੇ ਵਸਨੀਕ ਹੋਣ ਜਾਂ ਰਿਹਾਇਸ਼ ਦਾ ਸਬੂਤ ਰੱਖੋ। PFMS ਪੜਤਾਲ ਲਈ ਬੈਂਕ ਖਾਤਾ ਜਾਂ ਪਾਸਬੁੱਕ ਅਤੇ ਸਹਿਮਤੀ ਵੀ ਚਾਹੀਦੀ ਹੈ।"),
    "Pension/annuity statement where the applicant receives a lower pension and seeks payment of the difference; Additional income or residence proof requested by the DSWO during verification; Death/relationship proof where spouse income or household record needs correction": (
        "यदि कम पेंशन मिलती है और अंतर की राशि माँगी जा रही है तो पेंशन या वार्षिकी का विवरण दें। सत्यापन में DSWO अतिरिक्त आय या निवास प्रमाण माँग सकता है। जीवनसाथी की आय या परिवार का रिकॉर्ड सुधारना हो तो मृत्यु या रिश्ते का प्रमाण चाहिए।",
        "ਜੇ ਘੱਟ ਪੈਨਸ਼ਨ ਮਿਲਦੀ ਹੈ ਅਤੇ ਫ਼ਰਕ ਦੀ ਰਕਮ ਮੰਗੀ ਜਾ ਰਹੀ ਹੈ ਤਾਂ ਪੈਨਸ਼ਨ ਜਾਂ ਐਨੂਇਟੀ ਦੀ ਸਟੇਟਮੈਂਟ ਦਿਓ। ਪੜਤਾਲ ਦੌਰਾਨ DSWO ਵਾਧੂ ਆਮਦਨ ਜਾਂ ਰਿਹਾਇਸ਼ ਦਾ ਸਬੂਤ ਮੰਗ ਸਕਦਾ ਹੈ। ਜੀਵਨ ਸਾਥੀ ਦੀ ਆਮਦਨ ਜਾਂ ਪਰਿਵਾਰ ਦਾ ਰਿਕਾਰਡ ਸੁਧਾਰਨ ਲਈ ਮੌਤ ਜਾਂ ਰਿਸ਼ਤੇ ਦਾ ਸਬੂਤ ਚਾਹੀਦਾ ਹੈ।"),
}


@lru_cache(maxsize=768)
def translate(source, language, model, generate):
    if source in TRANSLATIONS:
        return TRANSLATIONS[source][0 if language == "hi" else 1]
    target = "Hindi (Devanagari)" if language == "hi" else "Punjabi (Gurmukhi)"
    response = generate("chat", {"model": model, "stream": False, "options": {"temperature": 0, "num_predict": 1200},
                        "messages": [{"role": "system", "content": f"Translate the entire source into {target}. Return only the translation. Preserve qualifications, literal numbers, URLs and dates. Do not answer or add advice."},
                                     {"role": "user", "content": source}]}, timeout=90)
    value = response["message"]["content"].strip()
    script = r"[\u0900-\u097f]" if language == "hi" else r"[\u0a00-\u0a7f]"
    if (response.get("done_reason") == "length" or not re.search(script, value)
            or sorted(re.findall(r"\d+", source)) != sorted(re.findall(r"\d+", value))
            or re.findall(r"https?://\S+", source) != re.findall(r"https?://\S+", value)):
        raise ValueError("Translation needs review")
    return value
