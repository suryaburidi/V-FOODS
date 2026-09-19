# Subbayya Gari Hotel — Zomato-style Full Stack Prototype

## Structure
- `frontend/` — customer website, menu, chatbot, cart, checkout, order tracking and table booking.
- `backend/` — Flask API, SQLite database, admin APIs and food uploads.

## Run
```powershell
cd backend
pip install -r requirements.txt
python app.py
```
Customer: `http://127.0.0.1:5000`
Admin direct URL: `http://127.0.0.1:5000/admin`

## Features
- Delivery address, phone and customer name at checkout.
- Quantity controls and cleaner spacing between food cards.
- UPI/Online demo, Card demo and Cash on Delivery options.
- Order confirmation and order tracking by phone.
- AI assistant can recognize simple food requirements and add matching items to cart.
- Live vegetarian food stock/availability and table availability.
- Admin sees customer address/payment and can update order status.

Online payment is demo-enabled in this local prototype; a live gateway requires merchant credentials and server-side integration.


### Chatbot availability display
The AI Assistant now displays available vegetarian foods as a clean numbered list with price and stock, one item per line.

## RAG chatbot
The Subbayya AI assistant now uses a RAG-first pipeline. `backend/knowledge_base.json` contains hotel knowledge, `backend/rag.py` retrieves relevant chunks, and the Flask `/api/chat` route adds live menu/table/order data from SQLite before producing a grounded response. This keeps the assistant focused on food, orders, delivery and table reservations instead of answering unrelated questions.
