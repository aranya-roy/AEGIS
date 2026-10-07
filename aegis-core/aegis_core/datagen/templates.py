"""Span-annotated utterance templates.

Markup: [[CODE:text]] marks a manipulation-signal span; the rendered text
of that span is the gold evidence quote. {slot} fields are filled by the
generator (brands, amounts, fake PII). Templates are written per *move*
(a workflow step) and language, so conversations can be recombined in many
orders, brands, channels and languages - the goal is workflow
generalization, not phrase memorization.

Wording is deliberately varied and NOT copied from the rule lexicon; the
hand-written held-out set in data/heldout/ is the honest test anyway.
"""

from __future__ import annotations

CODES = {
    "AUT": "AUTHORITY_CLAIM", "TRS": "TRUST_BUILDING", "LUR": "REWARD_LURE",
    "URG": "URGENCY", "THR": "THREAT", "CHN": "CHANNEL_SHIFT", "ISO": "ISOLATION",
    "SEC": "SECRECY", "NOV": "VERIFICATION_DISCOURAGEMENT", "RMT": "REMOTE_ACCESS",
    "CRD": "CREDENTIAL_REQUEST", "PII": "PERSONAL_INFO_REQUEST", "PAY": "PAYMENT_REQUEST",
    "SAF": "SAFETY_ADVICE",
}

