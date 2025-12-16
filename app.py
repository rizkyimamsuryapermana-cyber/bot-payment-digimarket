import os
import time
import hmac
import hashlib
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- KONFIGURASI (Auto-Load dari Vercel/Render) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TRIPAY_API_KEY = os.environ.get("TRIPAY_API_KEY")
TRIPAY_PRIVATE_KEY = os.environ.get("TRIPAY_PRIVATE_KEY")
TRIPAY_MERCHANT_CODE = os.environ.get("TRIPAY_MERCHANT_CODE")
TRIPAY_MODE = "api-sandbox" # Ubah ke 'api' jika sudah live production
# ---------------------------------------------------

def kirim_pesan(chat_id, text):
    """Fungsi pembantu untuk kirim pesan ke Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def buat_link_pembayaran(user_id):
    """Fungsi request ke Tripay"""
    merchant_ref = f"INV-{user_id}-{int(time.time())}" # Kode Unik
    amount = 50000  # GANTI HARGA DI SINI
    
    # 1. Buat Signature Keamanan Tripay
    signature_string = TRIPAY_MERCHANT_CODE + merchant_ref + str(amount)
    signature = hmac.new(
        TRIPAY_PRIVATE_KEY.encode(),
        signature_string.encode(),
        hashlib.sha256
    ).hexdigest()

    # 2. Siapkan Data
    payload = {
        'method': 'BRIVA', # Bisa diganti channel lain
        'merchant_ref': merchant_ref,
        'amount': amount,
        'customer_name': f'User {user_id}',
        'customer_email': 'pembeli@bot.com',
        'customer_phone': '08123456789',
        'order_items': [
            {'name': 'Produk Premium Bot', 'price': amount, 'quantity': 1}
        ],
        'return_url': 'https://t.me/', # Redirect setelah bayar
        'expired_time': (int(time.time()) + (24 * 60 * 60)), # 24 Jam
        'signature': signature
    }

    headers = {'Authorization': f'Bearer {TRIPAY_API_KEY}'}
    
    # 3. Tembak ke Tripay
    try:
        response = requests.post(
            f'https://tripay.co.id/{TRIPAY_MODE}/transaction/create',
            json=payload, headers=headers
        )
        data = response.json()
        if data['success']:
            return data['data']['checkout_url']
        else:
            return None
    except Exception as e:
        print(f"Error Tripay: {e}")
        return None

# --- RUTE 1: MENERIMA CHAT DARI TELEGRAM ---
@app.route('/', methods=['POST', 'GET'])
def telegram_handler():
    if request.method == 'POST':
        update = request.json
        
        # Cek apakah ada pesan baru
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '')

            # LOGIKA JAWABAN BOT
            if text == '/start':
                balasan = "Halo! Selamat datang.\nKetik /beli untuk membeli paket Premium Rp 50.000."
                kirim_pesan(chat_id, balasan)
            
            elif text == '/beli':
                kirim_pesan(chat_id, "Mohon tunggu, sedang membuat tagihan... ⏳")
                link = buat_link_pembayaran(chat_id)
                if link:
                    kirim_pesan(chat_id, f"✅ Tagihan Siap!\n\nSilakan bayar melalui link ini:\n{link}")
                else:
                    kirim_pesan(chat_id, "❌ Gagal membuat tagihan. Coba lagi nanti.")
            
            else:
                kirim_pesan(chat_id, "Maaf, perintah tidak dikenali. Ketik /beli untuk order.")

        return "OK", 200
    return "Bot Telegram Active!", 200

# --- RUTE 2: WEBHOOK (DIPANGGIL TRIPAY SAAT LUNAS) ---
@app.route('/webhook', methods=['POST'])
def tripay_webhook():
    data = request.json
    status = data.get('status')
    merchant_ref = data.get('merchant_ref')
    
    # Jika Status LUNAS (PAID)
    if status == 'PAID':
        # Parse User ID dari merchant_ref (Format: INV-USERID-WAKTU)
        try:
            parts = merchant_ref.split('-')
            user_id = parts[1] # Mengambil angka di tengah
            
            # KIRIM PRODUK / NOTIF KE USER DI SINI
            pesan_sukses = (
                "🎉 **PEMBAYARAN DITERIMA!**\n\n"
                "Terima kasih. Fitur Premium Anda telah aktif.\n"
                "Silakan akses grup VIP di link berikut: https://t.me/..."
            )
            kirim_pesan(user_id, pesan_sukses)
        except Exception as e:
            print(f"Gagal parse user ID: {e}")

    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
