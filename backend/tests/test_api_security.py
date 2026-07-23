import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi.routing import APIRoute


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from services.login_security import login_rate_limiter
from services.session_auth import COOKIE_NAME, create_session_token


class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        login_rate_limiter.reset()
        self.client = TestClient(main.app)

    def tearDown(self):
        login_rate_limiter.reset()

    def test_private_router_rejects_anonymous_requests(self):
        response = self.client.get("/clientes/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Authentication required")

    def test_every_service_router_has_server_side_session_dependency(self):
        public_paths = {"/", "/login"}
        unprotected = []
        for route in main.app.routes:
            if not isinstance(route, APIRoute) or route.path in public_paths:
                continue
            calls = {dependency.call for dependency in route.dependant.dependencies}
            if route.path.startswith((
                "/cobranza",
                "/renovaciones",
                "/cartera",
                "/clientes",
                "/ingestion",
                "/drive-sources",
                "/renewal-ingestion",
                "/client-email-directory",
                "/whatsapp",
                "/pendientes",
                "/mail-configuration",
                "/recluta",
            )) and main.current_username not in calls:
                unprotected.append(route.path)
        self.assertEqual(unprotected, [])

    def test_private_router_accepts_valid_session(self):
        with patch.dict(os.environ, {"AUTH_SESSION_SECRET": "test-session-secret"}), patch(
            "services.mail_configuration.configuration_for",
            return_value=None,
        ):
            token = create_session_token("person@example.com")
            response = self.client.get(
                "/mail-configuration",
                cookies={COOKIE_NAME: token},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"configured": False})

    def test_https_proxy_sets_secure_httponly_cookie(self):
        with patch.dict(os.environ, {"AUTH_SESSION_SECRET": "test-session-secret"}), patch.object(
            main.auth,
            "verify_credentials",
            return_value=True,
        ):
            response = self.client.post(
                "/login",
                headers={"x-forwarded-proto": "https", "cf-connecting-ip": "203.0.113.10"},
                json={"username": "Person@Example.com", "password": "correct"},
            )
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=lax", cookie)

    def test_production_forces_secure_cookie_without_proxy_header(self):
        with patch.dict(
            os.environ,
            {
                "AUTH_SESSION_SECRET": "test-session-secret",
                "TAIICO_ENV": "production",
                "AUTH_COOKIE_SECURE": "",
            },
        ), patch.object(main.auth, "verify_credentials", return_value=True):
            response = self.client.post(
                "/login",
                json={"username": "person@example.com", "password": "correct"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Secure", response.headers["set-cookie"])

    def test_repeated_failed_logins_are_rate_limited(self):
        with patch.dict(
            os.environ,
            {"AUTH_LOGIN_MAX_ATTEMPTS": "2", "AUTH_LOGIN_WINDOW_SECONDS": "60"},
        ), patch.object(main.auth, "verify_credentials", return_value=False):
            for _ in range(2):
                response = self.client.post(
                    "/login",
                    headers={"cf-connecting-ip": "203.0.113.11"},
                    json={"username": "person@example.com", "password": "wrong"},
                )
                self.assertEqual(response.status_code, 401)
            response = self.client.post(
                "/login",
                headers={"cf-connecting-ip": "203.0.113.11"},
                json={"username": "person@example.com", "password": "wrong"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_session_refresh_renews_cookie_for_one_hour(self):
        with patch.dict(
            os.environ,
            {
                "AUTH_SESSION_SECRET": "test-session-secret",
                "AUTH_SESSION_IDLE_SECONDS": "3600",
            },
        ):
            token = create_session_token("person@example.com")
            response = self.client.post(
                "/session/refresh",
                cookies={COOKIE_NAME: token},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Max-Age=3600", response.headers["set-cookie"])

    def test_logout_requires_a_session_and_clears_cookie(self):
        self.assertEqual(self.client.post("/logout").status_code, 401)
        with patch.dict(os.environ, {"AUTH_SESSION_SECRET": "test-session-secret"}):
            token = create_session_token("person@example.com")
            response = self.client.post("/logout", cookies={COOKIE_NAME: token})
        self.assertEqual(response.status_code, 200)
        self.assertIn("taiico_session=\"\"", response.headers["set-cookie"])

    def test_unlisted_cross_origin_request_gets_no_cors_permission(self):
        response = self.client.options(
            "/clientes/",
            headers={
                "origin": "https://malicious.example",
                "access-control-request-method": "GET",
            },
        )
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