# move -> lang -> list of templates
T: dict[str, dict[str, list[str]]] = {
    # ---------- openings / authority ----------
    "OPEN_BANK": {
        "en": [
            "Good afternoon {victim}, [[AUT:this is {agent} calling from {brand} head office]], fraud monitoring team.",
            "Hello, am I speaking with {victim}? [[AUT:I am {agent}, senior manager at {brand} KYC department]].",
            "[[AUT:I'm calling from the {brand} security team]] regarding a transaction on your account ending {acct4}.",
        ],
        "hinglish": [
            "Namaste {victim} ji, [[AUT:main {brand} head office se bol raha hoon]], mera naam {agent} hai.",
            "Hello sir, [[AUT:{brand} bank se baat kar raha hoon]], aapke account ending {acct4} pe ek issue hai.",
        ],
        "hi": [
            "नमस्ते {victim} जी, [[AUT:मैं {brand} बैंक से बोल रहा हूँ]], मेरा नाम {agent} है।",
        ],
    },
    "OPEN_PAYAPP": {
        "en": [
            "Hi, [[AUT:this is {agent} from {brand} customer support]]. You raised a complaint about a failed payment?",
            "[[AUT:I am calling from {brand} support desk]] about your pending refund request.",
        ],
        "hinglish": ["Hello ji, [[AUT:main {brand} customer care se bol raha hoon]], aapki complaint ke baare mein."],
        "hi": ["नमस्ते, [[AUT:मैं {brand} कस्टमर केयर से बात कर रहा हूँ]]।"],
    },
    "OPEN_COURIER": {
        "en": [
            "Hello, [[AUT:this is {agent} calling from {brand} courier]]. A parcel booked in your name has been held at Mumbai customs.",
            "[[AUT:I am from {brand} international shipments]]. Your package to Taiwan was stopped by customs.",
        ],
        "hinglish": ["Hello, [[AUT:main {brand} courier se bol raha hoon]], aapke naam ka ek parcel customs mein ruka hai."],
        "hi": ["नमस्ते, [[AUT:मैं {brand} कूरियर से बोल रहा हूँ]], आपके नाम का पार्सल कस्टम्स में रुका है।"],
    },
    "OPEN_POLICE": {
        "en": [
            "[[AUT:This is Inspector {agent} from {police} cyber crime branch]]. I am connecting you to the investigating officer.",
            "[[AUT:I'm calling from the {police} police headquarters]], narcotics division. Your Aadhaar is linked to a case.",
        ],
        "hinglish": ["[[AUT:Main {police} police se Inspector {agent} baat kar raha hoon]], aapke Aadhaar pe case hai."],
        "hi": ["[[AUT:मैं {police} पुलिस से इंस्पेक्टर {agent} बोल रहा हूँ]]।"],
    },
    "OPEN_TELECOM": {
        "en": [
            "[[AUT:This call is from {brand} telecom department]]. Your mobile number is registered for illegal activity.",
            "Hello, [[AUT:I'm calling from {brand} on behalf of TRAI]] regarding your SIM verification.",
        ],
        "hinglish": ["[[AUT:Main {brand} telecom department se bol raha hoon]], aapke SIM pe complaint aayi hai."],
        "hi": ["[[AUT:मैं {brand} टेलीकॉम विभाग से बोल रहा हूँ]], आपके सिम पर शिकायत है।"],
    },
    "OPEN_UTILITY": {
        "en": [
            "Dear customer, [[AUT:this is {brand} electricity office]]. Your last month bill is not updated in our system.",
        ],
        "hinglish": ["[[AUT:Main {brand} bijli vibhag se bol raha hoon]], aapka pichhla bill update nahi hua hai."],
        "hi": ["प्रिय ग्राहक, [[AUT:मैं {brand} बिजली विभाग से बोल रहा हूँ]], आपका बिल अपडेट नहीं हुआ है।"],
    },
    "OPEN_TECH": {
        "en": [
            "Hello, [[AUT:I'm calling from {brand} technical support]]. We detected unusual activity from your computer.",
        ],
        "hinglish": ["Hello sir, [[AUT:main {brand} technical support se bol raha hoon]], aapke computer se alert aaya hai."],
        "hi": ["[[AUT:मैं {brand} टेक्निकल सपोर्ट से बोल रहा हूँ]], आपके कंप्यूटर से अलर्ट आया है।"],
    },
    "OPEN_FAMILY": {
        "en": ["Hello? [[AUT:It's me, your nephew]], I'm calling from a friend's phone, mine is broken."],
        "hinglish": ["Hello mama ji, [[AUT:main aapka bhanja bol raha hoon]], ye dost ka number hai."],
        "hi": ["हैलो, [[AUT:मैं आपका भांजा बोल रहा हूँ]], ये दोस्त का नंबर है।"],
    },
    # ---------- lures ----------
    "LURE_REFUND": {
        "en": [
            "[[LUR:A refund of Rs {amount} has been approved]] for your failed transaction.",
            "Good news, [[LUR:your cashback of ₹{amount} is pending]] and I will process it now.",
        ],
        "hinglish": ["Aapka [[LUR:refund mil jayega, Rs {amount}]], bas ek process complete karna hai."],
        "hi": ["आपका [[LUR:{amount} रुपये का रिफंड]] मंजूर हो गया है।"],
    },
    "LURE_JOB": {
        "en": [
            "We are hiring for a part-time role. [[LUR:You can earn ₹{amount} daily just by rating hotels]] from home.",
            "[[LUR:Simple work from home, commission on each task]], payment same day.",
        ],
        "hinglish": ["[[LUR:Ghar baithe kamaiye ₹{amount} roz]], sirf YouTube videos like karne hain."],
        "hi": ["[[LUR:घर बैठे कमाइए {amount} रुपये रोज़]], बस वीडियो लाइक करने हैं।"],
    },
    "LURE_INVEST": {
        "en": [
            "Our members are getting [[LUR:guaranteed returns of 8% weekly]] on this IPO allotment scheme.",
            "With our VIP trading group [[LUR:you can double your money in 30 days]].",
        ],
        "hinglish": ["Is scheme mein [[LUR:paisa double ho jayega ek mahine mein]], guaranteed."],
        "hi": ["इस स्कीम में [[LUR:एक महीने में मुनाफा दोगुना]] होगा।"],
    },
    "LURE_PRIZE": {
        "en": ["Congratulations! [[LUR:Your number has won the KBC lucky draw of ₹{amount}]]."],
        "hinglish": ["Badhai ho! [[LUR:Aapka number lucky draw mein jeeta hai]], ₹{amount} ka inaam."],
        "hi": ["बधाई हो! [[LUR:आपने {amount} रुपये की लॉटरी जीती है]]।"],
    },
    "TRUST": {
        "en": [
            "[[TRS:Don't worry sir, I am here to help you]], this is a routine process.",
            "[[TRS:For your own safety]] we have temporarily held the transaction.",
        ],
        "hinglish": ["[[TRS:Aap chinta mat kijiye]], main aapki help karunga."],
        "hi": ["[[TRS:आप चिंता मत कीजिए]], मैं आपकी मदद करूँगा।"],
    },
    # ---------- pressure ----------
    "THREAT_ACCOUNT": {
        "en": [
            "Due to incomplete KYC [[THR:your account will be blocked]] [[URG:within 30 minutes]].",
            "If not verified, [[THR:all your cards will be frozen]] [[URG:today itself]].",
        ],
        "hinglish": ["KYC pending hai, [[THR:account block ho jayega]] [[URG:aaj raat]] tak."],
        "hi": ["केवाईसी अधूरी है, [[THR:आपका खाता बंद हो जाएगा]], [[URG:तुरंत]] अपडेट कीजिए।"],
    },
    "THREAT_LEGAL": {
        "en": [
            "[[THR:Drugs and fake passports were found]] in the parcel. [[THR:An FIR has been registered against you]].",
            "Sir, [[THR:a non-bailable warrant is issued in your name]] for money laundering. [[URG:You must respond immediately]].",
        ],
        "hinglish": ["Aapke naam pe [[THR:case darj hua hai]], [[THR:giraftar]] bhi ho sakte hain."],
        "hi": ["आपके नाम पर [[THR:केस दर्ज हुआ है]], आपको [[THR:गिरफ्तार]] किया जा सकता है।"],
    },
    "THREAT_SIM": {
        "en": ["[[THR:Your SIM will be deactivated]] [[URG:in 2 hours]] if you don't complete verification."],
        "hinglish": ["[[THR:Aapka SIM block ho jayega]] [[URG:2 ghante mein]]."],
        "hi": ["[[THR:आपका सिम ब्लॉक हो जाएगा]], [[URG:जल्दी]] कीजिए।"],
    },
    "THREAT_POWER": {
        "en": ["[[THR:Your electricity will be disconnected]] [[URG:tonight at 9:30 pm]]."],
        "hinglish": ["[[THR:Aaj raat bijli kat jayegi]], [[URG:turant]] update kariye."],
        "hi": ["[[THR:आज रात बिजली कट जाएगी]], [[URG:तुरंत]] बिल अपडेट कीजिए।"],
    },
    "THREAT_VIRUS": {
        "en": ["[[THR:Your computer is infected with a virus and hackers are stealing your bank data]]."],
        "hinglish": ["[[THR:Aapke computer mein virus hai]], bank details hack ho rahi hain."],
        "hi": ["[[THR:आपके कंप्यूटर में वायरस है]], बैंक डिटेल्स चोरी हो रही हैं।"],
    },
    "URGENCY_FAMILY": {
        "en": ["I had an accident, [[URG:I need money right now]] for the hospital."],
        "hinglish": ["Mera accident ho gaya, [[URG:abhi ke abhi]] paise chahiye hospital ke liye."],
        "hi": ["मेरा एक्सीडेंट हो गया है, [[URG:अभी]] पैसे चाहिए।"],
    },
    # ---------- isolation ----------
    "CHANNEL": {
        "en": [
            "[[CHN:Please continue this on WhatsApp]], I'm sending the official notice there.",
            "[[CHN:Call me back on {phone}]], this is my direct line.",
            "For the statement [[CHN:you must join a video call with the officer]] on Skype.",
            "[[CHN:I'm adding you to our Telegram group]] for the next steps.",
        ],
        "hinglish": [
            "[[CHN:WhatsApp pe aaiye]], wahan notice bhejta hoon.",
            "[[CHN:Is number pe call kariye {phone}]], ye mera direct line hai.",
        ],
        "hi": ["[[CHN:व्हाट्सएप पर]] आइए, वहाँ नोटिस भेजता हूँ।"],
    },
    "ISOLATION": {
        "en": [
            "[[ISO:Do not disconnect this call]] until the verification is complete.",
            "[[ISO:Sit alone in a room and keep the camera on]] during the enquiry.",
        ],
        "hinglish": ["[[ISO:Call mat kaatna]], verification chal raha hai."],
        "hi": ["[[ISO:फोन मत काटिए]], वेरिफिकेशन चल रहा है।"],
    },
    "SECRECY": {
        "en": [
            "This is a confidential investigation, [[SEC:do not tell anyone, not even your family]].",
            "[[SEC:Keep this strictly confidential]], otherwise you'll be charged too.",
        ],
        "hinglish": ["[[SEC:Ghar mein kisi ko mat batana]], ye secret investigation hai."],
        "hi": ["[[SEC:घर में किसी को मत बताइए]], यह गोपनीय जांच है।"],
    },
    "NOVERIFY": {
        "en": [
            "[[NOV:There is no need to visit the branch]], the branch staff are not aware of this case.",
            "[[NOV:Don't call the bank helpline]], it will delay your case.",
        ],
        "hinglish": ["[[NOV:Bank jaane ki zaroorat nahi]], sab yahin ho jayega."],
        "hi": ["[[NOV:बैंक जाने की ज़रूरत नहीं]], सब फोन पर हो जाएगा।"],
    },
    # ---------- compliance ----------
    "REMOTE": {
        "en": [
            "Please [[RMT:install the AnyDesk app from Play Store]] and tell me the 9 digit code.",
            "I'm sending a link, [[RMT:download this support app]] so I can fix it from my side.",
            "[[RMT:Open screen sharing]] so I can guide you step by step.",
        ],
        "hinglish": ["[[RMT:Play Store se QuickSupport app install kijiye]], main guide karta hoon."],
        "hi": ["[[RMT:प्ले स्टोर से एनीडेस्क ऐप डाउनलोड]] कीजिए।"],
    },
    "CRED_OTP": {
        "en": [
            "You just got an SMS, [[CRD:read me the 6 digit code]] to cancel the transaction.",
            "[[CRD:Tell me the OTP you received]] so I can stop the debit.",
        ],
        "hinglish": ["Aapke phone pe ek code aaya hoga, [[CRD:woh OTP bata dijiye]]."],
        "hi": ["आपके फोन पर कोड आया होगा, [[CRD:वो ओटीपी बताइए]]।"],
    },
    "CRED_PIN": {
        "en": ["For verification [[CRD:enter your UPI PIN]] on the screen now.", "[[CRD:Confirm your card number and CVV]] for re-activation."],
        "hinglish": ["Verification ke liye [[CRD:apna UPI PIN daaliye]]."],
        "hi": ["वेरिफिकेशन के लिए [[CRD:अपना पिन बताइए]]।"],
    },
    "PERSONAL": {
        "en": ["[[PII:Send me a photo of your Aadhaar card]] for verification.", "[[PII:Confirm your PAN number and date of birth]]."],
        "hinglish": ["[[PII:Aadhaar number bataiye]] verification ke liye."],
        "hi": ["वेरिफिकेशन के लिए [[PII:आधार नंबर बताइए]]।"],
    },
    "PAY_SAFE": {
        "en": [
            "To protect your savings, [[PAY:transfer the full balance to this RBI safe account]] {acct}.",
            "[[PAY:Move Rs {amount} to the verification account]], it will be refunded after the enquiry.",
        ],
        "hinglish": ["Saving bachane ke liye [[PAY:paise transfer kijiye is safe account mein]]."],
        "hi": ["अपनी बचत बचाने के लिए [[PAY:पैसे इस सुरक्षित खाते में ट्रांसफर]] कीजिए।"],
    },
    "PAY_FEE": {
        "en": [
            "There is a small [[PAY:processing fee of ₹{amount}]], pay it to {upi} to release the amount.",
            "To unlock withdrawal [[PAY:deposit Rs {amount} as security deposit]] first.",
        ],
        "hinglish": ["Bas [[PAY:₹{amount} fee jama kijiye]] {upi} pe, phir amount release hoga."],
        "hi": ["बस [[PAY:{amount} रुपये फीस जमा]] कीजिए।"],
    },
    "PAY_QR": {
        "en": ["To receive the refund, [[PAY:scan this QR code and enter your UPI PIN]]."],
        "hinglish": ["Refund lene ke liye [[PAY:ye QR code scan kariye]]."],
        "hi": ["रिफंड के लिए [[PAY:ये क्यूआर कोड स्कैन]] कीजिए।"],
    },
    "PAY_FAMILY": {
        "en": ["[[PAY:Please send ₹{amount} to {upi}]], I'll return it tomorrow."],
        "hinglish": ["[[PAY:₹{amount} bhej do {upi} pe]], kal lauta dunga."],
        "hi": ["[[PAY:{amount} रुपये भेज दो]] {upi} पर, कल लौटा दूँगा।"],
    },
    # ---------- benign ----------
    "BENIGN_BANK_OPEN": {
        "en": ["Hello, this is an automated alert from {brand}. A card transaction of ₹{amount} was attempted."],
        "hinglish": ["Namaste, ye {brand} ki taraf se alert hai, ₹{amount} ka transaction hua hai."],
        "hi": ["नमस्ते, यह {brand} की ओर से अलर्ट है, {amount} रुपये का लेनदेन हुआ है।"],
    },
    "BENIGN_BANK_SAFETY": {
        "en": [
            "If you did not do this, block the card in the app. [[SAF:We will never ask for your OTP or PIN]].",
            "Please [[SAF:call the number printed on the back of your card]] for any dispute.",
        ],
        "hinglish": ["Yaad rakhiye, [[SAF:OTP kisi ko na batayein]], bank bhi nahi poochta."],
        "hi": ["ध्यान दें, [[SAF:ओटीपी किसी को न बताएं]]।"],
    },
    "BENIGN_DELIVERY": {
        "en": ["Hi, I'm the delivery partner for your {brand} order, I'm at the gate. Should I leave it with security?"],
        "hinglish": ["Sir {brand} ka order hai, main gate pe hoon, security ko de doon?"],
        "hi": ["सर {brand} का ऑर्डर है, मैं गेट पर हूँ।"],
    },
    "BENIGN_SUPPORT": {
        "en": ["Thanks for calling {brand} support, I see your ticket about the delayed refund. It will reflect in 3 to 5 working days."],
        "hinglish": ["{brand} support mein call karne ke liye dhanyavaad, aapka refund 3-5 din mein aa jayega."],
        "hi": ["{brand} सपोर्ट में कॉल करने के लिए धन्यवाद, आपका रिफंड 3-5 दिन में आएगा।"],
    },
    "BENIGN_FRIEND": {
        "en": ["Hey, are we still meeting for dinner on Saturday? I booked the table for eight.", "Did you watch the match yesterday? What a finish."],
        "hinglish": ["Arre Saturday ko dinner pe mil rahe hain na? Table book kar diya hai."],
        "hi": ["शनिवार को डिनर पर मिल रहे हैं ना? टेबल बुक कर दिया है।"],
    },
    "BENIGN_BILL": {
        "en": ["Your {brand} bill of ₹{amount} is due on the 15th. You can pay it in the official app or at the office."],
        "hinglish": ["Aapka {brand} bill ₹{amount} 15 tareekh tak due hai, official app se pay kar sakte hain."],
        "hi": ["आपका {brand} बिल {amount} रुपये 15 तारीख तक देय है।"],
    },
    "SMALLTALK": {
        "en": ["Sir, can you hear me clearly?", "Just one moment, I'm checking your records.", "Okay, noted."],
        "hinglish": ["Sir awaaz aa rahi hai?", "Ek minute, records check kar raha hoon."],
        "hi": ["सर आवाज़ आ रही है?", "एक मिनट, रिकॉर्ड देख रहा हूँ।"],
    },
}

VICTIM: dict[str, list[str]] = {
    "en": ["Okay.", "What happened?", "Is this really from the bank?", "Oh no, what should I do?", "Alright, I'm doing it.", "Wait, why do you need that?", "Yes, I'm listening.", "Fine, go ahead.", "Hmm, okay sir."],
    "hinglish": ["Haan ji.", "Kya hua?", "Sach mein bank se ho?", "Theek hai, kar raha hoon.", "Kyun chahiye ye?", "Achha ji."],
    "hi": ["हाँ जी।", "क्या हुआ?", "ठीक है, कर रहा हूँ।", "ये क्यों चाहिए?", "अच्छा जी।"],
}
