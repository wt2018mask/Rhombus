"""Append-only Git commits with non-force reference updates as a CAS ledger."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.error
import urllib.request


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


class ControlError(RuntimeError):
    pass


class GitHub:
    """Fixed-origin, bounded JSON API. Never surface provider exception bodies."""

    def __init__(self, repository, token):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
            raise ControlError("GITHUB_AUTHENTICATION_NOT_CONFIGURED")
        self.repository = repository
        self.token = token

    def call(self, method, path, body=None, *, missing=False, conflict=False):
        if not path.startswith("/") or ".." in path or "?" in path:
            raise ControlError("INVALID_API_PATH")
        request = urllib.request.Request(
            "https://api.github.com/repos/" + self.repository + path,
            data=canonical(body) if body is not None else None,
            method=method,
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                     "X-GitHub-Api-Version": "2022-11-28"},
        )
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=45) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ControlError("GITHUB_RESPONSE_BUDGET")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            if conflict and error.code in (409, 422):
                return None
            raise ControlError("GITHUB_HTTP_" + str(error.code)) from None
        except (OSError, ValueError):
            raise ControlError("GITHUB_OUTCOME_UNCERTAIN") from None


class GitLedger:
    """One global admission ledger, bounding both concurrency and lifetime count.

    A candidate commit has exactly the observed tip as parent. Concurrent
    writers create siblings, so a non-force fast-forward update admits only
    one. A lost response NEVER gives the caller permission to submit.
    Protect this branch against deletion, force pushes and other writers.
    """

    branch = "rhombus-automation-ledger-v1"

    def __init__(self, github):
        self.github = github

    def read(self):
        reference = self.github.call("GET", "/git/ref/heads/" + self.branch, missing=True)
        if reference is None:
            return None, None
        revision = reference["object"]["sha"]
        commit = self.github.call("GET", "/git/commits/" + revision)
        tree = self.github.call("GET", "/git/trees/" + commit["tree"]["sha"])
        if tree.get("truncated") or len(tree["tree"]) != 1:
            raise ControlError("LEDGER_CORRUPT")
        entry = tree["tree"][0]
        if (entry["path"], entry["mode"], entry["type"]) != ("state.json", "100644", "blob"):
            raise ControlError("LEDGER_CORRUPT")
        blob = self.github.call("GET", "/git/blobs/" + entry["sha"])
        raw = base64.b64decode(blob["content"])
        if len(raw) > 1024 * 1024:
            raise ControlError("LEDGER_BUDGET")
        return revision, json.loads(raw)

    def compare_and_swap(self, previous, state):
        tree = self.github.call("POST", "/git/trees", {"tree": [
            {"path": "state.json", "mode": "100644", "type": "blob",
             "content": canonical(state).decode()}]})
        commit = self.github.call("POST", "/git/commits", {
            "message": "Rhombus automation state " + digest(state),
            "tree": tree["sha"], "parents": [previous] if previous else []})
        if previous is None:
            result = self.github.call("POST", "/git/refs", {
                "ref": "refs/heads/" + self.branch, "sha": commit["sha"]}, conflict=True)
        else:
            result = self.github.call("PATCH", "/git/refs/heads/" + self.branch, {
                "sha": commit["sha"], "force": False}, conflict=True)
        if result is None:
            return None
        if result.get("object", {}).get("sha") != commit["sha"]:
            raise ControlError("LEDGER_WRITE_UNCERTAIN")
        return commit["sha"]
