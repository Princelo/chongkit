from Crypto.Cipher import AES
import base64
import hashlib
import sys


def encrypt_string(key_string, plaintext):
    key = hashlib.sha256(key_string.encode()).digest()
    data = plaintext.encode('utf-8')
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    encoded_data = base64.b64encode(cipher.nonce + tag + ciphertext)
    encoded_data = encoded_data.decode('utf-8')
    return encoded_data


secret_key = open("private.words.secret", mode="r").read()
word = sys.argv[1]
if len(sys.argv) == 2:
    weight = "0"
else:
    weight = sys.argv[2]
with open("private.essay.encrypted", mode="a") as words:
    words.write("\n" + encrypt_string(secret_key, word + "\t" + weight))
