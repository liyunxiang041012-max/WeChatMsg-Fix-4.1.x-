"""
Verify captured key against WeChat databases (SQLCipher HMAC check)

LC044/WeChatMsg (留痕 MemoTrace) 配套工具 | 原作者: SiYuan
"""
import os
import hmac
import struct
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA512

# ---- Load key from file (NEVER hardcode your key for GitHub!) ----
KEY_HEX = None
key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wechat_db_key.txt')
if os.path.exists(key_file):
    with open(key_file, 'r') as f:
        KEY_HEX = f.read().strip()
if not KEY_HEX or len(KEY_HEX) != 64:
    print('[!] Key file not found or invalid.')
    print('    Place wechat_db_key.txt (64-char hex) in this directory,')
    print('    or run auto_extract.py to capture the key first.')
    exit(1)
SALT_SIZE = 16
KEY_SIZE = 32
ROUND_COUNT = 256000
PAGE_SIZE = 4096
HMAC_SHA512_SIZE = 64
IV_SIZE = 16
AES_BLOCK_SIZE = 16

passphrase = bytes.fromhex(KEY_HEX)

# Find DB directory automatically
# WeChat stores encrypted DBs under xwechat_files/<wxid>/db_storage/
search_paths = []

# Common WeChat data directories
common_bases = [
    os.path.expanduser(r'~\Documents\xwechat_files'),
    os.path.expanduser(r'~\Documents\WeChat Files'),
]

for base in common_bases:
    if os.path.exists(base):
        for root, dirs, files in os.walk(base):
            if 'db_storage' in root:
                search_paths.append(root)
                break
        if search_paths:
            break

if not search_paths:
    print('[!] Cannot find db_storage directory')
    exit(1)

print(f'[+] Found DB dir: {search_paths[0]}')

# Find a DB to test
def find_test_db(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.endswith('.db') and os.path.getsize(os.path.join(root, f)) > 4096:
                return os.path.join(root, f)
    return None

db_path = find_test_db(search_paths[0])
if not db_path:
    print('[!] No DB files found')
    exit(1)

print(f'[+] Testing with: {db_path}')
print(f'[+] Size: {os.path.getsize(db_path)} bytes')

# Verify key
with open(db_path, 'rb') as f:
    salt = f.read(SALT_SIZE)
    first_page = f.read(PAGE_SIZE - SALT_SIZE)

if not salt or len(salt) != SALT_SIZE:
    print('[!] File too small')
    exit(1)

mac_salt = bytes(x ^ 0x3a for x in salt)

# Derive keys
key = PBKDF2(passphrase, salt, dkLen=KEY_SIZE, count=ROUND_COUNT, hmac_hash_module=SHA512)
mac_key = PBKDF2(key, mac_salt, dkLen=KEY_SIZE, count=2, hmac_hash_module=SHA512)

# Compute HMAC
reserve = IV_SIZE + HMAC_SHA512_SIZE
reserve = ((reserve + AES_BLOCK_SIZE - 1) // AES_BLOCK_SIZE) * AES_BLOCK_SIZE

full_page = salt + first_page
mac = hmac.new(mac_key, full_page[SALT_SIZE:PAGE_SIZE - reserve + IV_SIZE], SHA512)
mac.update(struct.pack('<I', 1))
hash_mac = mac.digest()

hash_start = PAGE_SIZE - reserve + IV_SIZE
hash_end = hash_start + len(hash_mac)
stored_hash = full_page[hash_start:hash_end]

if hash_mac == stored_hash:
    print('\n[+] *** KEY VERIFIED! HMAC matches! ***')
    print(f'[+] Key: {KEY_HEX}')
    print(f'[+] Key length: {len(passphrase)} bytes')
    
    # Try decrypting first page
    page_key = PBKDF2(passphrase, salt, dkLen=KEY_SIZE, count=ROUND_COUNT, hmac_hash_module=SHA512)
    iv = full_page[PAGE_SIZE - reserve:PAGE_SIZE - reserve + IV_SIZE]
    
    cipher = AES.new(page_key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(first_page[:-reserve])
    
    # Check for SQLite header
    if decrypted[:16] == b'SQLite format 3\x00':
        print('[+] *** First page decrypts to SQLite header! ***')
    else:
        print(f'[+] First 32 bytes of decrypted page: {decrypted[:32].hex()}')
        print('[+] Key is correct but page format unexpected (may need different decryption)')
    
    # Save key (this file is gitignored, safe to keep locally)
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wechat_db_key.txt')
    with open(key_path, 'w') as f:
        f.write(KEY_HEX)
    print(f'\n[+] Key saved to: {key_path}')
else:
    print('\n[!] *** HMAC MISMATCH - key is WRONG! ***')
    print(f'[!] Expected: {stored_hash.hex()[:32]}...')
    print(f'[!] Got:      {hash_mac.hex()[:32]}...')
