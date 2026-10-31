"""
Pinata IPFS upload service for BlockTrace.

Uploads PDF reports (or any file bytes) to IPFS via Pinata's pinFileToIPFS
REST endpoint. Credentials come from environment variables — never hardcoded.

Usage:
    from pinata_service import upload_pdf_to_pinata
    result = upload_pdf_to_pinata(pdf_bytes, "investigation_report.pdf")
    # result = {"cid": "Qm...", "ipfs_url": "ipfs://Qm...", "gateway_url": "https://..."}
"""

import os
import requests
from config_errors import not_configured, rejected_credentials
from dotenv import load_dotenv

load_dotenv(override=True)

PINATA_JWT = os.getenv("PINATA_JWT")
PINATA_GATEWAY = os.getenv("PINATA_GATEWAY")  # e.g. "https://gateway.pinata.cloud"

PINATA_PIN_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"
PINATA_PIN_JSON_URL = "https://api.pinata.cloud/pinning/pinJSONToIPFS"

# Timeout in seconds for the upload request (connect, read)
PINATA_TIMEOUT = (10, 120)


class PinataUploadError(Exception):
    """Raised when a Pinata upload fails for any reason."""
    pass


def upload_json_to_pinata(data: dict, name: str) -> dict:
    """Uploads arbitrary JSON data to IPFS via Pinata's pinJSONToIPFS endpoint.

    Args:
        data: The Python dict / JSON data to pin.
        name: Name shown in the Pinata dashboard (e.g. "BlockTrace_Case_BT-2026-0001").

    Returns:
        dict with keys:
            cid         — the IPFS content identifier (CIDv1)
            gateway_url — HTTPS gateway link for direct access

    Raises:
        PinataUploadError on auth failure, timeout, or any non-200 response.
        ValueError if PINATA_JWT is not configured.
    """
    if not PINATA_JWT:
        raise ValueError(not_configured("Publishing to IPFS", "PINATA_JWT"))

    gateway_base = (PINATA_GATEWAY or "https://gateway.pinata.cloud").rstrip("/")

    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json",
    }

    payload = {
        "pinataOptions": {"cidVersion": 1},
        "pinataMetadata": {"name": name},
        "pinataContent": data,
    }

    try:
        response = requests.post(
            PINATA_PIN_JSON_URL,
            headers=headers,
            json=payload,
            timeout=PINATA_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise PinataUploadError("Pinata JSON upload timed out.")
    except requests.exceptions.ConnectionError as exc:
        raise PinataUploadError(f"Could not connect to Pinata: {exc}")
    except requests.exceptions.RequestException as exc:
        raise PinataUploadError(f"Pinata JSON upload request failed: {exc}")

    if response.status_code == 401:
        raise PinataUploadError(rejected_credentials("Pinata (IPFS)", "PINATA_JWT"))

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("reason", response.text)
        except Exception:
            detail = response.text[:300]
        raise PinataUploadError(f"Pinata returned HTTP {response.status_code}: {detail}")

    result = response.json()
    cid = result.get("IpfsHash")
    if not cid:
        raise PinataUploadError("Pinata response did not include an IpfsHash.")

    return {
        "cid": cid,
        "gateway_url": f"{gateway_base}/ipfs/{cid}",
    }


def upload_pdf_to_pinata(pdf_bytes: bytes, filename: str, investigation_id: str = None) -> dict:
    """Uploads a PDF (as raw bytes) to IPFS via Pinata's pinFileToIPFS endpoint.

    Args:
        pdf_bytes: The raw bytes of the PDF file.
        filename: The filename to associate with the pin (e.g. "investigation_report.pdf").
        investigation_id: Optional investigation/case identifier used as pinning metadata name.

    Returns:
        dict with keys:
            cid         — the IPFS content identifier (CIDv0 or CIDv1)
            ipfs_url    — canonical ipfs:// URI
            gateway_url — HTTPS gateway link for direct browser access

    Raises:
        PinataUploadError on auth failure, timeout, or any non-200 response.
        ValueError if PINATA_JWT is not configured.
    """
    if not PINATA_JWT:
        raise ValueError(not_configured("Publishing to IPFS", "PINATA_JWT"))

    gateway_base = (PINATA_GATEWAY or "https://gateway.pinata.cloud").rstrip("/")

    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
    }

    # Pinata accepts multipart form data: the file and optional JSON metadata.
    files = {
        "file": (filename, pdf_bytes, "application/pdf"),
    }

    # Pinning metadata — the name shown in the Pinata dashboard.
    metadata_name = investigation_id or filename
    data = {
        "pinataMetadata": '{"name": "' + metadata_name.replace('"', '\\"') + '"}',
        "pinataOptions": '{"cidVersion": 1}',
    }

    try:
        response = requests.post(
            PINATA_PIN_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=PINATA_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise PinataUploadError(
            "Pinata upload timed out. The file may be too large or the service is slow — try again."
        )
    except requests.exceptions.ConnectionError as exc:
        raise PinataUploadError(f"Could not connect to Pinata: {exc}")
    except requests.exceptions.RequestException as exc:
        raise PinataUploadError(f"Pinata request failed: {exc}")

    if response.status_code == 401:
        raise PinataUploadError(rejected_credentials("Pinata (IPFS)", "PINATA_JWT"))

    if response.status_code != 200:
        # Try to extract a human-readable error from the response body.
        try:
            detail = response.json().get("error", {}).get("reason", response.text)
        except Exception:
            detail = response.text[:300]
        raise PinataUploadError(
            f"Pinata returned HTTP {response.status_code}: {detail}"
        )

    result = response.json()
    cid = result.get("IpfsHash")
    if not cid:
        raise PinataUploadError("Pinata response did not include an IpfsHash.")

    return {
        "cid": cid,
        "ipfs_url": f"ipfs://{cid}",
        "gateway_url": f"{gateway_base}/ipfs/{cid}",
    }


def upload_encrypted_file_to_pinata(file_bytes: bytes, filename: str, metadata_name: str = None) -> dict:
    """Uploads an encrypted case snapshot file to IPFS via Pinata pinFileToIPFS.

    Args:
        file_bytes: Encrypted envelope bytes.
        filename: Filename (e.g. '<case_number>.enc').
        metadata_name: Optional name for Pinata dashboard.

    Returns:
        dict with keys: cid, ipfs_url, gateway_url.
    """
    if not PINATA_JWT:
        raise ValueError(not_configured("Publishing to IPFS", "PINATA_JWT"))

    gateway_base = (PINATA_GATEWAY or "https://gateway.pinata.cloud").strip().rstrip("/")
    if not gateway_base.startswith("http"):
        gateway_base = f"https://{gateway_base}"

    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
    }

    files = {
        "file": (filename, file_bytes, "application/octet-stream"),
    }

    meta_name = metadata_name or filename
    data = {
        "pinataMetadata": '{"name": "' + meta_name.replace('"', '\\"') + '"}',
        "pinataOptions": '{"cidVersion": 1}',
    }

    try:
        response = requests.post(
            PINATA_PIN_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=PINATA_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise PinataUploadError("Pinata upload timed out.")
    except requests.exceptions.ConnectionError as exc:
        raise PinataUploadError(f"Could not connect to Pinata: {exc}")
    except requests.exceptions.RequestException as exc:
        raise PinataUploadError(f"Pinata request failed: {exc}")

    if response.status_code == 401:
        raise PinataUploadError(rejected_credentials("Pinata (IPFS)", "PINATA_JWT"))

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("reason", response.text)
        except Exception:
            detail = response.text[:300]
        raise PinataUploadError(f"Pinata returned HTTP {response.status_code}: {detail}")

    result = response.json()
    cid = result.get("IpfsHash")
    if not cid:
        raise PinataUploadError("Pinata response did not include an IpfsHash.")

    return {
        "cid": cid,
        "ipfs_url": f"ipfs://{cid}",
        "gateway_url": f"{gateway_base}/ipfs/{cid}",
    }


def download_file_from_ipfs(cid: str, max_bytes: int = 25 * 1024 * 1024, timeout: int = 15) -> bytes:
    """Downloads a file artifact from IPFS using the configured PINATA_GATEWAY
    with fallback to public IPFS gateways.

    Args:
        cid: The IPFS CID.
        max_bytes: Maximum allowed bytes (default 25 MB).
        timeout: Request timeout in seconds.

    Returns:
        bytes: Raw content of the downloaded file.

    Raises:
        PinataUploadError: If file cannot be retrieved or exceeds max_bytes.
    """
    configured_gw = (os.getenv("PINATA_GATEWAY") or "https://gateway.pinata.cloud").strip().rstrip("/")
    if not configured_gw.startswith("http"):
        configured_gw = f"https://{configured_gw}"

    candidate_urls = [
        f"{configured_gw}/ipfs/{cid}",
        f"https://gateway.pinata.cloud/ipfs/{cid}",
        f"https://ipfs.io/ipfs/{cid}",
        f"https://cloudflare-ipfs.com/ipfs/{cid}",
    ]

    headers = {}
    jwt = os.getenv("PINATA_JWT")
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    last_error = None
    for url in candidate_urls:
        try:
            req_headers = headers if ("mypinata.cloud" in url or "pinata.cloud" in url) else {}
            resp = requests.get(url, headers=req_headers, stream=True, timeout=timeout)
            if resp.status_code == 200:
                chunks = []
                total = 0
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        chunks.append(chunk)
                        total += len(chunk)
                        if total > max_bytes:
                            raise PinataUploadError(f"IPFS artifact exceeds {max_bytes} bytes limit.")
                return b"".join(chunks)
            else:
                last_error = f"Gateway HTTP {resp.status_code}"
        except Exception as exc:
            last_error = str(exc)

    raise PinataUploadError(f"Could not retrieve file for CID {cid} from IPFS: {last_error}")

