"""Multilingual cue lexicon for the real-time rule extractor.

Covers English, Hinglish (romanized Hindi) and Hindi (Devanagari). Patterns
run case-insensitively on *sanitized* text, so PII tags like [PHONE] and
[URL] are usable cues. Devanagari patterns avoid \\b because Python treats
combining vowel signs as non-word characters.

Add a language by appending patterns; nothing else needs to change.
"""

from __future__ import annotations

import re

from ..taxonomy import ActorClaim, RequestedAction, Signal

_ORGS = (
    r"(?:bank|head office|branch|police|cyber ?(?:cell|crime)|cbi|ncb|customs|income tax|rbi|"
    r"reserve bank|trai|telecom|law enforcement|special investigation team|social security(?: administration)?|irs|internal revenue|federal \w+|\w+ administration|office of \w+(?: \w+)?|police (?:station|headquarters)|national cyber cell|electricity(?: board| department)?|courier|fedex|dhl|blue ?dart|npci|"
    r"customer (?:care|support)|support (?:team|desk)|microsoft|windows|amazon|flipkart|paytm|phonepe|"
    r"g ?pay|google pay|uidai|crime branch|enforcement directorate|narcotics)"
)

SIGNAL_PATTERNS: dict[Signal, list[str]] = {
    Signal.AUTHORITY_CLAIM: [
        rf"\b(?:calling|speaking|call(?:ing)? you|i am|i'm|we are|this is) (?:\w+ ){{0,4}}from (?:the )?(?:\w+ ){{0,3}}{_ORGS}",
        r"\b(?:sbi|hdfc|icici|axis|kotak|pnb|canara|bank of baroda|state bank)(?: bank)? (?:head office|fraud (?:department|team|cell)|kyc (?:department|team|cell)|customer care|security team)",
        r"\b(?:cbi|ncb|ed|enforcement directorate|cyber ?crime|crime branch|mumbai police|delhi police|customs|trai)(?: department)? (?:officer|official|inspector|department|headquarters|team)",
        r"\b(?:i am|i'm|this is|speaking,?) (?:\w+ ){0,2}(?:inspector|officer|sub-inspector|dcp|investigating officer|senior manager|kyc executive|relationship manager)",
        r"\b(?:employee|badge|officer) (?:id|number) (?:is )?[a-z0-9-]+",
        rf"\bmy name is (?:\w+ ){{0,3}}from (?:the )?(?:\w+ ){{0,3}}{_ORGS}",
        rf"\b{_ORGS} (?:\w+ ){{0,2}}se (?:bol (?:raha|rahi)|baat kar (?:raha|rahi)|call kar (?:raha|rahi))",
        r"\b(?:inspector|sub-inspector|acp|dcp|sp|si|officer|constable|commissioner)\s+[a-z]+(?:\s+[a-z]+)?\s+(?:bol|baat kar) (?:raha|rahi) (?:hoon|hu|hun|hai)",
        rf"\bmain (?:\w+ ){{0,2}}{_ORGS} (?:se|ka|ki)\b",
        r"(?:बैंक|पुलिस|हेड ऑफिस|साइबर सेल|सीबीआई|कस्टम्स|बिजली विभाग|कूरियर) से (?:बोल|बात)",
        r"(?:अधिकारी|इंस्पेक्टर|ऑफिसर) (?:बोल|हूँ|हूं)",
    ],
    Signal.TRUST_BUILDING: [
        r"\b(?:i am|i'm) (?:here|calling) to help\b",
        r"\b(?:don't|do not) worry\b",
        r"\bfor your (?:own )?(?:safety|security|protection)\b",
        r"\bwe (?:are|have) (?:protecting|secured|safeguarding) your\b",
        r"\btrust me\b",
        r"\bi understand your (?:concern|fear)\b",
        r"\b(?:chinta|tension) mat (?:kijiye|karo|lijiye)\b",
        r"\bmain aapki (?:madad|help)\b",
        r"\bghabra(?:iye|o) mat\b",
        r"चिंता (?:मत|न) कर",
        r"आपकी मदद",
    ],
    Signal.REWARD_LURE: [
        r"\b(?:refund|cashback|cash back) (?:of|amount|is|has been|will be|pending|initiated|approved)",
        r"\b(?:won|winner|selected for) (?:a |the )?(?:prize|lottery|lucky draw|reward|bumper)",
        r"\blucky draw\b|\bkbc lottery\b|\blottery\b",
        r"\bearn (?:rs\.?|₹|inr)? ?\d[\d,]* ?(?:k|thousand|per day|daily|a day)?",
        r"\b(?:daily income|part[- ]time (?:job|work)|work from home|commission (?:per|on each) task|like (?:youtube )?videos and earn)",
        r"\b(?:guaranteed|assured|fixed) (?:returns?|profit)\b|\bdouble your (?:money|investment)\b",
        r"\b\d+ ?% (?:daily|weekly|monthly) (?:returns?|profit)",
        r"\b(?:inaam|inam) (?:jeeta|mila|nikla)|\bpaisa double\b|\bghar baithe kama",
        r"\brefund (?:mil|aa) (?:jayega|raha)",
        r"इनाम|लॉटरी|रिफंड|मुनाफा|घर बैठे कमा",
    ],
    Signal.URGENCY: [
        r"\b(?:within|in|next) \d+ ?(?:min|mins|minutes|hours|hrs)\b",
        r"\b(?:immediately|right now|right away|urgent(?:ly)?|asap|as soon as possible|today itself|at the earliest)\b",
        r"\bbefore (?:\d+ ?(?:pm|am)|tonight|midnight|end of (?:the )?day|it(?:'s| is) too late)",
        r"\b(?:last|final) (?:chance|warning|reminder|notice)\b",
        r"\btime is running out\b|\bno time\b|\btonight\b",
        r"\b(?:turant|fauran|abhi ke abhi|jaldi (?:karo|kijiye|kariye))\b",
        r"\b\d+ minute (?:mein|me|ke andar)\b|\baaj raat\b",
        r"तुरंत|फौरन|जल्दी|मिनट में|आज रात",
    ],
    Signal.THREAT: [
        r"\b(?:account|card|sim|number|connection|wallet|kyc)\b[^.?!]{0,30}\b(?:will be|is going to be|has been|getting|is being|be) (?:blocked|frozen|suspended|closed|deactivated|disconnected|cut)",
        r"\b(?:block|freeze|suspend|deactivate|close)(?:d)? your (?:account|card|sim|number|connection|aadhaar)",
        r"\b(?:arrest warrant|digital arrest|non-?bailable warrant|under arrest|be arrested|legal action|court case)\b",
        r"\b(?:fir|case|complaint) (?:has been |is |was )?(?:registered|filed|lodged) (?:against|in your name)",
        r"\b(?:money laundering|drugs?|narcotics|illegal (?:items|parcel|passports?)|fake passports?)\b[^.?!]{0,30}\b(?:found|seized|linked|detected|booked)",
        r"\b(?:electricity|power|gas)\b[^.?!]{0,25}\b(?:cut|disconnected)\b",
        r"\b(?:virus|malware|hacked|compromised|hackers)\b",
        r"\b(?:penalty|fine) of\b",
        r"\bsuspicious (?:activity|transactions?|login)\b[^.?!]{0,30}\b(?:on|in|with|from) your\b",
        r"\b(?:has been|have been|is|was|been|will be) (?:suspended|compromised|flagged|seized)\b",
        r"\bif you (?:don't|do not|fail to) (?:cooperate|comply|pay|act|respond)\b",
        r"\bmatter of (?:national security|great importance|utmost urgency)\b|\bwarrant (?:for|in) your\b",
        r"\b(?:band|block|freeze) ho (?:jayega|jayegi|jaega)\b|\bgiraftar\b|\barrest ho\b|\bcase darj\b|\bbijli kat\b",
        r"\b(?:freeze|block|band) kiya ja (?:sakta|raha|sakti)\b",
        r"\b(?:case|fir|complaint|criminal complaint)\b[^.?!]{0,30}\b(?:register|darj|file|receive)\w* (?:ho|hui|hua|kar|kiya)",
        r"\bfir ho (?:chuki|gayi|gaya)\b|\bsuspect (?:maana|mana|bana)\b",
        r"\b(?:illegal|asleel|obscene|pornographic|morphed|gande)\b[^.?!]{0,40}\b(?:messages?|content|material|photos?|images?|videos?|activit\w+)",
        r"\b(?:money laundering|telecom fraud|cyber fraud|financial fraud|digital fraud|cyber crime)\b[^.?!]{0,30}\b(?:case|complaint|investigation|hai|mein|kiya)",
        r"\bmisuse\b[^.?!]{0,20}\b(?:report|kiya|hua|hui)",
        r"बंद हो जाएगा|ब्लॉक हो|गिरफ्तार|केस दर्ज|कट जाएगी|फ्रीज",
    ],
    Signal.CHANNEL_SHIFT: [
        r"\b(?:come|move|switch|continue|talk|join|connect|chat|shift)\b[^.?!]{0,15}\b(?:on|to|over) (?:whatsapp|telegram|skype|signal|video call)",
        r"\b(?:whatsapp|telegram) (?:me|group|channel|karo|kijiye|pe aaiye)\b",
        r"\badd(?:ing)? you (?:to|on|in) (?:a |our |the )?(?:whatsapp|telegram)",
        r"\bcall (?:me )?(?:back )?on (?:this|my|another|the following|the given) (?:number|line|whatsapp)",
        r"\bcall (?:me )?(?:back )?(?:on |at )?\[PHONE\]",
        r"\b(?:only|directly) on this number\b",
        r"\b(?:join|connect to|come on) (?:the |this |a )?(?:video|skype) call\b|\bvideo call (?:verification|statement|enquiry)\b",
        r"\b(?:whatsapp|telegram) (?:pe|par) (?:aao|aaiye|baat|call|message)",
        r"\bis number (?:pe|par) (?:call|baat)",
        r"व्हाट्सएप पर|टेलीग्राम पर|वीडियो कॉल",
    ],
    Signal.ISOLATION: [
        r"\b(?:don't|do not|dont) (?:disconnect|hang up|cut the call|end the call|put the phone down)\b",
        r"\bstay on (?:the )?(?:line|call)\b|\bkeep (?:the|your) (?:call|line|camera|video) on\b",
        r"\b(?:alone|by yourself) in (?:a|the|your) room\b|\b(?:lock|close) (?:the|your) (?:door|room)\b",
        r"\b(?:don't|do not) (?:leave|go out|step out|let anyone in)\b",
        r"\b(?:call|phone) mat (?:kaatna|kaato|kaatiye|katna|rakhna)\b|\bakele (?:raho|rahiye|baithiye)\b",
        r"फोन मत काट|कॉल मत काट|अकेले",
    ],
    Signal.SECRECY: [
        r"\b(?:keep|is|be) (?:it |this |the matter )?(?:strictly )?(?:confidential|secret)\b",
        r"\b(?:don't|do not|dont|never) (?:tell|inform|involve|share this with|discuss (?:this )?with) (?:anyone|anybody|your family|your (?:wife|husband|son|daughter|parents|friends)|others)",
        r"\b(?:national secret|confidential (?:investigation|matter|case|enquiry)|official secrets act)\b",
        r"\bkisi ko (?:mat|nahi|na) (?:batana|batao|bataiye|batayein)\b|\bgupt rakh|\bsecret rakh",
        r"किसी को (?:मत|न|नहीं) बता|गोपनीय",
    ],
    Signal.VERIFICATION_DISCOURAGEMENT: [
        r"\b(?:no need|don't need|do not need) to (?:call|visit|go to|contact|check with) (?:the |your )?(?:bank|branch|customer care|police)",
        r"\b(?:don't|do not) (?:call|visit|go to|contact) (?:the |your )?(?:bank|branch|customer care|police station|local police)",
        r"\b(?:branch|bank) (?:staff|people|employees) (?:are|is|may be) (?:involved|corrupt|not aware)",
        r"\b(?:don't|do not) trust (?:anyone|the branch|bank staff|other numbers)",
        r"\b(?:don't|do not) (?:verify|check|confirm) (?:it |this )?(?:with|anywhere|elsewhere)",
        r"\bbank (?:jaane|call karne) ki (?:zaroorat|jarurat) nahi\b|\bbranch mat (?:jaana|jaiye)\b",
        r"बैंक जाने की (?:जरूरत|ज़रूरत) नहीं|ब्रांच मत",
    ],
    Signal.REMOTE_ACCESS: [
        r"\b(?:any ?desk|team ?viewer|quick ?support|rust ?desk|airdroid|ammyy|ultraviewer)\b",
        r"\b(?:share (?:your )?screen|screen ?shar(?:e|ing))\b",
        r"\bremote (?:access|support|control|app)\b",
        r"\b(?:install|download|open) (?:this|the|an?|one|our) (?:\w+ ){0,2}(?:app|application|apk|software|file)\b",
        r"\.apk\b|\[URL\][^.?!]{0,20}\b(?:install|download)",
        r"\b(?:\d[- ]digit|9 digit) (?:code|id|address) (?:on|in|from) (?:the|your) (?:app|screen)",
        r"\bapp (?:install|download) (?:karo|kijiye|kar lijiye|kariye)\b",
        r"ऐप (?:डाउनलोड|इंस्टॉल)|स्क्रीन शेयर|एनीडेस्क",
    ],
    Signal.CREDENTIAL_REQUEST: [
        r"\b(?:tell|share|give|read|send|say|confirm|provide|enter|type|forward)\b (?:me |us )?(?:the |your |that |this )?(?:\w+ ){0,2}(?:otp|one[- ]time password|m?pin|upi pin|atm pin|cvv|password|net ?banking (?:id|password)|login (?:id|details)|verification code|\d[- ]digit code|card number|expiry date)",
        r"\bwhat is (?:the |your )?(?:otp|pin|cvv|code|password)\b",
        r"\b(?:you will|you'll|you have) (?:get|receive|received) an? (?:otp|code|sms)\b[^.?!]{0,30}\b(?:tell|share|read|give)",
        r"\b(?:otp|pin|cvv|password|code) (?:bata(?:o|iye|dijiye|na)|bhej(?:o|iye|dijiye)|share kar(?:o|iye|dijiye)|dijiye)\b",
        r"(?:ओटीपी|पिन|पासवर्ड|सीवीवी) (?:बता|भेज|दीजिए)",
    ],
    Signal.PERSONAL_INFO_REQUEST: [
        r"\b(?:share|send|give|tell|provide|upload|confirm|verify)\b (?:me |us )?(?:the |your )?(?:\w+ ){0,1}(?:aadhaa?r|pan(?: card)?|social security number|ssn|date of birth|dob|mother'?s maiden name|kyc documents?|selfie|photo id|address proof|account number)",
        r"\b(?:aadhaa?r|pan) (?:number|details|card)? ?(?:batao|bataiye|bhejo|bhejiye|dijiye|share kar)",
        r"\b(?:identity|kyc|documents?) verify kar(?:ni|na|ne) (?:hogi|hoga|padegi|padega)|\bpolice verification\b",
        r"(?:आधार|पैन) (?:नंबर|कार्ड)? ?(?:बता|भेज|दीजिए)",
    ],
    Signal.PAYMENT_REQUEST: [
        r"\b(?:transfer|send|pay|deposit|move|remit)\b[^.?!]{0,40}\b(?:account|upi|wallet|amount|money|funds|fee|charges|rupees|rs\.?|₹|lakh|\[UPI\]|\[ACCOUNT\])",
        r"\b(?:safe|secure|rbi|government|escrow) (?:account|vault|wallet)\b",
        r"\b(?:verification|processing|registration|clearance|release|security|customs|activation) (?:fee|charges?|amount|deposit)\b",
        r"\bscan (?:this|the|my) qr\b|\bqr code (?:scan|bhej)|\bapprove the (?:collect |payment )?request\b|\benter (?:your )?upi pin to (?:receive|get)",
        r"\b(?:paise|paisa|amount|rupaye) (?:transfer|bhejo|bhejiye|daalo|daaliye|jama)\b|\bpayment (?:karo|kijiye|kar dijiye)\b|\bfee (?:bharo|bhariye|jama)\b",
        r"पैसे (?:ट्रांसफर|भेज)|भुगतान कर|फीस जमा|रकम भेज",
    ],
    Signal.SAFETY_ADVICE: [
        r"\b(?:never|do not|don't) (?:share|disclose|give|tell)\b[^.?!]{0,20}\b(?:otp|pin|password|cvv)\b[^.?!]{0,30}(?:anyone|anybody|bank|with)",
        r"\b(?:we|the bank|bank|rbi) (?:will )?never (?:ask|call|request)\b",
        r"\bcall the (?:number|helpline) (?:on|printed on) (?:the back of )?your card\b",
        r"\b(?:visit|go to) your (?:nearest|home) branch\b",
        r"\breport (?:it |this )?(?:to|at|on) (?:1930|cybercrime\.gov\.in|the cyber helpline)",
        r"\b(?:hang up|disconnect) and call (?:your bank|the official)",
        r"\botp kisi (?:ko|se) (?:mat|na|nahi) (?:batayein|batana|share)",
        r"ओटीपी किसी को (?:न|मत) बता",
    ],
}

