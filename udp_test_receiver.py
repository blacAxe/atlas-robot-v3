import socket
from datetime import datetime

UDP_IP = "0.0.0.0"
UDP_PORT = 4210
BUFFER_SIZE = 4096


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.bind((UDP_IP, UDP_PORT))
    except OSError as exc:
        print(f"Could not listen on UDP port {UDP_PORT}: {exc}")
        print("Make sure another program is not already using port 4210.")
        return

    print(f"Listening for Atlas UDP telemetry on {UDP_IP}:{UDP_PORT}")
    print("Press Ctrl+C to stop.")
    print()

    try:
        while True:
            data, sender_address = sock.recvfrom(BUFFER_SIZE)

            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            message = data.decode("utf-8", errors="replace").strip()

            sender_ip, sender_port = sender_address

            print(
                f"[{timestamp}] "
                f"From {sender_ip}:{sender_port} | "
                f"{message}"
            )

    except KeyboardInterrupt:
        print("\nUDP receiver stopped.")

    finally:
        sock.close()


if __name__ == "__main__":
    main()