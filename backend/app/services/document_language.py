"""Normalisation shared by multilingual extraction and comparisons."""

from unicodedata import decimal, name, normalize

from text_unidecode import unidecode


def ascii_digits(text: str) -> str:
    return "".join(str(decimal(char)) if char.isdecimal() else char for char in text)


def detected_language(text: str) -> str | None:
    scripts = set()
    for char in text:
        if not char.isalpha():
            continue
        if "\u0900" <= char <= "\u097f":
            scripts.add("Hindi")
        elif "\u0a00" <= char <= "\u0a7f":
            scripts.add("Punjabi")
        elif "LATIN" in name(char, ""):
            scripts.add("English")
    if len(scripts) == 1:
        return scripts.pop()
    return "Mixed" if scripts else None


ALIASES = {
    "gender": {
        "male": ("m", "boy", "पुरुष", "ਪੁਰਸ਼", "ਮਰਦ"),
        "female": ("f", "girl", "महिला", "स्त्री", "ਔਰਤ", "ਇਸਤਰੀ"),
    },
    "state": {
        "punjab": ("पंजाब", "ਪੰਜਾਬ"),
        "haryana": ("हरियाणा", "ਹਰਿਆਣਾ"),
        "chandigarh": ("चंडीगढ़", "चण्डीगढ़", "ਚੰਡੀਗੜ੍ਹ"),
        "himachal pradesh": ("हिमाचल प्रदेश", "ਹਿਮਾਚਲ ਪ੍ਰਦੇਸ਼"),
        "delhi": ("दिल्ली", "ਦਿੱਲੀ", "new delhi", "नई दिल्ली", "ਨਵੀਂ ਦਿੱਲੀ"),
        "rajasthan": ("राजस्थान", "ਰਾਜਸਥਾਨ"),
        "uttar pradesh": ("उत्तर प्रदेश", "ਉੱਤਰ ਪ੍ਰਦੇਸ਼"),
    },
    "district": {
        "ludhiana": ("लुधियाना", "ਲੁਧਿਆਣਾ"),
        "amritsar": ("अमृतसर", "ਅੰਮ੍ਰਿਤਸਰ"),
        "jalandhar": ("जालंधर", "ਜਲੰਧਰ"),
        "patiala": ("पटियाला", "ਪਟਿਆਲਾ"),
        "ambala": ("अंबाला", "अम्बाला", "ਅੰਬਾਲਾ"),
        "karnal": ("करनाल", "ਕਰਨਾਲ"),
        "hisar": ("हिसार", "ਹਿਸਾਰ"),
    },
    "social_category": {
        "sc": ("अनुसूचित जाति", "ਅਨੁਸੂਚਿਤ ਜਾਤੀ", "scheduled caste"),
        "st": ("अनुसूचित जनजाति", "ਅਨੁਸੂਚਿਤ ਜਨਜਾਤੀ", "scheduled tribe"),
        "obc": ("अन्य पिछड़ा वर्ग", "ਹੋਰ ਪੱਛੜਾ ਵਰਗ", "other backward class"),
        "ews": ("आर्थिक रूप से कमजोर वर्ग", "ਆਰਥਿਕ ਤੌਰ ਤੇ ਕਮਜ਼ੋਰ ਵਰਗ", "economically weaker section"),
    },
}
CANONICAL = {
    field: {normalize("NFKC", alias): canonical for canonical, aliases in groups.items() for alias in aliases}
    for field, groups in ALIASES.items()
}
CANONICAL["city"] = {**CANONICAL["state"], **CANONICAL["district"]}


def english_display(field: str, value: str) -> str:
    text = ascii_digits(normalize("NFKC", value))
    canonical = CANONICAL.get(field, {}).get(" ".join(text.casefold().split()))
    if canonical:
        return canonical.upper() if field == "social_category" else canonical.title()
    if text.isascii():
        return text
    # Proper names are transliterated. The English spelling is for display only.
    transliterated = " ".join(unidecode(text).split())
    return transliterated.title() if transliterated else text