# Request-type signals that flip meaning when negated ("do not share your OTP").
NEGATABLE = {
    Signal.CREDENTIAL_REQUEST, Signal.PERSONAL_INFO_REQUEST, Signal.PAYMENT_REQUEST,
    Signal.REMOTE_ACCESS,
}
NEGATION = re.compile(r"(?:\bnever|\bdon'?t|\bdo not|\bnot|\bmat|\bna|\bnahi|मत|न|नहीं)\W+(?:\w+\W+){0,2}$", re.I)

ACTOR_PATTERNS: list[tuple[ActorClaim, str]] = [
    (ActorClaim.LAW_ENFORCEMENT, r"\b(?:police|cbi|ncb|cyber ?(?:crime|cell)|crime branch|enforcement directorate|inspector|narcotics|customs officer)\b|पुलिस|सीबीआई|साइबर"),
    (ActorClaim.GOVERNMENT, r"\b(?:income tax|uidai|government|ministry|court|customs department)\b"),
    (ActorClaim.TELECOM, r"\b(?:trai|sim card|sim will|airtel|jio|vodafone|telecom)\b"),
    (ActorClaim.PAYMENT_APP, r"\b(?:paytm|phonepe|g ?pay|google pay|bhim|upi (?:support|helpline|team))\b"),
    (ActorClaim.BANK, r"\b(?:bank|sbi|hdfc|icici|axis|kotak|pnb|rbi|reserve bank|credit card department|net ?banking)\b|बैंक"),
    (ActorClaim.COURIER, r"\b(?:courier|fedex|dhl|blue ?dart|parcel|shipment|consignment)\b|कूरियर|पार्सल"),
    (ActorClaim.UTILITY, r"\b(?:electricity|bijli|power department|gas (?:agency|connection)|meter)\b|बिजली"),
    (ActorClaim.TECH_SUPPORT, r"\b(?:microsoft|windows support|tech(?:nical)? support|apple support|antivirus)\b"),
    (ActorClaim.EMPLOYER, r"\b(?:hr (?:team|department|manager)|recruit\w*|hiring|part[- ]time (?:job|work)|job offer|task)\b"),
    (ActorClaim.INVESTMENT, r"\b(?:invest\w*|trading|crypto|stock (?:tips|market)|ipo|forex)\b"),
    (ActorClaim.LOTTERY, r"\b(?:lottery|lucky draw|kbc|prize)\b|लॉटरी"),
    (ActorClaim.FAMILY_OR_FRIEND, r"\b(?:it'?s me,? your|i am your|main tumhara|main aapka) (?:son|daughter|nephew|niece|friend|cousin|beta|bhai|bhanja)\b"),
]

