import os
import time
import hmac
import hashlib
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Wajib agar Website bisa akses

# --- KONFIGURASI ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRIPAY_API_KEY = os.environ.get("TRIPAY_API_KEY")
TRIPAY_PRIVATE_KEY = os.environ.get("TRIPAY_PRIVATE_KEY")
TRIPAY_MERCHANT_CODE = os.environ.get("TRIPAY_MERCHANT_CODE")
TRIPAY_MODE = "api-sandbox" 

# --- FUNGSI BANTUAN ---
def kirim_pesan_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

# Update: Menambahkan parameter 'custom_redirect'
def generate_tripay_link(customer, items, amount, method_code='BRIVA', user_id_tele=None, custom_redirect=None):
    
    if user_id_tele:
        merchant_ref = f"INV-TELE-{user_id_tele}-{int(time.time())}"
        # Jika dari Bot, return ke Telegram
        url_tujuan = f"https://t.me/GantiDenganUsernameBotAnda" 
    else:
        merchant_ref = f"INV-WEB-{int(time.time())}"
        # Jika dari Web, pakai URL custom (atau default ke Google kalau kosong)
        url_tujuan = custom_redirect if custom_redirect else 'https://google.com'

    # Signature Tripay
    signature_string = TRIPAY_MERCHANT_CODE + merchant_ref + str(amount)
    signature = hmac.new(
        TRIPAY_PRIVATE_KEY.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()

    payload = {
        'method': method_code,
        'merchant_ref': merchant_ref,
        'amount': amount,
        'customer_name': customer.get('name', 'Pelanggan'),
        'customer_email': customer.get('email', 'email@test.com'),
        'customer_phone': customer.get('phone', '08123456789'),
        'order_items': items,
        'return_url': url_tujuan, # <--- INI KUNCINYA
        'expired_time': (int(time.time()) + (24 * 60 * 60)),
        'signature': signature
    }

    headers = {'Authorization': f'Bearer {TRIPAY_API_KEY}'}
    try:
        response = requests.post(
            f'https://tripay.co.id/{TRIPAY_MODE}/transaction/create',
            json=payload, headers=headers
        )
        return response.json()
    except Exception as e:
        return {'success': False, 'message': str(e)}

# --- ENDPOINT 1: WEB APP (REACT) ---
@app.route('/api/checkout', methods=['POST'])
def checkout_web():
    data = request.json
    
    cart = data.get('cart', [])
    user = data.get('user', {})
    total_amount = data.get('total', 0)
    selected_method = data.get('paymentMethod', 'BRIVA')

    # ==================================================
    # GANTI URL DI BAWAH INI DENGAN LINK WEBSITE ANDA
    # Contoh: 'https://tokosaya.vercel.app'
    # ==================================================
    website_url = 'https://digimarketbywebnest.netlify.app/' 

    tripay_items = []
    for item in cart:
        tripay_items.append({
            'name': item['name'],
            'price': int(item['price']),
            'quantity': int(item['quantity'])
        })

    result = generate_tripay_link(
        customer={'name': user.get('name'), 'email': user.get('email')},
        items=tripay_items,
        amount=int(total_amount),
        method_code=selected_method,
        custom_redirect=website_url # <--- Mengirim URL Website
    )

    return jsonify(result)

# --- ENDPOINT 2: BOT TELEGRAM ---
@app.route('/', methods=['POST', 'GET'])
def telegram_handler():
    if request.method == 'POST':
        update = request.json
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '')

            if text == '/start':
                kirim_pesan_telegram(chat_id, "Halo! Ketik /beli untuk tes.")
            
            elif text == '/beli':
                # Contoh transaksi Bot
                kirim_pesan_telegram(chat_id, "Membuat tagihan... ⏳")
                result = generate_tripay_link(
                    customer={'name': 'User Telegram'},
                    items=[{'name': 'Produk Bot', 'price': 50000, 'quantity': 1}],
                    amount=50000,
                    method_code='QRIS',
                    user_id_tele=chat_id 
                    # Tidak kirim custom_redirect, jadi otomatis ke t.me
                )
                
                if result['success']:
                    link = result['data']['checkout_url']
                    kirim_pesan_telegram(chat_id, f"Link Bayar: {link}")
                else:
                    kirim_pesan_telegram(chat_id, "Gagal.")
                    
    return "OK", 200

# --- ENDPOINT 3: WEBHOOK ---
@app.route('/webhook', methods=['POST'])
def tripay_webhook():
    data = request.json
    status = data.get('status')
    merchant_ref = data.get('merchant_ref')
    
    if status == 'PAID':
        try:
            parts = merchant_ref.split('-')
            if parts[1] == 'TELE':
                user_id_tele = parts[2]
                kirim_pesan_telegram(user_id_tele, "✅ Pembayaran LUNAS!")
            elif parts[1] == 'WEB':
                print(f"Web Order Lunas: {merchant_ref}")
        except:
            pass

    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
