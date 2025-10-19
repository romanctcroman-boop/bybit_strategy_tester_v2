import socket

def probe(host, port, timeout=3):
    print(f"\n-- probing {host}:{port} --")
    try:
        s = socket.create_connection((host, port), timeout)
    except Exception as e:
        print('connect error:', type(e).__name__, e)
        return
    try:
        try:
            data = s.recv(4096)
            print('received bytes len:', len(data))
            print('repr:', repr(data))
            print('hex:', data.hex())
        except Exception as e:
            print('recv error:', type(e).__name__, e)
    finally:
        s.close()

if __name__ == '__main__':
    probe('127.0.0.1', 5432)
    probe('127.0.0.1', 5433)
