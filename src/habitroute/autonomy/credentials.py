"""Proxy-side workload identity and OAuth token exchange.

This module is intended to run inside the isolated egress-proxy trust boundary.
Raw workload SVIDs and upstream access tokens must never enter agent context,
workflow inputs, journal events, logs, traces, or returned operation outputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Mapping, Protocol
from urllib.parse import urlsplit

from ..machine import (
    HarnessOperationResult,
    OperationEffect,
    OperationNotExecuted,
    OperationOutcome,
    OperationStep,
)
from .capabilities import (
    CapabilityVerifier,
    CapabilityToken,
    DecisionKind,
    PolicyRequest,
    canonical_json,
    deterministic_idempotency_key,
    evaluate_capability,
)
from .guards import SnapshotVerifier, require_recovery_snapshot
from .ledger import BudgetExceeded, IdempotencyConflict, SQLiteFlowJournal
from .worker import (
    ApprovalEvidence,
    ApprovalVerifier,
    OperationDescriptor,
    RecoveryPlan,
    _secret_mapping,
    approval_request_sha256,
)

_TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
_JWT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:jwt"
_ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
_SCOPE = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
_COMPACT_JWT_PART = re.compile(r"^[A-Za-z0-9_-]+$")


class CredentialExchangeError(RuntimeError):
    """Safe-to-report error; never contains a token or broker response body."""


@dataclass(frozen=True, slots=True, repr=False)
class WorkloadJWT:
    """JWT-SVID acquired from the local SPIFFE Workload API."""
    value: str = field(repr=False)
    spiffe_id: str
    expires_at: int

    def __post_init__(self) -> None:
        parts = self.value.split(".")
        if len(parts) != 3 or any(not _COMPACT_JWT_PART.fullmatch(x) for x in parts):
            raise ValueError("workload identity must be a compact signed JWT")
        parsed = urlsplit(self.spiffe_id)
        if parsed.scheme != "spiffe" or not parsed.netloc or not parsed.path.strip("/"):
            raise ValueError("workload identity must be a non-root SPIFFE ID")
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("SPIFFE ID contains forbidden URI components")
        if self.expires_at <= 0:
            raise ValueError("workload identity expiry must be positive")

    def __repr__(self) -> str:
        return "WorkloadJWT(<redacted>)"


class WorkloadJWTSource(Protocol):
    """Adapter over SPIFFE Workload API; broker verifies the JWT-SVID signature."""
    def fetch_jwt_svid(self, audience: str) -> WorkloadJWT: ...


class FormTokenExchangeTransport(Protocol):
    """HTTPS/mTLS transport to the credential broker."""
    def post_form(self, endpoint: str, form: Mapping[str, str]) -> Mapping[str, object]: ...


def _spiffe_workload_api_message_types():
    """Build the stable SPIFFE JWT-SVID protobuf messages without protoc.

    The field numbers and RPC paths are taken from the canonical
    standards/workloadapi.proto. The optional spiffe extra supplies grpcio
    and protobuf; this avoids checking generated code into the core package.
    """
    try:
        from google.protobuf import descriptor_pb2, descriptor_pool, message_factory, struct_pb2
    except ImportError as exc:
        raise RuntimeError(
            "SPIFFE Workload API support requires the 'spiffe' optional dependencies"
        ) from exc

    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(struct_pb2.DESCRIPTOR.serialized_pb)
    file_proto = descriptor_pb2.FileDescriptorProto()
    file_proto.name = "habitroute_spiffe_workloadapi.proto"
    file_proto.syntax = "proto3"
    file_proto.dependency.append("google/protobuf/struct.proto")

    F = descriptor_pb2.FieldDescriptorProto

    def add_message(name: str, fields: tuple[tuple[str, int, int, int, str | None], ...]):
        message = file_proto.message_type.add()
        message.name = name
        for field_name, number, field_type, label, type_name in fields:
            field = message.field.add()
            field.name = field_name
            field.number = number
            field.type = field_type
            field.label = label
            if type_name:
                field.type_name = type_name

    add_message("JWTSVIDRequest", (
        ("audience", 1, F.TYPE_STRING, F.LABEL_REPEATED, None),
        ("spiffe_id", 2, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
    ))
    add_message("JWTSVID", (
        ("spiffe_id", 1, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
        ("svid", 2, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
        ("hint", 3, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
    ))
    add_message("JWTSVIDResponse", (
        ("svids", 1, F.TYPE_MESSAGE, F.LABEL_REPEATED, ".JWTSVID"),
    ))
    add_message("ValidateJWTSVIDRequest", (
        ("audience", 1, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
        ("svid", 2, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
    ))
    add_message("ValidateJWTSVIDResponse", (
        ("spiffe_id", 1, F.TYPE_STRING, F.LABEL_OPTIONAL, None),
        ("claims", 2, F.TYPE_MESSAGE, F.LABEL_OPTIONAL, ".google.protobuf.Struct"),
    ))
    pool.AddSerializedFile(file_proto.SerializeToString())

    return {
        name: message_factory.GetMessageClass(pool.FindMessageTypeByName(name))
        for name in (
            "JWTSVIDRequest", "JWTSVID", "JWTSVIDResponse",
            "ValidateJWTSVIDRequest", "ValidateJWTSVIDResponse",
        )
    }


class SpiffeWorkloadAPIJWTSource:
    """Fetch and validate JWT-SVIDs through the local SPIFFE Workload API.

    The Workload API is gRPC and should normally be exposed through a Unix
    domain socket. Both RPCs include the mandatory workload.spiffe.io=true
    metadata. The agent's ValidateJWTSVID RPC validates signature, audience
    and expiry using its trust bundle; this class does not implement JWT
    signature verification itself.

    A fake channel can be injected for deterministic unit tests. Production
    callers should leave channel unset and point socket_path at the local
    SPIFFE Workload Endpoint socket.
    """

    _METADATA = (("workload.spiffe.io", "true"),)
    _FETCH_METHOD = "/SpiffeWorkloadAPI/FetchJWTSVID"
    _VALIDATE_METHOD = "/SpiffeWorkloadAPI/ValidateJWTSVID"

    def __init__(
        self,
        *,
        expected_spiffe_id: str,
        socket_path: str = "/run/spire/sockets/agent.sock",
        timeout_seconds: float = 2.0,
        channel=None,
    ) -> None:
        parsed = urlsplit(expected_spiffe_id)
        if (
            parsed.scheme != "spiffe" or not parsed.netloc
            or not parsed.path.strip("/") or parsed.query or parsed.fragment
            or parsed.username or parsed.password
        ):
            raise ValueError("expected workload identity must be a non-root SPIFFE ID")
        if timeout_seconds <= 0:
            raise ValueError("Workload API timeout must be positive")
        self._expected_spiffe_id = expected_spiffe_id
        self._timeout = timeout_seconds
        self._owns_channel = channel is None
        self._classes = _spiffe_workload_api_message_types()
        if channel is None:
            try:
                import grpc
            except ImportError as exc:
                raise RuntimeError(
                    "SPIFFE Workload API support requires the 'spiffe' optional dependencies"
                ) from exc
            if not socket_path or not socket_path.startswith("/") or "\x00" in socket_path:
                raise ValueError("SPIFFE Workload API socket_path must be absolute")
            target = "unix://" + socket_path
            channel = grpc.insecure_channel(target)
        self._channel = channel
        self._fetch = self._channel.unary_unary(
            self._FETCH_METHOD,
            request_serializer=lambda request: request.SerializeToString(),
            response_deserializer=self._classes["JWTSVIDResponse"].FromString,
        )
        self._validate = self._channel.unary_unary(
            self._VALIDATE_METHOD,
            request_serializer=lambda request: request.SerializeToString(),
            response_deserializer=self._classes["ValidateJWTSVIDResponse"].FromString,
        )

    def fetch_jwt_svid(self, audience: str) -> WorkloadJWT:
        if not audience or not audience.strip():
            raise ValueError("SPIFFE JWT-SVID audience must be non-empty")
        request_type = self._classes["JWTSVIDRequest"]
        request = request_type(
            audience=[audience],
            spiffe_id=self._expected_spiffe_id,
        )
        try:
            response = self._fetch(
                request, timeout=self._timeout, metadata=self._METADATA,
            )
            matches = [
                item for item in response.svids
                if item.spiffe_id == self._expected_spiffe_id and item.svid
            ]
            if len(matches) != 1:
                raise CredentialExchangeError(
                    "SPIFFE Workload API did not return exactly one configured workload identity"
                )

            jwt = matches[0].svid
            validate_type = self._classes["ValidateJWTSVIDRequest"]
            validate_request = validate_type(audience=audience, svid=jwt)
            validated = self._validate(
                validate_request, timeout=self._timeout, metadata=self._METADATA,
            )
            if validated.spiffe_id != self._expected_spiffe_id:
                raise CredentialExchangeError(
                    "SPIFFE agent validated an unexpected workload identity"
                )
            from google.protobuf.json_format import MessageToDict
            claims = MessageToDict(validated.claims, preserving_proto_field_name=True)
            subject = claims.get("sub")
            token_audience = claims.get("aud")
            expires = claims.get("exp")
            aud_set = (
                {token_audience} if isinstance(token_audience, str)
                else set(token_audience) if isinstance(token_audience, (list, tuple))
                else set()
            )
            if subject != self._expected_spiffe_id:
                raise CredentialExchangeError("validated JWT-SVID subject does not match its SPIFFE identity")
            if aud_set != {audience}:
                raise CredentialExchangeError("validated JWT-SVID audience is not restricted to the requested service")
            if (
                isinstance(expires, bool) or not isinstance(expires, (int, float))
                or not float(expires).is_integer()
            ):
                raise CredentialExchangeError("validated JWT-SVID has no valid integer expiry claim")
            expires_at = int(expires)
            if expires_at <= int(time.time()):
                raise CredentialExchangeError("SPIFFE agent returned an expired JWT-SVID")
            return WorkloadJWT(jwt, validated.spiffe_id, expires_at)
        except CredentialExchangeError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", None)
            code_value = code() if callable(code) else None
            safe_code = str(code_value) if code_value is not None else type(exc).__name__
            raise CredentialExchangeError(
                "SPIFFE Workload API request failed (" + safe_code + ")"
            ) from None

    def close(self) -> None:
        if self._owns_channel:
            close = getattr(self._channel, "close", None)
            if callable(close):
                close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class CredentialedRequestTransport(Protocol):
    """Provider HTTP transport; must not log or persist authorization_header."""
    def send(
        self,
        descriptor: OperationDescriptor,
        operation: OperationStep,
        inputs: Mapping[str, str],
        *,
        idempotency_key: str,
        authorization_header: str,
    ) -> HarnessOperationResult: ...


@dataclass(frozen=True, slots=True, repr=False)
class EphemeralAccessToken:
    """Short-lived upstream token; available only inside the proxy process."""
    _value: str = field(repr=False)
    resource: str
    audience: str
    scopes: frozenset[str]
    expires_at: int

    def __post_init__(self) -> None:
        if not self._value or any(ch.isspace() for ch in self._value):
            raise ValueError("access token is empty or malformed")
        if self.expires_at <= int(time.time()):
            raise ValueError("access token is expired")
        if not self.scopes:
            raise ValueError("access token must have at least one scope")

    def __repr__(self) -> str:
        return "EphemeralAccessToken(<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"

    def _authorization_header(self) -> str:
        """Internal proxy-to-provider use only; never expose to agent code."""
        if self.expires_at <= int(time.time()):
            raise CredentialExchangeError("upstream access token expired before dispatch")
        return "Bearer " + self._value

    def _contains_value(self, candidate: str) -> bool:
        return bool(candidate) and self._value in candidate


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward JWT-SVIDs or authorization codes to a redirect target.
        return None


class MutualTLSFormTransport:
    """Small HTTPS form client using a client certificate and a pinned CA file.

    Certificate/key files should be atomically refreshed from the SPIFFE
    Workload API (for example, through an approved SVID helper). A fresh TLS
    context is built per request so rotations are observed without restarting.
    """

    def __init__(
        self,
        *,
        ca_file: str,
        client_cert_file: str,
        client_key_file: str,
        timeout_seconds: float = 3.0,
        max_response_bytes: int = 65536,
    ) -> None:
        if timeout_seconds <= 0 or max_response_bytes < 1024:
            raise ValueError("invalid token transport limits")
        self._ca_file = ca_file
        self._cert_file = client_cert_file
        self._key_file = client_key_file
        self._timeout = timeout_seconds
        self._max_response = max_response_bytes

    @staticmethod
    def _validate_endpoint(endpoint: str) -> None:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme.lower() != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            raise ValueError("credential broker endpoint must be an absolute HTTPS URL without userinfo/query/fragment")

    def post_form(self, endpoint: str, form: Mapping[str, str]) -> Mapping[str, object]:
        self._validate_endpoint(endpoint)
        context = ssl.create_default_context(cafile=self._ca_file)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self._cert_file, self._key_file)
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise CredentialExchangeError("broker TLS verification is not enabled")
        body = urllib.parse.urlencode(dict(form)).encode("ascii")
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-store",
            },
        )
        opener = urllib.request.build_opener(
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=context),
        )
        try:
            with opener.open(request, timeout=self._timeout) as response:
                raw = response.read(self._max_response + 1)
            if len(raw) > self._max_response:
                raise CredentialExchangeError("credential broker response exceeded size limit")
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise CredentialExchangeError("credential broker returned an invalid response")
            return decoded
        except urllib.error.HTTPError as exc:
            # Do not include the response body, which could contain sensitive material.
            raise CredentialExchangeError(
                f"credential broker rejected token exchange (HTTP {exc.code})"
            ) from None
        except CredentialExchangeError:
            raise
        except Exception as exc:
            raise CredentialExchangeError(
                "credential broker transport failed (" + type(exc).__name__ + ")"
            ) from None


class OAuthTokenExchangeClient:
    """RFC 8693 client that exchanges a broker-audience JWT-SVID for one resource.

    The authorization server must validate the SPIFFE JWT-SVID against the
    corresponding SPIFFE trust bundle and enforce client/resource/scope policy.
    """

    def __init__(
        self,
        *,
        token_endpoint: str,
        broker_audience: str,
        workload_identity: WorkloadJWTSource,
        transport: FormTokenExchangeTransport,
        expected_spiffe_id: str,
        max_token_lifetime_seconds: int = 300,
    ) -> None:
        MutualTLSFormTransport._validate_endpoint(token_endpoint)
        if not broker_audience.strip():
            raise ValueError("broker audience must be non-empty")
        expected = urlsplit(expected_spiffe_id)
        if (
            expected.scheme != "spiffe" or not expected.netloc
            or not expected.path.strip("/") or expected.query or expected.fragment
            or expected.username or expected.password
        ):
            raise ValueError("expected proxy identity must be a non-root SPIFFE ID")
        if not 1 <= max_token_lifetime_seconds <= 900:
            raise ValueError("maximum upstream token lifetime must be between 1 and 900 seconds")
        self._endpoint = token_endpoint
        self._broker_audience = broker_audience
        self._expected_spiffe_id = expected_spiffe_id
        self._identity = workload_identity
        self._transport = transport
        self._max_lifetime = max_token_lifetime_seconds

    @staticmethod
    def _validate_resource(resource: str) -> None:
        parsed = urlsplit(resource)
        if (
            parsed.scheme.lower() != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
        ):
            raise ValueError("token exchange resource must be an absolute HTTPS origin")

    @staticmethod
    def _normalize_scopes(scopes: frozenset[str] | set[str]) -> frozenset[str]:
        normalized = frozenset(scopes)
        if not normalized or any(not _SCOPE.fullmatch(scope) for scope in normalized):
            raise ValueError("token exchange requires non-empty, valid operation scopes")
        return normalized

    def exchange(
        self, *, resource: str, audience: str, scopes: frozenset[str] | set[str],
        now: int | None = None,
    ) -> EphemeralAccessToken:
        self._validate_resource(resource)
        if not audience.strip():
            raise ValueError("resource-server audience must be non-empty")
        requested_scopes = self._normalize_scopes(scopes)
        current = int(time.time()) if now is None else int(now)

        svid = self._identity.fetch_jwt_svid(self._broker_audience)
        if not isinstance(svid, WorkloadJWT) or svid.expires_at <= current:
            raise CredentialExchangeError("SPIFFE Workload API returned an expired or invalid identity")
        if svid.spiffe_id != self._expected_spiffe_id:
            raise CredentialExchangeError("SPIFFE workload identity does not match the configured proxy principal")

        form = {
            "grant_type": _TOKEN_EXCHANGE_GRANT,
            "subject_token_type": _JWT_TOKEN_TYPE,
            "subject_token": svid.value,
            "resource": resource,
            "audience": audience,
            "scope": " ".join(sorted(requested_scopes)),
        }
        response = self._transport.post_form(self._endpoint, form)
        if not isinstance(response, Mapping):
            raise CredentialExchangeError("credential broker returned an invalid response")

        access_token = response.get("access_token")
        token_type = response.get("token_type")
        expires_in = response.get("expires_in")
        issued_type = response.get("issued_token_type", _ACCESS_TOKEN_TYPE)
        returned_scope = response.get("scope")

        if (
            not isinstance(access_token, str) or not access_token
            or len(access_token) > 16384 or any(ch.isspace() for ch in access_token)
        ):
            raise CredentialExchangeError("credential broker returned an invalid access token")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise CredentialExchangeError("credential broker returned an unsupported token type")
        if issued_type != _ACCESS_TOKEN_TYPE:
            raise CredentialExchangeError("credential broker returned an unexpected token type")
        if isinstance(expires_in, bool) or not isinstance(expires_in, int):
            raise CredentialExchangeError("credential broker returned an invalid token lifetime")
        if not 1 <= expires_in <= self._max_lifetime:
            raise CredentialExchangeError("credential broker token lifetime exceeds policy")
        if "refresh_token" in response:
            raise CredentialExchangeError("refresh tokens are not accepted by the proxy")

        if returned_scope is None:
            granted_scopes = requested_scopes  # RFC 8693: omitted scope means requested scope.
        elif isinstance(returned_scope, str):
            granted_scopes = frozenset(returned_scope.split())
        else:
            raise CredentialExchangeError("credential broker returned invalid scope metadata")
        if granted_scopes != requested_scopes:
            raise CredentialExchangeError("credential broker scope does not exactly match the operation scope")

        return EphemeralAccessToken(
            access_token, resource, audience, granted_scopes, current + expires_in,
        )


class UrllibJsonEgressTransport:
    """Minimal HTTPS JSON transport used only inside the isolated proxy process."""

    def __init__(self, *, timeout_seconds: float = 10.0, max_response_bytes: int = 1_048_576):
        if timeout_seconds <= 0 or max_response_bytes < 1024:
            raise ValueError("invalid upstream transport limits")
        self._timeout = timeout_seconds
        self._max_response = max_response_bytes

    def send(
        self,
        descriptor: OperationDescriptor,
        operation: OperationStep,
        inputs: Mapping[str, str],
        *,
        idempotency_key: str,
        authorization_header: str,
    ) -> HarnessOperationResult:
        if not descriptor.external:
            raise OperationNotExecuted("upstream transport accepts external descriptors only")
        url = descriptor.resource
        data = None
        if descriptor.method in {"GET", "HEAD"}:
            if inputs:
                separator = "&" if "?" in url else "?"
                url += separator + urllib.parse.urlencode(dict(inputs))
        else:
            data = json.dumps(
                dict(inputs), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=descriptor.method,
            headers={
                "Accept": "application/json",
                "Authorization": authorization_header,
                "Idempotency-Key": idempotency_key,
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        opener = urllib.request.build_opener(
            _NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        try:
            with opener.open(request, timeout=self._timeout) as response:
                raw = response.read(self._max_response + 1)
                status = response.status
            if len(raw) > self._max_response:
                return HarnessOperationResult(
                    OperationOutcome.UNKNOWN, error_code="upstream_response_too_large",
                )
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400 or exc.code in {408, 425, 429} or exc.code >= 500:
                outcome = OperationOutcome.UNKNOWN
            else:
                outcome = OperationOutcome.FAILED
            return HarnessOperationResult(
                outcome, error_code="upstream_http_" + str(exc.code),
            )
        except Exception:
            # The request might have reached the provider. The caller must reconcile.
            raise

        if status < 200 or status >= 300:
            return HarnessOperationResult(
                OperationOutcome.UNKNOWN, error_code="upstream_http_" + str(status),
            )
        if not raw:
            return HarnessOperationResult(OperationOutcome.SUCCEEDED)
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {"body": raw.decode("utf-8", errors="replace")}
        if isinstance(decoded, Mapping):
            outputs = tuple(
                (str(key), value if isinstance(value, str) else json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ))
                for key, value in decoded.items()
            )
        else:
            outputs = (("body", json.dumps(
                decoded, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )),)
        return HarnessOperationResult(OperationOutcome.SUCCEEDED, outputs=outputs)


class BrokeredEgressProxy:
    """Capability-, approval-, recovery- and credential-enforcing proxy adapter.

    Deploy this class in a separately isolated proxy process. The workload JWT
    source, token-exchange client, request transport and journal belong to that
    process, not the agent. The local SQLite journal is single-proxy reference
    persistence; clustered deployments require a shared transactional ledger.
    """

    def __init__(
        self,
        *,
        capability_broker: CapabilityVerifier,
        token_exchange: OAuthTokenExchangeClient,
        transport: CredentialedRequestTransport,
        journal: SQLiteFlowJournal,
        operation_descriptors: Mapping[str, OperationDescriptor],
        operation_steps: Mapping[str, OperationStep],
        audience_by_host: Mapping[str, str],
        scopes_by_operation: Mapping[str, frozenset[str]],
        approval_required_operations: frozenset[str] = frozenset(),
        approval_verifier: ApprovalVerifier | None = None,
        snapshot_verifier: SnapshotVerifier | None = None,
    ) -> None:
        self._broker = capability_broker
        self._exchange = token_exchange
        self._transport = transport
        self._journal = journal
        self._descriptors = dict(operation_descriptors)
        self._steps = dict(operation_steps)
        self._audiences = {host.lower(): audience for host, audience in audience_by_host.items()}
        self._scopes = {operation: frozenset(scopes) for operation, scopes in scopes_by_operation.items()}
        self._approval_required = frozenset(approval_required_operations)
        self._approval_verifier = approval_verifier
        self._snapshot_verifier = snapshot_verifier
        if (
            not self._descriptors
            or any(key != descriptor.operation_ref or not descriptor.external
                   for key, descriptor in self._descriptors.items())
        ):
            raise ValueError("proxy must declare an authoritative external operation catalogue")
        if set(self._scopes) != set(self._descriptors):
            raise ValueError("proxy operation scopes must exactly match its operation catalogue")
        if (
            set(self._steps) != set(self._descriptors)
            or any(key != step.operation_ref for key, step in self._steps.items())
        ):
            raise ValueError("proxy operation steps must exactly match its operation catalogue")
        allowed_hosts = {descriptor.host.lower() for descriptor in self._descriptors.values()}
        if not self._audiences or set(self._audiences) != allowed_hosts or any(
            not value.strip() for value in self._audiences.values()
        ):
            raise ValueError("proxy audiences must exactly match catalogue hosts")
        if not self._scopes or any(not scopes for scopes in self._scopes.values()):
            raise ValueError("proxy must declare non-empty scopes for allowed operations")
        if self._approval_required and self._approval_verifier is None:
            raise ValueError("approval-required operations need an independent verifier")

    def _deny(self, descriptor: OperationDescriptor, idempotency_key: str, reason: str) -> None:
        digest = hashlib.sha256(
            (idempotency_key + ":" + descriptor.operation_ref + ":" + reason).encode(),
        ).hexdigest()
        self._journal.append_audit(
            "proxy-deny:" + digest,
            "proxy_authorization_denied",
            {"operation_ref": descriptor.operation_ref, "reason": reason},
        )
        raise OperationNotExecuted("egress proxy denied operation: " + reason)

    def invoke(
        self,
        descriptor: OperationDescriptor,
        operation: OperationStep,
        inputs: Mapping[str, str],
        *,
        idempotency_key: str,
        capability_token: CapabilityToken | str,
        approval_evidence: ApprovalEvidence | None = None,
        recovery_plan: RecoveryPlan | None = None,
    ) -> HarnessOperationResult:
        trusted_descriptor = self._descriptors.get(operation.operation_ref)
        if trusted_descriptor is None:
            self._deny(descriptor, idempotency_key, "operation_not_in_proxy_catalogue")
        if descriptor != trusted_descriptor:
            self._deny(trusted_descriptor, idempotency_key, "untrusted_operation_descriptor")
        descriptor = trusted_descriptor
        trusted_step = self._steps[operation.operation_ref]
        if operation != trusted_step:
            self._deny(descriptor, idempotency_key, "untrusted_operation_step")
        operation = trusted_step
        if not descriptor.external:
            self._deny(descriptor, idempotency_key, "external_descriptor_required")
        if descriptor.operation_ref != operation.operation_ref:
            self._deny(descriptor, idempotency_key, "operation_descriptor_mismatch")
        if _secret_mapping(inputs):
            self._deny(descriptor, idempotency_key, "raw_secret_input_rejected")
        scopes = self._scopes.get(operation.operation_ref)
        audience = self._audiences.get(descriptor.host.lower())
        if scopes is None or audience is None:
            self._deny(descriptor, idempotency_key, "operation_audience_or_scope_not_configured")
        method_read = descriptor.method in {"GET", "HEAD"}
        if operation.effect is OperationEffect.READ_ONLY and not method_read:
            self._deny(descriptor, idempotency_key, "read_only_requires_get_or_head")
        if operation.effect is not OperationEffect.READ_ONLY and method_read:
            self._deny(descriptor, idempotency_key, "mutating_operation_cannot_use_get_or_head")

        try:
            claims = self._broker.verify(capability_token)
        except Exception:
            self._deny(descriptor, idempotency_key, "capability_verification_failed")
        ancestors = tuple(item.capability_id for item in claims.budget_chain)
        if self._journal.is_capability_revoked(claims.capability_id, ancestors):
            self._deny(descriptor, idempotency_key, "capability_or_ancestor_revoked")

        if descriptor.destructive:
            if recovery_plan is None or self._snapshot_verifier is None:
                self._deny(descriptor, idempotency_key, "destructive_operation_requires_recovery_evidence")
            try:
                require_recovery_snapshot(
                    recovery_plan.evidence, self._snapshot_verifier,
                    workflow_id=recovery_plan.workflow_id,
                    required_sequence=recovery_plan.required_sequence,
                    expected_state_sha256=recovery_plan.expected_state_sha256,
                    max_age_seconds=recovery_plan.max_age_seconds,
                )
            except Exception:
                self._deny(descriptor, idempotency_key, "recovery_evidence_verification_failed")

        requires_approval = (
            descriptor.approval_required
            or operation.operation_ref in claims.approval_required
            or operation.operation_ref in self._approval_required
        )
        approval_ok = False
        if requires_approval or approval_evidence is not None:
            now = int(time.time())
            request_digest = approval_request_sha256(
                descriptor, operation, inputs, idempotency_key, recovery_plan,
            )
            verifier = self._approval_verifier
            try:
                approval_ok = bool(
                    approval_evidence is not None
                    and verifier is not None
                    and approval_evidence.capability_id == claims.capability_id
                    and approval_evidence.operation_ref == descriptor.operation_ref
                    and approval_evidence.host.lower() == descriptor.host.lower()
                    and approval_evidence.resource == descriptor.resource
                    and approval_evidence.expires_at > now
                    and approval_evidence.request_sha256 == request_digest
                    and verifier.verify(approval_evidence, claims, descriptor, now)
                )
            except Exception:
                approval_ok = False
        decision = evaluate_capability(
            claims,
            PolicyRequest(
                descriptor.operation_ref, descriptor.host, descriptor.resource,
                descriptor.cost_units, requires_approval,
            ),
            approval_verified=approval_ok,
        )
        if decision.kind is not DecisionKind.ALLOW:
            self._deny(descriptor, idempotency_key, decision.reason)

        input_digest = hashlib.sha256(canonical_json(dict(inputs))).hexdigest()
        try:
            claim = self._journal.claim_invocation(
                capability_id=claims.capability_id,
                idempotency_key=idempotency_key,
                operation_ref=operation.operation_ref,
                effect=operation.effect.value,
                input_sha256=input_digest,
                estimated_cost=descriptor.cost_units,
                max_calls=claims.max_calls,
                max_cost=claims.max_cost,
                budget_chain=tuple(
                    (item.capability_id, item.max_calls, item.max_cost)
                    for item in claims.budget_chain
                ),
            )
        except (BudgetExceeded, IdempotencyConflict, PermissionError) as exc:
            self._deny(descriptor, idempotency_key, type(exc).__name__)
        if not claim.executable:
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code=claim.reason)

        # Token exchange happens before the provider request. A broker failure is
        # therefore a known non-dispatch and is safe to record as failed.
        try:
            credential = self._exchange.exchange(
                resource="https://" + descriptor.host.lower(),
                audience=audience,
                scopes=scopes,
            )
        except Exception:
            self._journal.finish_invocation(
                idempotency_key, "failed", "credential_exchange_failed",
            )
            return HarnessOperationResult(
                OperationOutcome.FAILED, error_code="credential_exchange_failed",
            )

        try:
            result = self._transport.send(
                descriptor, operation, inputs,
                idempotency_key=idempotency_key,
                authorization_header=credential._authorization_header(),
            )
        except OperationNotExecuted:
            self._journal.finish_invocation(
                idempotency_key, "failed", "provider_request_not_dispatched",
            )
            return HarnessOperationResult(
                OperationOutcome.FAILED, error_code="provider_request_not_dispatched",
            )
        except Exception:
            self._journal.finish_invocation(
                idempotency_key, "unknown", "provider_outcome_unknown",
            )
            return HarnessOperationResult(
                OperationOutcome.UNKNOWN, error_code="provider_outcome_unknown",
            )

        if not isinstance(result, HarnessOperationResult):
            self._journal.finish_invocation(
                idempotency_key, "unknown", "invalid_upstream_result",
            )
            return HarnessOperationResult(OperationOutcome.UNKNOWN, error_code="invalid_upstream_result")
        if any(
            credential._contains_value(key) or credential._contains_value(value)
            for key, value in result.outputs
        ):
            self._journal.finish_invocation(
                idempotency_key, "unknown", "credential_disclosure",
            )
            return HarnessOperationResult(
                OperationOutcome.UNKNOWN, error_code="upstream_credential_disclosure",
            )
        try:
            self._journal.finish_invocation(
                idempotency_key, result.outcome.value, result.error_code,
            )
        except Exception:
            return HarnessOperationResult(
                OperationOutcome.UNKNOWN, error_code="proxy_result_commit_failed",
            )
        return result
