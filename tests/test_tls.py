import hashlib
import socket
import ssl
import threading
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from custom_components.pando_hood.tls import mqtt_context


@pytest.fixture
def server(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pando.iotpga.it")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now - timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    (tmp_path / "cert").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "key").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "cert", tmp_path / "key")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(3)
    received = []

    def serve():
        try:
            conn, _ = listener.accept()
            with context.wrap_socket(conn, server_side=True) as tls:
                received.append(tls.recv(100))
        except (OSError, ssl.SSLError):
            pass

    thread = threading.Thread(target=serve)
    thread.start()
    yield (
        listener.getsockname(),
        hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
        received,
    )
    listener.close()
    thread.join(timeout=4)


def test_wrong_pin_rejects_peer_before_any_credentials(server):
    address, _, received = server
    context = mqtt_context("00" * 32)
    with socket.create_connection(address) as sock:
        with pytest.raises(ssl.SSLError):
            with context.wrap_socket(
                sock, server_hostname="pando.iotpga.it", do_handshake_on_connect=False
            ) as tls:
                tls.sendall(b"credentials")
    assert b"credentials" not in received


def test_exact_pin_accepts_expired_certificate(server):
    address, pin, _ = server
    context = mqtt_context(pin)
    with socket.create_connection(address) as sock:
        with context.wrap_socket(
            sock, server_hostname="pando.iotpga.it", do_handshake_on_connect=False
        ) as tls:
            tls.sendall(b"accepted")


def test_default_context_requires_ca_and_hostname_validation():
    context = mqtt_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
