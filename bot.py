import uuid
import jwt
import time
import requests
from datetime import datetime
from typing import List, Optional
from colorama import init, Fore, Style
import os

# Initialize colorama
init(autoreset=True)


def display_banner():
    """Menampilkan banner saat program dijalankan."""
    print(Fore.GREEN + "[+]===============================[+]")
    print(Fore.GREEN + "[+]  NAORIS PROTOCOL AUTOMATION   [+]")
    print(Fore.GREEN + "[+]       @AirdropFamilyIDN       [+]")
    print(Fore.GREEN + "[+]===============================[+]")
    print()  

# Utils
def generate_device_hash() -> str:
    """Generate a unique device hash."""
    return str(int(uuid.uuid4().hex.replace("-", "")[:8], 16))

def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT token and extract relevant data."""
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        if not decoded:
            raise ValueError("Invalid token format")
        return {
            "wallet_address": decoded.get("wallet_address"),
            "id": decoded.get("id"),
            "exp": decoded.get("exp"),
        }
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Error decoding token: {e}")
        return None

def is_token_expired(account: dict) -> bool:
    """Check if the account's token is expired."""
    if not account.get("decoded") or not account["decoded"].get("exp"):
        return True
    return time.time() >= account["decoded"]["exp"]

def load_proxies(proxy_file: str) -> List[str]:
    """Load proxies from a text file."""
    try:
        with open(proxy_file, "r") as file:
            proxies = [line.strip() for line in file if line.strip()]
        return proxies
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Failed to load proxies: {e}")
        return []

def ask_proxy_usage():
    """Tanyakan apakah pengguna ingin menggunakan proxy."""
    while True:
        choice = input(f"{Fore.CYAN}[?] Apakah Anda ingin menggunakan proxy? (y/n): ").strip().lower()
        if choice in ["y", "n"]:
            return choice == "y"
        else:
            print(f"{Fore.RED}[ERROR] Masukkan 'y' untuk Ya atau 'n' untuk Tidak.")

# Configurations
API_CONFIG = {
    "base_url": "https://naorisprotocol.network",
    "endpoints": {
        "heartbeat": "/sec-api/api/produce-to-kafka",
    },
    "headers": {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "chrome-extension://cpikainghpmifinihfeigiboilmmp",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    },
}

APP_CONFIG = {
    "heartbeat_interval": 6000,  # 6 detik
    "data_file": "data.txt",  
    "proxy_file": "proxy.txt",  
}

# Heartbeat Service with Proxy Support
class HeartbeatService:
    def __init__(self, use_proxy: bool):
        self.accounts: List[dict] = []
        self.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.wallet_colors = [Fore.GREEN, Fore.CYAN]  # Warna untuk setiap wallet
        self.proxies = load_proxies(APP_CONFIG["proxy_file"]) if use_proxy else []
        self.use_proxy = use_proxy

    def load_accounts(self):
        """Load accounts from the data file."""
        try:
            with open(APP_CONFIG["data_file"], "r") as file:
                tokens = file.read().splitlines()

            self.accounts = []
            for idx, token in enumerate(tokens):
                decoded = decode_token(token.strip())
                if not decoded or not decoded.get("wallet_address"):
                    print(f"{Fore.RED}[ERROR] Failed to decode token: {token[:20]}...")
                    continue

                # Assign proxy to account (jika menggunakan proxy)
                proxy = self.proxies[idx % len(self.proxies)] if self.use_proxy and self.proxies else None

                self.accounts.append({
                    "token": token.strip(),
                    "decoded": decoded,
                    "device_hash": generate_device_hash(),
                    "status": "initialized",
                    "wallet_number": idx + 1,  # Penanda wallet (Wallet 1, Wallet 2)
                    "proxy": proxy,  
                })

            if not self.accounts:
                raise ValueError("No valid accounts loaded")

            print(f"{Fore.CYAN}[INFO] Successfully loaded {len(self.accounts)} accounts.")
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Error loading accounts: {e}")
            raise

    def get_session(self, proxy: Optional[str] = None):
        """Create a requests session with proxy support."""
        session = requests.Session()
        if proxy:
            session.proxies = {
                "http": proxy,
                "https": proxy,
            }
        return session

    def send_heartbeat(self, account: dict):
        """Send a heartbeat request for the given account."""
        try:
            session = self.get_session(account["proxy"])
            headers = API_CONFIG["headers"].copy()
            headers["Authorization"] = f"Bearer {account['token']}"
            payload = {
                "topic": "device-heartbeat",
                "deviceHash": account["device_hash"],
                "walletAddress": account["decoded"]["wallet_address"],
            }
            response = session.post(
                f"{API_CONFIG['base_url']}{API_CONFIG['endpoints']['heartbeat']}",
                headers=headers,
                json=payload,
            )
            account["last_heartbeat"] = datetime.now().strftime("%H:%M:%S")
            account["status"] = "active"

            
            wallet_color = self.wallet_colors[(account["wallet_number"] - 1) % len(self.wallet_colors)]

            # Tampilkan pesan success dengan atau tanpa proxy
            if account["proxy"]:
                print(f"{wallet_color}[SUCCESS] Wallet {account['wallet_number']}: Heartbeat sent for wallet {account['decoded']['wallet_address']} (with proxy)")
            else:
                print(f"{wallet_color}[SUCCESS] Wallet {account['wallet_number']}: Heartbeat sent for wallet {account['decoded']['wallet_address']} (without proxy)")

            return response.json()
        except Exception as e:
            account["status"] = "error"
            print(f"{Fore.RED}[ERROR] Wallet {account['wallet_number']}: Error sending heartbeat for wallet {account['decoded']['wallet_address']}: {e}")
            return None

    def start(self):
        """Start the heartbeat service."""
        self.load_accounts()
        print(f"{Fore.CYAN}[INFO] Heartbeat service started at {self.start_time}.")

        # Display active accounts (tanpa warna khusus)
        print(f"\n[ACCOUNTS] Active Accounts:")
        for account in self.accounts:
            last_heartbeat = account.get("last_heartbeat", "Never")
            exp_date = datetime.fromtimestamp(account["decoded"]["exp"]).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  - Wallet {account['wallet_number']}: {account['decoded']['wallet_address'][:10]}... | "
                f"Last Heartbeat: {last_heartbeat} | "
                f"Exp: {exp_date} | "
                f"Status: {account.get('status', 'waiting')}"
            )

        # Spasi kosong sebelum mulai mengirim heartbeat
        print()

        # Start sending heartbeats
        while True:
            for account in self.accounts:
                if is_token_expired(account):
                    print(f"{Fore.YELLOW}[WARNING] Wallet {account['wallet_number']}: Token expired for wallet {account['decoded']['wallet_address']}")
                    account["status"] = "expired"
                    continue

                self.send_heartbeat(account)
                time.sleep(1)  # Jeda 1 detik antara akun

            time.sleep(APP_CONFIG["heartbeat_interval"] / 1000)  # Jeda sesuai interval

# Main
def main():
    """Fungsi utama untuk menjalankan bot."""
    display_banner()  # Tampilkan banner

    # Tanyakan apakah pengguna ingin menggunakan proxy
    use_proxy = ask_proxy_usage()

    # Jalankan layanan heartbeat
    service = HeartbeatService(use_proxy)
    try:
        service.start()
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}[INFO] Heartbeat service stopped.")

if __name__ == "__main__":
    main()