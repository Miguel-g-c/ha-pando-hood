"""Optional exact certificate pin, checked before MQTT credentials are sent."""

import hashlib
import hmac
import re
import ssl


class PinnedContext(ssl.SSLContext):
    def __new__(cls, fingerprint):
        return super().__new__(cls, ssl.PROTOCOL_TLS_CLIENT)

    def __init__(self, fingerprint):
        normalized = fingerprint.replace(":", "").lower()
        if not re.fullmatch("[0-9a-f]{64}", normalized):
            raise ValueError("Expected SHA-256 certificate fingerprint (64 hex digits)")
        self.fingerprint = normalized
        self.check_hostname = False
        self.verify_mode = ssl.CERT_NONE
        self.minimum_version = ssl.TLSVersion.TLSv1_2

    def wrap_socket(self, *args, **kwargs):
        if kwargs.get("server_hostname") != "pando.iotpga.it":
            raise ssl.SSLError("Certificate pin is restricted to the Pando MQTT host")
        # Paho normally defers its handshake. Force it here so no MQTT CONNECT
        # packet (which contains credentials) can precede pin validation.
        kwargs["do_handshake_on_connect"] = True
        sock = super().wrap_socket(*args, **kwargs)
        certificate = sock.getpeercert(binary_form=True)
        # A completed TLS client handshake requires a server certificate.
        assert certificate is not None
        actual = hashlib.sha256(certificate).hexdigest()
        if not hmac.compare_digest(actual, self.fingerprint):
            sock.close()
            raise ssl.SSLError("Pando MQTT certificate pin mismatch")
        return sock


def mqtt_context(fingerprint=""):
    if fingerprint:
        return PinnedContext(fingerprint)
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
