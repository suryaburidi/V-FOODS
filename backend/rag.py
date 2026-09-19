import json, os, re
from collections import Counter

KB_PATH=os.path.join(os.path.dirname(__file__),'knowledge_base.json')
with open(KB_PATH,encoding='utf-8') as f:
    KNOWLEDGE_BASE=json.load(f)

STOP=set('the a an is are am to of for and or in on at with what which how many me tell can i you your our about please do does this that now available food table tables order booking book reserve reservation hotel'.split())
SYNONYMS={
 'food':['menu','dish','dishes','meal','meals','biryani','tiffin','starter','starters','dessert','rice','curry'],
 'table':['tables','seat','seats','reservation','reservations','reserve','booking','book'],
 'order':['orders','ordering','delivery','deliver','cart','food'],
 'payment':['pay','upi','card','cash','cod'],
 'timing':['time','timings','hours','open','close']
}

def tokens(text):
    raw=re.findall(r"[a-z0-9]+", text.lower())
    out=[]
    for t in raw:
        if t in STOP: continue
        out.append(t)
        for base,alts in SYNONYMS.items():
            if t in alts: out.append(base)
    return out

def retrieve(query, extra_docs=None, top_k=4):
    docs=KNOWLEDGE_BASE+(extra_docs or [])
    q=tokens(query); qset=Counter(q)
    scored=[]
    for d in docs:
        dt=tokens(d.get('title','')+' '+d.get('text',''))
        dc=Counter(dt)
        overlap=sum(min(qset[k],dc[k]) for k in qset)
        if overlap:
            # small phrase/title boost; keeps retrieval deterministic and local
            title_tokens=set(tokens(d.get('title','')))
            title_boost=sum(1 for x in qset if x in title_tokens)
            scored.append((overlap*2+title_boost,d))
    scored.sort(key=lambda x:x[0],reverse=True)
    return [d for _,d in scored[:top_k]]

def context(docs):
    return '\n'.join(f"[{d['title']}] {d['text']}" for d in docs)

def answer_from_rag(query, docs):
    """Grounded response generator used when no external LLM is configured."""
    q=query.lower()
    ctx=context(docs)
    # Focused answer selection from retrieved knowledge.
    if any(x in q for x in ('open','closing','close','timing','hours','time')):
        return 'We are open daily from 6:00 AM to 10:00 PM.'
    if any(x in q for x in ('payment','pay','upi','card','cash','cod')):
        return 'Payment options are UPI / Online (demo), Card (demo), and Cash on Delivery. Live gateway payments are not connected in this prototype.'
    if any(x in q for x in ('address','delivery','deliver')):
        return 'For food delivery, please provide your full name, phone number and complete delivery address. After placing the order, you can track it using the same phone number.'
    if any(x in q for x in ('table','reservation','reserve','booking','book')):
        return 'I can help with tables. Tell me the date, time and number of guests. I can then check the live table availability.'
    if any(x in q for x in ('veg','vegetarian')):
        return 'Yes. The online menu is vegetarian-only.'
    if any(x in q for x in ('order','food','menu','dish','biryani','meal','tiffin','starter','dessert','rice')):
        return 'I can help with the vegetarian menu, live food availability and food ordering. You can type your requirement, for example: “2 Veg Biryani and 1 Paneer 65”.'
    if docs:
        # Use the retrieved facts instead of a generic unrelated answer.
        return 'Here is what I can help with: ' + '; '.join(d['text'] for d in docs[:2])
    return 'I’m the Subbayya Gari Hotel assistant. I can help with vegetarian food, food availability, orders, delivery details, table availability and reservations.'
