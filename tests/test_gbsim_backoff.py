"""Tests for the 429 backoff in the vendored gbsim pump (offline, fake HTTP)."""

import time

from gbsim.web import _Sender


class _FakeResp:
    def __init__(self, status):
        self.status = status

    def read(self):
        return b""


class _FakeConn:
    """Returns queued statuses in order; 204 when the queue is empty."""

    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.requests = []

    def request(self, *args, **kwargs):
        self.requests.append(args)

    def getresponse(self):
        status = self.statuses.pop(0) if self.statuses else 204
        return _FakeResp(status)

    def close(self):
        pass


def test_429_sets_backoff_then_success_recovers():
    s = _Sender("host", False, "/frame", 1.0)
    fake = _FakeConn([429, 204])
    s._connect = lambda: fake

    s.put(b"frame-a")
    deadline = time.time() + 3
    while time.time() < deadline and s._rate_limited == 0:
        time.sleep(0.05)
    assert s._rate_limited == 1
    assert s._backoff_until is not None          # pump is backing off
    delay = s._backoff_until - time.monotonic()
    assert 0.5 < delay <= 1.6                    # first backoff ~1.5s

    time.sleep(delay + 0.2)                      # let backoff expire
    s.put(b"frame-b")
    deadline = time.time() + 5
    while time.time() < deadline and (s._busy or s._slot is not None):
        time.sleep(0.05)
    assert s._rate_limited == 0                  # success resets the limiter
    assert len(fake.requests) == 2
    s.close(2)


def test_backoff_grows_then_caps():
    s = _Sender("host", False, "/frame", 1.0)
    fake = _FakeConn([429, 429, 429])
    s._connect = lambda: fake

    seen = []
    for expected in (1, 2, 3):
        s.put(b"x")                              # the pump only sends on traffic
        deadline = time.time() + 5
        while time.time() < deadline and s._rate_limited < expected:
            time.sleep(0.05)
        assert s._rate_limited == expected
        assert s._backoff_until is not None
        seen.append(s._backoff_until - time.monotonic())
        time.sleep(seen[-1] + 0.2)               # let the backoff expire

    assert seen[0] < seen[1] < seen[2] <= 10.0   # exponential, capped at 10s
    s.close(2)
