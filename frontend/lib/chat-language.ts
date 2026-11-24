export type ChatLanguage = "en" | "hi" | "pa";

const copy: Record<string, [string, string]> = {
  "Scheme assistant": ["योजना सहायक", "ਯੋਜਨਾ ਸਹਾਇਕ"],
  "Your profile details": ["आपकी प्रोफ़ाइल", "ਤੁਹਾਡੇ ਪ੍ਰੋਫ਼ਾਈਲ ਦੇ ਵੇਰਵੇ"],
  "Your question": ["आपका सवाल", "ਤੁਹਾਡਾ ਸਵਾਲ"],
  "Send": ["भेजें", "ਭੇਜੋ"], "Confirm": ["पुष्टि करें", "ਪੁਸ਼ਟੀ ਕਰੋ"], "Dismiss": ["हटाएँ", "ਹਟਾਓ"],
  "Source": ["स्रोत", "ਸਰੋਤ"], "Checked": ["जाँच की तारीख", "ਜਾਂਚ ਦੀ ਮਿਤੀ"],
  "Original wording": ["मूल पाठ देखें", "ਮੂਲ ਪਾਠ ਵੇਖੋ"],
  "Translation unavailable": ["इस अंश का अनुवाद उपलब्ध नहीं है।", "ਇਸ ਹਿੱਸੇ ਦਾ ਅਨੁਵਾਦ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।"],
  "Conditional documents": ["स्थिति के अनुसार अतिरिक्त दस्तावेज़", "ਹਾਲਾਤ ਮੁਤਾਬਕ ਵਾਧੂ ਦਸਤਾਵੇਜ਼"],
  "Review each suggestion before adding it to your profile.": ["प्रोफ़ाइल में जोड़ने से पहले हर सुझाव जाँचें।", "ਪ੍ਰੋਫ਼ਾਈਲ ਵਿੱਚ ਜੋੜਨ ਤੋਂ ਪਹਿਲਾਂ ਹਰ ਸੁਝਾਅ ਵੇਖੋ।"],
  "Use confirmed details in my profile": ["पुष्टि किए गए विवरण प्रोफ़ाइल में जोड़ें", "ਪੁਸ਼ਟੀ ਕੀਤੇ ਵੇਰਵੇ ਪ੍ਰੋਫ਼ਾਈਲ ਵਿੱਚ ਜੋੜੋ"],
  "Open profile form": ["प्रोफ़ाइल खोलें", "ਪ੍ਰੋਫ਼ਾਈਲ ਖੋਲ੍ਹੋ"],
  "State or Union Territory": ["राज्य या केंद्र शासित प्रदेश", "ਰਾਜ ਜਾਂ ਕੇਂਦਰ ਸ਼ਾਸਿਤ ਪ੍ਰਦੇਸ਼"],
  "Currently studying": ["अभी पढ़ाई कर रहे हैं", "ਇਸ ਵੇਲੇ ਪੜ੍ਹ ਰਹੇ ਹੋ"], "Farmer": ["किसान", "ਕਿਸਾਨ"],
  "Date of birth": ["जन्म तिथि", "ਜਨਮ ਮਿਤੀ"], "Marital status": ["वैवाहिक स्थिति", "ਵਿਆਹੁਤਾ ਸਥਿਤੀ"],
  "Annual household income (INR)": ["परिवार की वार्षिक आय (रुपये)", "ਪਰਿਵਾਰ ਦੀ ਸਾਲਾਨਾ ਆਮਦਨ (ਰੁਪਏ)"],
  "yes": ["हाँ","ਹਾਂ"], "no": ["नहीं","ਨਹੀਂ"], "Searching the catalogue…": ["योजनाएँ खोज रहे हैं…","ਯੋਜਨਾਵਾਂ ਲੱਭ ਰਹੇ ਹਾਂ…"],
  "Preliminary check": ["प्रारंभिक जाँच","ਮੁੱਢਲੀ ਜਾਂਚ"], "likely_eligible": ["संभावित पात्रता","ਸੰਭਾਵੀ ਯੋਗਤਾ"],
  "likely_not_eligible": ["पात्रता की शर्त मेल नहीं खाती","ਯੋਗਤਾ ਦੀ ਸ਼ਰਤ ਮੇਲ ਨਹੀਂ ਖਾਂਦੀ"],
  "needs_more_information": ["अधिक जानकारी चाहिए","ਹੋਰ ਜਾਣਕਾਰੀ ਚਾਹੀਦੀ ਹੈ"], "information_only": ["केवल जानकारी","ਸਿਰਫ਼ ਜਾਣਕਾਰੀ"],
  "Retry": ["सेवा उपलब्ध नहीं है। फिर कोशिश करें।","ਸੇਵਾ ਉਪਲਬਧ ਨਹੀਂ ਹੈ। ਮੁੜ ਕੋਸ਼ਿਸ਼ ਕਰੋ।"],
  "Confirmed": ["पुष्टि हुई", "ਪੁਸ਼ਟੀ ਹੋਈ"], "Dismissed": ["हटाया गया", "ਹਟਾਇਆ ਗਿਆ"],
  "Ask about benefits, documents or application steps in English, Hindi or Punjabi. Translations include the original catalogue wording. Leave out identity numbers.": ["लाभ, दस्तावेज़ या आवेदन के बारे में पूछें। अनुवाद के साथ मूल पाठ भी देख सकते हैं। पहचान संख्या साझा न करें।","ਲਾਭ, ਦਸਤਾਵੇਜ਼ ਜਾਂ ਅਰਜ਼ੀ ਬਾਰੇ ਪੁੱਛੋ। ਅਨੁਵਾਦ ਦੇ ਨਾਲ ਮੂਲ ਪਾਠ ਵੀ ਵੇਖ ਸਕਦੇ ਹੋ। ਪਛਾਣ ਨੰਬਰ ਸਾਂਝੇ ਨਾ ਕਰੋ।"],
  "The local language model is unavailable. Showing keyword search results.": ["भाषा मॉडल उपलब्ध नहीं है। खोज के परिणाम दिखाए गए हैं।","ਭਾਸ਼ਾ ਮਾਡਲ ਉਪਲਬਧ ਨਹੀਂ ਹੈ। ਖੋਜ ਦੇ ਨਤੀਜੇ ਵਿਖਾਏ ਗਏ ਹਨ।"],
  "Changed": ["बदला गया","ਬਦਲਿਆ ਗਿਆ"],
};
export function chatLabel(key: string, lang: ChatLanguage) {
  return lang === "en" ? key.replaceAll("_", " ") : copy[key]?.[lang === "hi" ? 0 : 1] ?? key;
}
