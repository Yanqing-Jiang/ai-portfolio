from starlette.requests import Request
import rate_limiter as limiter


def request(headers, path='/api/fortune/create'):
    return Request({'type': 'http', 'path': path, 'headers': [(k.encode(), v.encode()) for k, v in headers.items()], 'client': ('127.0.0.1', 8000), 'scheme': 'https', 'server': ('test', 443), 'query_string': b''})


def test_own_worker_preserves_distinct_visitors(monkeypatch):
    monkeypatch.setattr(limiter, 'TRUST_FORWARDED_IP', True)
    base = {'cf-connecting-ip': '2a06:98c0:3600::103', 'cf-worker': 'ai-portfolio-6jm.pages.dev'}
    assert limiter._guest_ip(request({**base, 'x-forwarded-for': '203.0.113.10'})) == '203.0.113.10'
    assert limiter._guest_ip(request({**base, 'x-forwarded-for': '203.0.113.11, 198.51.100.1'})) == '203.0.113.11'


def test_untrusted_workers_cannot_choose_guest_identity(monkeypatch):
    monkeypatch.setattr(limiter, 'TRUST_FORWARDED_IP', True)
    for worker in ('evil.pages.dev', '', 'yanqing.app.attacker.example'):
        assert limiter._guest_ip(request({'cf-connecting-ip': '2a06:98c0:3600::103', 'cf-worker': worker, 'x-forwarded-for': '203.0.113.10'})) == '2a06:98c0:3600::103'
    assert limiter._guest_ip(request({'cf-connecting-ip': '203.0.113.12', 'cf-worker': 'yanqing.app', 'x-forwarded-for': '203.0.113.10'})) == '203.0.113.12'


def test_invalid_forwarded_ip_and_untrusted_transport_fail_closed(monkeypatch):
    headers = {'cf-connecting-ip': '2a06:98c0:3600::103', 'cf-worker': 'ai-portfolio-6jm.pages.dev', 'x-forwarded-for': 'invalid'}
    monkeypatch.setattr(limiter, 'TRUST_FORWARDED_IP', True)
    assert limiter._guest_ip(request(headers)) == '2a06:98c0:3600::103'
    monkeypatch.setattr(limiter, 'TRUST_FORWARDED_IP', False)
    assert limiter._guest_ip(request(headers)) == '127.0.0.1'


def test_read_allowance_does_not_expand_generation_allowance():
    assert limiter.resolve_limits(limiter.RateLimitScope.FORTUNE_REPLAY, False) == 120
    assert limiter.resolve_limits(limiter.RateLimitScope.FORTUNE_CREATE, False) == 3
    assert limiter.resolve_limits(limiter.RateLimitScope.FORTUNE_ASK, False) == 5
