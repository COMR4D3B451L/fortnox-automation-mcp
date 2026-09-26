"""Small, testable Fortnox REST client.

The client deliberately uses the Python standard library so the offline core can
be installed before credentials and dependency management are decided.
"""
from __future__ import annotations

import json
import mimetypes
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping


class FortnoxAPIError(RuntimeError):
    def __init__(self, status: int | None, message: str, payload: Any = None):
        super().__init__(f"Fortnox API error{f' ({status})' if status else ''}: {message}")
        self.status, self.payload = status, payload


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, str, Mapping[str, str], bytes | None], Response]


def _urllib_transport(url: str, method: str, headers: Mapping[str, str], body: bytes | None) -> Response:
    req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return Response(res.status, dict(res.headers.items()), res.read())
    except urllib.error.HTTPError as exc:
        return Response(exc.code, dict(exc.headers.items()), exc.read())


class FortnoxClient:
    """Fortnox API client with resource helpers and injectable transport."""

    def __init__(self, *, access_token: str | None = None, refresh_token: str | None = None,
                 client_id: str | None = None, client_secret: str | None = None,
                 base_url: str | None = None, company_id: str | None = None,
                 tenant_id: str | None = None,
                 transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep):
        self.base_url = (base_url or os.getenv("FORTNOX_BASE_URL", "https://api.fortnox.se")).rstrip("/")
        self.access_token = access_token or os.getenv("FORTNOX_ACCESS_TOKEN")
        self.refresh_token = refresh_token or os.getenv("FORTNOX_REFRESH_TOKEN")
        self.client_id = client_id or os.getenv("FORTNOX_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("FORTNOX_CLIENT_SECRET")
        self.company_id = company_id or os.getenv("FORTNOX_COMPANY_ID")
        self.tenant_id = tenant_id or os.getenv("FORTNOX_TENANT_ID")
        self.transport = transport or _urllib_transport
        self.sleep = sleep
        self._last_response: Response | None = None

    def _headers(self) -> dict[str, str]:
        if not self.access_token:
            raise FortnoxAPIError(None, "FORTNOX_ACCESS_TOKEN is not configured")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
        if self.company_id:
            headers["Client-Company-ID"] = self.company_id
        if self.tenant_id:
            headers["TenantId"] = self.tenant_id
        return headers

    @staticmethod
    def _decode(response: Response) -> Any:
        if not response.body:
            return None
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FortnoxAPIError(response.status, "Invalid JSON response", response.body[:500]) from exc

    @staticmethod
    def _persist_env_values(values: Mapping[str, str]) -> None:
        """Persist rotated OAuth tokens without printing or broadening permissions."""
        from pathlib import Path
        env_path = Path(os.getenv("FORTNOX_ENV_FILE", "/root/fortnox-automation/.env"))
        if not env_path.exists():
            return
        lines = env_path.read_text(encoding="utf-8").splitlines()
        replaced: set[str] = set()
        output: list[str] = []
        for line in lines:
            key = line.split("=", 1)[0] if "=" in line else ""
            if key in values:
                output.append(f"{key}={values[key]}")
                replaced.add(key)
            else:
                output.append(line)
        output.extend(f"{key}={value}" for key, value in values.items() if key not in replaced)
        env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
        os.chmod(env_path, 0o600)

    def refresh_access_token(self) -> dict[str, Any]:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise FortnoxAPIError(None, "OAuth refresh requires client ID, client secret, and refresh token")
        form = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": self.refresh_token}).encode()
        auth = (self.client_id + ":" + self.client_secret).encode()
        import base64
        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
                   "Authorization": "Basic " + base64.b64encode(auth).decode()}
        response = self.transport(self.base_url + "/oauth-v1/token", "POST", headers, form)
        payload = self._decode(response)
        if response.status >= 400 or not isinstance(payload, dict) or "access_token" not in payload:
            raise FortnoxAPIError(response.status, "OAuth token refresh failed", payload)
        self.access_token = payload["access_token"]
        self.refresh_token = payload.get("refresh_token", self.refresh_token)
        self._persist_env_values({"FORTNOX_ACCESS_TOKEN": self.access_token,
                                  "FORTNOX_REFRESH_TOKEN": self.refresh_token or ""})
        return payload

    def request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None,
                json_body: Any = None, retries: int = 2) -> Any:
        path = "/" + path.lstrip("/")
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = self.base_url + path + ("?" + query if query else "")
        body = None if json_body is None else json.dumps(json_body).encode()
        headers = self._headers()
        if body is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(retries + 1):
            response = self.transport(url, method.upper(), headers, body)
            self._last_response = response
            payload = self._decode(response)
            if response.status == 401 and self.refresh_token and attempt == 0:
                self.refresh_access_token()
                headers = self._headers()
                continue
            # Fortnox has no documented native idempotency key. Never retry a
            # mutating request automatically after it may have reached the API.
            retryable_method = method.upper() in {"GET", "HEAD", "OPTIONS"}
            if (response.status == 429 or response.status >= 500) and retryable_method:
                if attempt < retries:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else min(2 ** attempt, 8)
                    except ValueError:
                        delay = min(2 ** attempt, 8)
                    self.sleep(delay)
                    continue
            if response.status >= 400:
                message = "request failed"
                if isinstance(payload, dict):
                    error_info = payload.get("ErrorInformation")
                    if isinstance(error_info, dict):
                        message = str(error_info.get("message") or error_info.get("error") or error_info)
                    else:
                        message = str(payload.get("message") or payload.get("error") or payload)
                raise FortnoxAPIError(response.status, message, payload)
            return payload
        raise FortnoxAPIError(response.status, "request failed after retries", payload)

    def request_multipart(self, method: str, path: str, *, file_field: str,
                          file_name: str, file_bytes: bytes, content_type: str | None = None,
                          params: Mapping[str, Any] | None = None) -> Any:
        """Send one file as multipart/form-data without retrying the mutation."""
        if len(file_bytes) > 50 * 1024 * 1024:
            raise ValueError("attachment exceeds the 50 MiB safety limit")
        boundary = "----HermesFortnox" + uuid.uuid4().hex
        mime = content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        body = (f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n").encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
        path = "/" + path.lstrip("/")
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = self.base_url + path + ("?" + query if query else "")
        headers = self._headers()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        response = self.transport(url, method.upper(), headers, body)
        self._last_response = response
        payload = self._decode(response)
        if response.status >= 400:
            message = str(payload)
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("error") or payload)
            raise FortnoxAPIError(response.status, message, payload)
        return payload

    def upload_archive_file(self, file_path: str | os.PathLike[str], *, path: str | None = None,
                            folder_id: str | None = None) -> Any:
        from pathlib import Path
        source = Path(file_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        return self.request_multipart("POST", "/3/archive", file_field="file",
                                      file_name=source.name, file_bytes=source.read_bytes(),
                                      params={"path": path, "folderid": folder_id})

    def connect_voucher_file(self, file_id: str, *, voucher_series: str,
                             voucher_number: int | str, voucher_year: int,
                             voucher_description: str | None = None) -> Any:
        connection = {"FileId": str(file_id), "VoucherSeries": voucher_series,
                      "VoucherNumber": str(voucher_number)}
        # VoucherDescription and VoucherYear are returned by Fortnox but read-only on create.
        return self.request("POST", "/3/voucherfileconnections",
                            json_body={"VoucherFileConnection": connection})

    def list_voucher_file_connections(self, **params: Any) -> list[dict[str, Any]]:
        payload = self.request("GET", "/3/voucherfileconnections", params=params) or {}
        return payload.get("VoucherFileConnections", []) if isinstance(payload, dict) else []

    def list(self, resource: str, *, params: Mapping[str, Any] | None = None,
             page_size: int = 100, max_items: int | None = None) -> list[dict[str, Any]]:
        """Fetch all pages; Fortnox list responses commonly wrap rows by resource name."""
        result: list[dict[str, Any]] = []
        page = 1
        while True:
            query = dict(params or {})
            query.setdefault("limit", page_size)
            query["page"] = page
            payload = self.request("GET", f"/3/{resource[:1].lower() + resource[1:]}", params=query) or {}
            rows = payload.get(resource) if isinstance(payload, dict) else None
            if rows is None and isinstance(payload, dict):
                rows = next((v for v in payload.values() if isinstance(v, list)), [])
            rows = rows or []
            result.extend(x for x in rows if isinstance(x, dict))
            if max_items is not None and len(result) >= max_items:
                return result[:max_items]
            meta = payload.get("MetaInformation", {}) if isinstance(payload, dict) else {}
            total_pages = meta.get("@TotalPages") if isinstance(meta, dict) else None
            current_page = meta.get("@CurrentPage") if isinstance(meta, dict) else None
            if total_pages is not None and current_page is not None:
                if int(current_page) >= int(total_pages):
                    return result
            elif len(rows) < page_size:
                return result
            page += 1

    # Explicit helpers make the supported surface discoverable and auditable.
    def get_invoice(self, document_number: str) -> Any:
        return self.request("GET", f"/3/invoices/{urllib.parse.quote(str(document_number))}")

    def list_invoices(self, *, page_size: int = 100, max_items: int | None = None, **params: Any) -> list[dict[str, Any]]:
        return self.list("Invoices", params=params, page_size=page_size, max_items=max_items)

    def list_customers(self, *, page_size: int = 100, max_items: int | None = None, **params: Any) -> list[dict[str, Any]]:
        return self.list("Customers", params=params, page_size=page_size, max_items=max_items)

    def list_vouchers(self, *, page_size: int = 100, max_items: int | None = None, **params: Any) -> list[dict[str, Any]]:
        return self.list("Vouchers", params=params, page_size=page_size, max_items=max_items)

    def create_invoice(self, invoice: Mapping[str, Any]) -> Any:
        return self.request("POST", "/3/invoices", json_body={"Invoice": dict(invoice)})

    def create_voucher(self, voucher: Mapping[str, Any]) -> Any:
        payload = dict(voucher)
        if "Voucher" not in payload:
            payload = {"Voucher": payload}
        return self.request("POST", "/3/vouchers", json_body=payload)

    def delete_voucher(self, voucher_series: str, voucher_number: str | int, *,
                       financialyear: int | str | None = None, confirm: bool = False) -> Any:
        """Delete one voucher after an explicit caller confirmation.

        Deletion is an irreversible financial mutation. The helper therefore
        requires ``confirm=True`` and disables automatic retries for the DELETE
        request. The caller must separately enforce user approval, period-lock,
        attachment, and audit-policy checks before calling this method.
        """
        if not confirm:
            raise ValueError("delete_voucher requires explicit confirm=True")
        series = urllib.parse.quote(str(voucher_series), safe="")
        number = urllib.parse.quote(str(voucher_number), safe="")
        return self.request("DELETE", f"/3/vouchers/{series}/{number}",
                            params={"financialyear": financialyear}, retries=0)

    def update_invoice(self, document_number: str, invoice: Mapping[str, Any]) -> Any:
        return self.request("PUT", f"/3/invoices/{urllib.parse.quote(str(document_number))}",
                            json_body={"Invoice": dict(invoice)})
