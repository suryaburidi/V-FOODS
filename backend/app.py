import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, session, redirect
from werkzeug.utils import secure_filename
from rag import retrieve, context, answer_from_rag
BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,'hotel.db')
FRONTEND_DIR=os.path.abspath(os.path.join(BASE_DIR,'..','frontend'))
UPLOAD_FOLDER=os.path.join(BASE_DIR,'uploads')
ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD','admin123')
ALLOWED_EXTENSIONS={'png','jpg','jpeg','webp'}
os.makedirs(UPLOAD_FOLDER,exist_ok=True)
app=Flask(__name__,static_folder=FRONTEND_DIR,static_url_path='/static')
app.secret_key=os.environ.get('SECRET_KEY','change-this-secret-in-production')
VEG_FOODS=[
('Andhra Veg Meals',180,'meals',30,1,1,'Traditional Andhra vegetarian meal with rice, curries and sides.'),('Special Veg Meals',160,'meals',25,1,1,'A wholesome vegetarian traditional spread.'),('Paneer 65',190,'starters',18,1,1,'Crispy paneer tossed with South Indian spices.'),('Gobi 65',170,'starters',20,1,1,'Crispy cauliflower with classic spices.'),('Veg Biryani',220,'biryani',20,1,1,'Aromatic basmati rice with vegetables and herbs.'),('Mushroom Biryani',240,'biryani',15,1,1,'Fragrant biryani with spiced mushrooms.'),('Gulab Jamun',90,'desserts',25,1,1,'Soft syrup-soaked sweet, served warm.'),('Payasam',80,'desserts',20,1,1,'Traditional creamy South Indian dessert.'),('Idli',60,'tiffins',30,1,1,'Soft steamed idlis served with chutney and sambar.'),('Vada',70,'tiffins',25,1,1,'Crispy South Indian vada with chutney.'),('Dosa',80,'tiffins',25,1,1,'Crispy dosa served with chutneys and sambar.'),('Pesarattu',90,'tiffins',20,1,1,'Andhra-style green gram dosa.'),('Pulihora',52,'rice',30,1,1,'Tangy tamarind rice with roasted spices and peanuts.')]
def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c
def init_db():
    c=db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS menu(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,price INTEGER NOT NULL,category TEXT NOT NULL,stock INTEGER NOT NULL DEFAULT 0,is_veg INTEGER NOT NULL DEFAULT 1,available INTEGER NOT NULL DEFAULT 1,description TEXT DEFAULT '',image TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS tables(id INTEGER PRIMARY KEY AUTOINCREMENT,table_no INTEGER UNIQUE NOT NULL,seats INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS reservations(id INTEGER PRIMARY KEY AUTOINCREMENT,table_id INTEGER NOT NULL,booking_date TEXT NOT NULL,booking_time TEXT NOT NULL,guests INTEGER NOT NULL,customer_name TEXT NOT NULL,phone TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'confirmed',created_at TEXT NOT NULL,FOREIGN KEY(table_id) REFERENCES tables(id));
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_name TEXT NOT NULL,phone TEXT NOT NULL,address TEXT NOT NULL DEFAULT '',total INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'received',payment_method TEXT NOT NULL DEFAULT 'cash',payment_status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL,menu_id INTEGER NOT NULL,quantity INTEGER NOT NULL,price INTEGER NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id),FOREIGN KEY(menu_id) REFERENCES menu(id));
    """)
    cols={r['name'] for r in c.execute('PRAGMA table_info(menu)').fetchall()}
    if 'image' not in cols: c.execute("ALTER TABLE menu ADD COLUMN image TEXT DEFAULT ''")
    cols={r['name'] for r in c.execute('PRAGMA table_info(orders)').fetchall()}
    if 'address' not in cols: c.execute("ALTER TABLE orders ADD COLUMN address TEXT DEFAULT ''")
    if 'payment_method' not in cols: c.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'cash'")
    if 'payment_status' not in cols: c.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'pending'")
    cols={r['name'] for r in c.execute('PRAGMA table_info(reservations)').fetchall()}
    if 'created_at' not in cols: c.execute("ALTER TABLE reservations ADD COLUMN created_at TEXT DEFAULT ''")
    for item in VEG_FOODS: c.execute('INSERT OR IGNORE INTO menu(name,price,category,stock,is_veg,available,description,image) VALUES(?,?,?,?,?,?,?,?)',(*item,''))
    if c.execute('SELECT COUNT(*) c FROM tables').fetchone()['c']==0: c.executemany('INSERT INTO tables(table_no,seats) VALUES(?,?)',[(1,2),(2,2),(3,2),(4,4),(5,4),(6,4),(7,6),(8,6),(9,8),(10,8)])
    c.execute("UPDATE menu SET is_veg=0,available=0 WHERE LOWER(name) LIKE '%chicken%' OR LOWER(name) LIKE '%mutton%'"); c.commit(); c.close()
def allowed_file(n): return '.' in n and n.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS
def admin_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('admin'):
            if request.path.startswith('/api/admin'): return jsonify(error='Admin login required'),401
            return redirect('/admin')
        return fn(*a,**kw)
    return wrapper
@app.after_request
def no_cache_admin(resp):
    if request.path.startswith('/admin') or request.path.startswith('/api/admin'): resp.headers['Cache-Control']='no-store'
    return resp
@app.route('/')
def home(): return send_from_directory(app.static_folder,'index.html')
@app.route('/menu')
def menu_page(): return send_from_directory(app.static_folder,'index.html')
@app.route('/admin')
def admin_page(): return send_from_directory(app.static_folder,'admin.html')
@app.route('/uploads/<path:filename>')
def uploaded_file(filename): return send_from_directory(UPLOAD_FOLDER,filename)
@app.route('/<path:path>')
def static_files(path): return send_from_directory(app.static_folder,path)
@app.post('/api/admin/login')
def admin_login():
    d=request.get_json(force=True)
    if d.get('password')==ADMIN_PASSWORD: session['admin']=True; return jsonify(success=True)
    return jsonify(success=False,error='Wrong admin password'),401
@app.post('/api/admin/logout')
def admin_logout(): session.clear(); return jsonify(success=True)
@app.get('/api/menu')
def menu():
    c=db(); rows=c.execute('SELECT id,name,price,category,stock,is_veg,available,description,image FROM menu WHERE is_veg=1 ORDER BY id').fetchall(); c.close(); return jsonify([dict(r) for r in rows])
@app.get('/api/admin/menu')
@admin_required
def admin_menu():
    c=db(); rows=c.execute('SELECT * FROM menu WHERE is_veg=1 ORDER BY id DESC').fetchall(); c.close(); return jsonify([dict(r) for r in rows])
@app.post('/api/admin/menu')
@admin_required
def add_menu():
    d=request.get_json(force=True)
    try:
        name=str(d['name']).strip(); price=int(d['price']); stock=max(0,int(d.get('stock',0))); category=d.get('category','meals'); description=str(d.get('description','')).strip(); available=1 if d.get('available',True) else 0
        if not name or price<0: raise ValueError
    except (KeyError,ValueError,TypeError): return jsonify(error='Enter a valid name, price and stock.'),400
    c=db()
    try:
        cur=c.execute('INSERT INTO menu(name,price,category,stock,is_veg,available,description,image) VALUES(?,?,?,?,1,?,?,?)',(name,price,category,stock,available,description,'')); c.commit(); iid=cur.lastrowid
    except sqlite3.IntegrityError: c.close(); return jsonify(error='A food with this name already exists.'),409
    c.close(); return jsonify(success=True,id=iid)
@app.put('/api/admin/menu/<int:iid>')
@admin_required
def update_menu(iid):
    d=request.get_json(force=True); c=db(); row=c.execute('SELECT * FROM menu WHERE id=? AND is_veg=1',(iid,)).fetchone()
    if not row: c.close(); return jsonify(error='Food not found'),404
    try:
        vals=(str(d.get('name',row['name'])).strip(),int(d.get('price',row['price'])),d.get('category',row['category']),max(0,int(d.get('stock',row['stock']))),1 if d.get('available',bool(row['available'])) else 0,str(d.get('description',row['description'] or '')).strip(),str(d.get('image',row['image'] or '')).strip(),iid)
        c.execute('UPDATE menu SET name=?,price=?,category=?,stock=?,available=?,description=?,image=? WHERE id=? AND is_veg=1',vals); c.commit()
    except (ValueError,TypeError,sqlite3.IntegrityError): c.close(); return jsonify(error='Could not update food.'),400
    c.close(); return jsonify(success=True)
@app.delete('/api/admin/menu/<int:iid>')
@admin_required
def delete_menu(iid):
    c=db(); c.execute('DELETE FROM menu WHERE id=? AND is_veg=1',(iid,)); c.commit(); c.close(); return jsonify(success=True)
@app.post('/api/admin/menu/<int:iid>/availability')
@admin_required
def set_availability(iid):
    d=request.get_json(force=True); c=db(); cur=c.execute('UPDATE menu SET available=? WHERE id=? AND is_veg=1',(1 if d.get('available') else 0,iid)); c.commit(); c.close(); return jsonify(success=cur.rowcount>0)
@app.post('/api/admin/menu/<int:iid>/image')
@admin_required
def upload_image(iid):
    f=request.files.get('image')
    if not f or not f.filename or not allowed_file(f.filename): return jsonify(error='Allowed image types: PNG, JPG, JPEG, WEBP'),400
    c=db(); row=c.execute('SELECT id FROM menu WHERE id=? AND is_veg=1',(iid,)).fetchone()
    if not row: c.close(); return jsonify(error='Food not found'),404
    ext=secure_filename(f.filename).rsplit('.',1)[1].lower(); fn=f'food_{iid}.{ext}'; f.save(os.path.join(UPLOAD_FOLDER,fn)); url=f'/uploads/{fn}'; c.execute('UPDATE menu SET image=? WHERE id=?',(url,iid)); c.commit(); c.close(); return jsonify(success=True,image=url)
def available_tables(date,time,guests):
    c=db(); rows=c.execute("""SELECT t.* FROM tables t WHERE t.seats>=? AND t.id NOT IN (SELECT table_id FROM reservations WHERE booking_date=? AND booking_time=? AND status='confirmed') ORDER BY t.seats,t.table_no""",(guests,date,time)).fetchall(); c.close(); return [dict(r) for r in rows]
@app.get('/api/tables')
def tables():
    date=request.args.get('date'); time=request.args.get('time'); guests=int(request.args.get('guests',2))
    if not date or not time: return jsonify(error='date and time are required'),400
    opts=available_tables(date,time,guests); return jsonify(available_count=len(opts),tables=opts)
@app.post('/api/reservations')
def reserve():
    d=request.get_json(force=True); required=['date','time','guests','name','phone']
    if any(not d.get(k) for k in required): return jsonify(error='Please provide date, time, guests, name and phone'),400
    opts=available_tables(d['date'],d['time'],int(d['guests']))
    if not opts: return jsonify(success=False,message='No suitable table is available for that slot.'),409
    t=opts[0]; c=db(); cur=c.execute('INSERT INTO reservations(table_id,booking_date,booking_time,guests,customer_name,phone,status,created_at) VALUES(?,?,?,?,?,?,?,?)',(t['id'],d['date'],d['time'],int(d['guests']),d['name'].strip(),d['phone'].strip(),'confirmed',datetime.now().isoformat(timespec='seconds'))); c.commit(); rid=cur.lastrowid; c.close(); return jsonify(success=True,reservation_id=rid,table_no=t['table_no'],date=d['date'],time=d['time'],guests=int(d['guests']))
def order_details(oid):
    c=db(); o=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not o: c.close(); return None
    items=c.execute('SELECT oi.menu_id,oi.quantity,oi.price,m.name,m.image FROM order_items oi JOIN menu m ON m.id=oi.menu_id WHERE oi.order_id=?',(oid,)).fetchall(); c.close(); d=dict(o); d['items']=[dict(x) for x in items]; return d
@app.post('/api/orders')
def order():
    d=request.get_json(force=True); items=d.get('items',[]); name=str(d.get('name','')).strip(); phone=str(d.get('phone','')).strip(); address=str(d.get('address','')).strip(); payment=d.get('payment_method','cash')
    if not items or not name or not phone or not address: return jsonify(error='Name, phone, delivery address and at least one item are required'),400
    if payment not in ('cash','upi','card'): return jsonify(error='Invalid payment method'),400
    c=db(); total=0; validated=[]
    try:
        for item in items:
            row=c.execute('SELECT * FROM menu WHERE id=? AND is_veg=1',(item.get('menu_id'),)).fetchone(); qty=int(item.get('quantity',0))
            if not row or qty<1: raise ValueError('Invalid menu item or quantity')
            if not row['available']: raise ValueError(f"{row['name']} is currently unavailable.")
            if row['stock']<qty: raise ValueError(f"Only {row['stock']} {row['name']} available.")
            total+=row['price']*qty; validated.append((row,qty))
        pay_status='paid_demo' if payment in ('upi','card') else 'pending'
        cur=c.execute('INSERT INTO orders(customer_name,phone,address,total,status,payment_method,payment_status,created_at) VALUES(?,?,?,?,?,?,?,?)',(name,phone,address,total,'received',payment,pay_status,datetime.now().isoformat(timespec='seconds'))); oid=cur.lastrowid
        for row,qty in validated:
            c.execute('INSERT INTO order_items(order_id,menu_id,quantity,price) VALUES(?,?,?,?)',(oid,row['id'],qty,row['price'])); c.execute('UPDATE menu SET stock=stock-? WHERE id=?',(qty,row['id']))
        c.commit()
    except ValueError as e: c.rollback(); c.close(); return jsonify(error=str(e)),409
    except Exception: c.rollback(); c.close(); return jsonify(error='Order could not be placed.'),500
    c.close(); return jsonify(success=True,order=order_details(oid))
@app.get('/api/orders/<int:oid>')
def get_order(oid):
    d=order_details(oid); return jsonify(d) if d else (jsonify(error='Order not found'),404)
@app.get('/api/orders')
def customer_orders():
    phone=request.args.get('phone','').strip()
    if not phone: return jsonify(error='Phone is required'),400
    c=db(); ids=c.execute('SELECT id FROM orders WHERE phone=? ORDER BY id DESC LIMIT 20',(phone,)).fetchall(); c.close(); return jsonify([order_details(r['id']) for r in ids])
@app.get('/api/admin/orders')
@admin_required
def admin_orders():
    c=db(); rows=c.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 100').fetchall(); c.close(); return jsonify([dict(r) for r in rows])
@app.post('/api/admin/orders/<int:oid>/status')
@admin_required
def update_order_status(oid):
    status=request.get_json(force=True).get('status','received'); allowed={'received','preparing','out_for_delivery','delivered','cancelled'}
    if status not in allowed: return jsonify(error='Invalid status'),400
    c=db(); cur=c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid)); c.commit(); c.close(); return jsonify(success=cur.rowcount>0)
@app.get('/api/admin/reservations')
@admin_required
def admin_reservations():
    c=db(); rows=c.execute('SELECT r.*,t.table_no,t.seats FROM reservations r JOIN tables t ON t.id=r.table_id ORDER BY r.id DESC LIMIT 100').fetchall(); c.close(); return jsonify([dict(r) for r in rows])
def parse_items(message):
    c=db(); rows=c.execute('SELECT id,name,price,stock,available FROM menu WHERE is_veg=1').fetchall(); c.close(); found=[]
    for r in rows:
        if r['name'].lower() in message:
            m=re.search(r'(\d+)\s*(?:x|plates?|pcs?)?\s*'+re.escape(r['name'].lower()),message)
            if not m: m=re.search(re.escape(r['name'].lower())+r'\s*(?:x|[- ]?)\s*(\d+)',message)
            qty=int(m.group(1)) if m else 1
            found.append({'menu_id':r['id'],'name':r['name'],'quantity':qty,'price':r['price'],'available':bool(r['available'] and r['stock']>=qty),'stock':r['stock']})
    return found
@app.post('/api/chat')
def chat():
    """RAG-first hotel assistant.
    Retrieval uses the local knowledge base plus live menu/table/order data.
    The final answer is grounded in retrieved context and current DB state.
    """
    data=request.get_json(force=True) or {}
    original=(data.get('message') or '').strip()
    msg=original.lower()
    if not original:
        return jsonify(reply='Please ask me about food, orders, delivery, tables or reservations.',action=None)

    # Live menu becomes retrieval context, so answers stay aligned with Admin updates.
    c=db(); menu_rows=c.execute('SELECT id,name,price,stock,available,category,description FROM menu WHERE is_veg=1 ORDER BY name').fetchall(); c.close()
    menu_docs=[{'id':'menu_live_'+str(r['id']),'title':r['name'],'text':f"{r['name']} costs ₹{r['price']}. It is {'available' if r['available'] and r['stock']>0 else 'unavailable'}. Current stock: {r['stock']}. Category: {r['category']}. {r['description'] or ''}"} for r in menu_rows]
    docs=retrieve(original,menu_docs,top_k=5)

    # Food requirement -> cart action. This always checks live stock first.
    found=parse_items(msg)
    if found and any(x['available'] for x in found):
        good=[x for x in found if x['available']]
        lines=['I understood your food requirement and checked the live menu:','']
        for i,x in enumerate(good,1): lines.append(f"{i}. {x['name']} × {x['quantity']} — ₹{x['price']*x['quantity']}")
        lines += ['', 'I added the available items to your cart. Open the cart to enter your delivery address and choose payment.']
        return jsonify(reply='\n'.join(lines),action='add_to_cart',items=good,rag=True,sources=[d['title'] for d in docs[:4]])
    if found and not any(x['available'] for x in found):
        unavailable=[]
        for x in found:
            if not x['available']:
                reason='currently unavailable' if x['stock']<=0 or not x['available'] else f"only {x['stock']} available"
                unavailable.append(f"{x['name']} — {reason}")
        return jsonify(reply='I checked the live menu.\n\n'+'\n'.join(f'{i}. {v}' for i,v in enumerate(unavailable,1))+'\n\nPlease choose another available vegetarian item.',action='availability',rag=True,sources=[d['title'] for d in docs[:4]])

    # Live availability query.
    if any(k in msg for k in ('available','availability','stock','what food','menu')) and any(k in msg for k in ('food','dish','menu','biryani','meal','tiffin','starter','dessert','available','stock')):
        c=db(); rows=c.execute('SELECT name,price,stock FROM menu WHERE is_veg=1 AND available=1 AND stock>0 ORDER BY name').fetchall(); c.close()
        items=[f"{i}. {r['name']} — ₹{r['price']} — {r['stock']} available" for i,r in enumerate(rows,1)]
        reply='Available vegetarian food right now:\n\n'+'\n'.join(items) if items else 'There is no vegetarian food available right now.'
        return jsonify(reply=reply,action='availability',rag=True,sources=[d['title'] for d in docs[:4]])

    # Live table availability. If date/time are not supplied, ask for them rather than inventing.
    if 'table' in msg or 'reservation' in msg or 'reserve' in msg or 'book a table' in msg:
        # Accept common explicit YYYY-MM-DD plus a time such as 20:00 / 8 PM.
        date_match=re.search(r'\b(20\d{2}-\d{2}-\d{2})\b',msg)
        time_match=re.search(r'\b([01]?\d|2[0-3]):[0-5]\d\b',msg)
        if not time_match:
            time_match=re.search(r'\b(1[0-2]|[1-9])\s*(am|pm)\b',msg)
        guests_match=re.search(r'\b(\d+)\s*(?:people|persons|guests|pax)\b',msg)
        if date_match and time_match and guests_match:
            date=date_match.group(1); raw_time=time_match.group(0); guests=int(guests_match.group(1))
            # Convert 8 PM style to the backend's simple display value if needed.
            if ':' in raw_time:
                norm_time=raw_time
            else:
                h=int(re.search(r'\d+',raw_time).group()); ampm=raw_time[-2:]
                if ampm=='pm' and h!=12:h+=12
                if ampm=='am' and h==12:h=0
                norm_time=f'{h:02d}:00'
            opts=available_tables(date,norm_time,guests)
            if opts:
                tables=', '.join(str(x['table_no']) for x in opts)
                reply=f"Yes. I checked live availability for {date} at {raw_time.upper()} for {guests} guest(s).\n\n{len(opts)} suitable table(s) are available: Table {tables}.\n\nIf you want to reserve one, use the Book a Table form with the same date, time and guest count."
            else:
                reply=f"I checked live availability for {date} at {raw_time.upper()} for {guests} guest(s).\n\nNo suitable table is available for that slot. Please try another time."
            return jsonify(reply=reply,action='table',rag=True,sources=[d['title'] for d in docs[:4]])
        return jsonify(reply='Sure — I can check or help reserve a table. Please give me the date, time and number of guests. Example: “2026-09-20 8 PM, 4 people”.',action='table',rag=True,sources=[d['title'] for d in docs[:4]])

    # Order tracking via phone or order number.
    if any(k in msg for k in ('track','status','where is my order','my order','order status')):
        phone=re.search(r'\b\d{10}\b',msg)
        oid=re.search(r'order\s*#?\s*(\d+)',msg)
        if oid:
            d=order_details(int(oid.group(1)))
            if d:
                return jsonify(reply=f"Order #{d['id']} is currently {d['status'].replace('_',' ')}. Total: ₹{d['total']}. Payment: {d['payment_method']}. Delivery address: {d['address']}.",action='order_status',rag=True,sources=[x['title'] for x in docs[:4]])
        if phone:
            c=db(); ids=c.execute('SELECT id FROM orders WHERE phone=? ORDER BY id DESC LIMIT 3',(phone.group(0),)).fetchall(); c.close()
            if ids:
                lines=['Here are your recent orders:','']
                for i,r in enumerate(ids,1):
                    d=order_details(r['id']); lines.append(f"{i}. Order #{d['id']} — {d['status'].replace('_',' ')} — ₹{d['total']}")
                return jsonify(reply='\n'.join(lines),action='order_status',rag=True,sources=[x['title'] for x in docs[:4]])
        return jsonify(reply='I can check your order status. Please send your order number (for example, Order #12) or the 10-digit phone number used for the order.',action='order_status',rag=True,sources=[x['title'] for x in docs[:4]])

    # RAG-grounded domain answer.
    reply=answer_from_rag(original,docs)
    return jsonify(reply=reply,action=None,rag=True,sources=[d['title'] for d in docs[:4]])

if __name__=='__main__':
    init_db(); app.run(debug=True,host='0.0.0.0',port=5000)
