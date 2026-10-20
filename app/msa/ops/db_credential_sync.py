"""In-cluster credential propagation. Never logs Secret data, token or digest.

Only the three named Deployment template annotations can be changed. The Secret
is read only; no AWS API, DB password mutation or rollback is performed here.
"""
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.error
import urllib.request

DEPLOYMENTS = ("member-depl", "product-depl", "ordering-depl")
ANNOTATION = "final.project/db-secret-sha256"


class ApiError(RuntimeError):
    def __init__(self, status):
        super().__init__(f"Kubernetes API HTTP {status}")
        self.status = status


class Kube:
    def __init__(self):
        self.sa = Path("/var/run/secrets/kubernetes.io/serviceaccount")
        self.ns = os.environ.get("NAMESPACE", "soldesk")
        self.base = "https://kubernetes.default.svc"
        self.context = ssl.create_default_context(cafile=str(self.sa / "ca.crt"))

    def request(self, method, path, data=None):
        # Read a projected token each time; it can rotate during the job.
        headers = {"Authorization": "Bearer " + (self.sa / "token").read_text().strip()}
        payload = None
        if data is not None:
            headers["Content-Type"] = "application/merge-patch+json"
            payload = json.dumps(data).encode()
        request = urllib.request.Request(self.base + path, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=15) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # API response bodies can contain request data; never log them.
            raise ApiError(error.code) from None

    def secret(self):
        return self.request("GET", f"/api/v1/namespaces/{self.ns}/secrets/db-credentials")

    def deployment(self, name):
        return self.request("GET", f"/apis/apps/v1/namespaces/{self.ns}/deployments/{name}")

    def stamp(self, name, deployment, digest):
        return self.request("PATCH", f"/apis/apps/v1/namespaces/{self.ns}/deployments/{name}", {
            # Refuse an intervening GitOps/user change instead of overwriting it.
            "metadata": {"resourceVersion": deployment["metadata"]["resourceVersion"]},
            "spec": {"template": {"metadata": {"annotations": {ANNOTATION: digest}}}},
        })


def fingerprint(secret):
    value = secret.get("data", {}).get("DB_PW")
    if not value:
        raise ValueError("DB_PW key is absent")
    # Stable value fingerprint: resourceVersion/ESO refresh alone is not a change.
    return hashlib.sha256(value.encode()).hexdigest()


def ready(deployment, digest):
    spec = deployment.get("spec", {})
    if spec.get("template", {}).get("metadata", {}).get("annotations", {}).get(ANNOTATION) != digest:
        return False
    desired = spec.get("replicas", 1)
    status = deployment.get("status", {})
    return (desired > 0
            and status.get("observedGeneration", 0) >= deployment["metadata"].get("generation", 1)
            and status.get("updatedReplicas", 0) == desired
            and status.get("availableReplicas", 0) >= desired
            and status.get("replicas", 0) == desired)


def reconcile(api, timeout=240, clock=time.monotonic, sleep=time.sleep):
    digest = fingerprint(api.secret())
    # During initial sync, absence is a wait condition, not permission to create apps.
    initial = {}
    for name in DEPLOYMENTS:
        try:
            initial[name] = api.deployment(name)
        except ApiError as error:
            if error.status == 404:
                print("WAIT: application deployments are not all present")
                return "waiting"
            raise
    for name in DEPLOYMENTS:
        if fingerprint(api.secret()) != digest:
            raise RuntimeError("Secret changed again; next scheduled run will retry")
        deployment = initial[name]
        stamped = deployment.get("spec", {}).get("template", {}).get("metadata", {}).get("annotations", {}).get(ANNOTATION)
        if stamped != digest:
            print(f"UPDATE: {name}")
            api.stamp(name, deployment, digest)
        deadline = clock() + timeout
        while True:
            if fingerprint(api.secret()) != digest:
                raise RuntimeError("Secret changed during rollout; stopped before the next app")
            if ready(api.deployment(name), digest):
                print(f"READY: {name}")
                break
            if clock() >= deadline:
                raise TimeoutError(f"{name} readiness timed out; stopped before the next app")
            sleep(5)
    print("PASS: DB credential propagation and DB-readiness completed")
    return "ready"


if __name__ == "__main__":
    try:
        reconcile(Kube())
    except Exception as error:
        # No traceback or exception body: failed Job is routed by a Final alert.
        print("FAIL: credential propagation stopped (" + type(error).__name__ + ")", file=sys.stderr)
        sys.exit(1)