ACTION_PATTERNS: list[tuple[RequestedAction, str]] = [
    (RequestedAction.SCAN_QR, r"\bscan (?:this|the|my) qr\b|\bqr code\b|\bapprove the (?:collect )?request\b"),
    (RequestedAction.SHARE_OTP, r"\b(?:otp|one[- ]time password|verification code|\d[- ]digit code)\b|ओटीपी"),
    (RequestedAction.CLICK_LINK, r"\b(?:click|open|tap) (?:on )?(?:the |this )?(?:link|\[URL\])"),
    (RequestedAction.CALL_NUMBER, r"\bcall (?:me )?(?:back )?(?:on |at )?(?:\[PHONE\]|this number|the number)"),
]

ENTITY_PATTERNS: list[tuple[str, str]] = [
    ("APP", r"\b(?:any ?desk|team ?viewer|quick ?support|rust ?desk|airdroid|ultraviewer)\b"),
    ("CHANNEL", r"\b(?:whatsapp|telegram|skype|video call|sms|signal app)\b"),
    ("AMOUNT", r"(?:₹|rs\.?|inr) ?\d[\d,]*(?:\.\d+)?(?: ?(?:lakh|crore|k))?|\b\d[\d,]* ?(?:rupees|rupaye|lakh|crore)\b"),
    ("DEADLINE", r"\b\d+ ?(?:min|mins|minutes|hours|hrs)\b|\btonight\b|\bmidnight\b"),
    ("ORG", r"\b(?:sbi|hdfc|icici|axis|kotak|pnb|rbi|cbi|ncb|trai|uidai|fedex|dhl|blue ?dart|paytm|phonepe|google pay|microsoft|amazon|flipkart|airtel|jio)\b"),
    ("PHONE", r"\[PHONE\]"), ("UPI", r"\[UPI\]"), ("ACCOUNT", r"\[ACCOUNT\]"),
    ("URL", r"\[URL\]"), ("EMAIL", r"\[EMAIL\]"), ("ID_DOC", r"\[(?:AADHAAR|PAN)\]"),
]


def compile_all() -> tuple[dict[Signal, list[re.Pattern[str]]], list, list, list]:
    sig = {s: [re.compile(p, re.I) for p in ps] for s, ps in SIGNAL_PATTERNS.items()}
    actors = [(a, re.compile(p, re.I)) for a, p in ACTOR_PATTERNS]
    actions = [(a, re.compile(p, re.I)) for a, p in ACTION_PATTERNS]
    ents = [(t, re.compile(p, re.I)) for t, p in ENTITY_PATTERNS]
    return sig, actors, actions, ents
