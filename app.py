import os
from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import time

app = Flask(__name__)

# --- KONFIGURASI DIAMBIL DARI SERVER (ENVIRONMENT VARIABLES) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRIPAY_API_KEY = os.environ.get("TRIPAY_API_KEY")
TRIPAY_PRIVATE_KEY = os.environ.get("TRIPAY_PRIVATE_KEY")
TRIPAY_MERCHANT_CODE = os.environ.get("TRIPAY_MERCHANT_CODE")
TRIPAY_MODE = "api-sandbox" # Ganti 'api' jika sudah production
# -------------------------------------------------------------

def kirim_pesan_telegram(chat_id, pesan):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": pesan}
    requests.post(url, json=payload)

@app.route('/')
def home():
    return "Bot Payment Server is Running!", 200

# 1. Pemicu Transaksi (Contoh link: https://nama-app.onrender.com/beli?user_id=123)
@app.route('/beli', methods=['GET'])
def beli():
    user_id = request.args.get('user_id')
    if not user_id:
        return "Error: Masukkan user_id", 400

    ref_id = f'ORDER-{user_id}-{int(time.time())}' # Invoice Unik pakai waktu
    
    # Signature Keamanan Tripay
    signature_string = TRIPAY_MERCHANT_CODE + ref_id + '50000'
    signature = hmac.new(
        TRIPAY_PRIVATE_KEY.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()

    payload = {
        'method': 'BRIVA', 
        'merchant_ref': ref_id,
        'amount': 50000,
        'customer_name': 'Pelanggan Bot',
        'customer_email': 'email@test.com',
        'customer_phone': '08123456789',
        'order_items': [{'name': 'Voucher Premium', 'price': 50000, 'quantity': 1}],
        'return_url': 'https://t.me/UsernameBotAnda', # Redirect setelah bayar
        'expired_time': (int(time.time()) + (24 * 60 * 60)),
        'signature': signature
    }

    headers = {'Authorization': f'Bearer {TRIPAY_API_KEY}'}
    response = requests.post(
        f'https://tripay.co.id/{TRIPAY_MODE}/transaction/create',
        json=payload, headers=headers
    )
    
    data = response.json()
    if data['success']:
        checkout_url = data['data']['checkout_url']
        kirim_pesan_telegram(user_id, f"Tagihan dibuat! Klik untuk bayar: {checkout_url}")
        return f"Sukses! Link dikirim ke Telegram ID {user_id}"
    else:
        return f"Gagal: {data['message']}"

# 2. Webhook (Jalur Laporan Tripay)
@app.route('/webhook', methods=['POST'])
def webhook():
    # Ambil data JSON dari Tripay
    data = request.json
    
    # Validasi Signature Webhook (Opsional tapi disarankan agar tidak di-hack)
    # Untuk tutorial ini kita skip validasi signature masuk agar simpel
    
    status = data.get('status') 
    merchant_ref = data.get('merchant_ref')
    
    if status == 'PAID':
        # Format ref kita tadi: ORDER-USERID-WAKTU
        # Kita ambil USERID-nya (elemen ke-1)
        try:
            user_id = merchant_ref.split('-')[1]
            kirim_pesan_telegram(user_id, "✅ Pembayaran LUNAS! Fitur Premium Anda sudah aktif.")
        except:
            print("Gagal parsing ID user")

    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
