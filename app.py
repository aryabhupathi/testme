from __future__ import annotations
import json
import os
import sqlite3
import time
from http.cookiejar import CookieJar
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from flask import (
    Flask,
    Response,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "qa_test_manager.db"))
MAX_HTML_BYTES = 1_000_000
MAX_LINK_CHECKS = 20
REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_AUTOMATION_TIMEOUT_MS = 10_000
DEMO_SERVICES: list[dict[str, str]] = [
    {
        "name": "Functional QA",
        "slug": "functional-qa",
        "summary": "Login, signup, forms, navigation, and business flow validation.",
    },
    {
        "name": "Automation QA",
        "slug": "automation-qa",
        "summary": "Playwright-ready checks for real browser journeys and regressions.",
    },
    {
        "name": "Security Review",
        "slug": "security-review",
        "summary": "Authentication, authorization, injection, and data exposure checks.",
    },
    {
        "name": "Database Testing",
        "slug": "database-testing",
        "summary": "SQLite CRUD, data integrity, registration, and contact persistence checks.",
    },
]
TESTING_TYPES: list[dict[str, Any]] = [
    {
        "name": "Functional Testing",
        "focus": "Does the feature work according to business requirements?",
        "description": "Checks user-facing features such as login, cart, payment, and search behavior.",
        "examples": ["Login works correctly", "Add to cart works", "Payment succeeds"],
        "tools": [],
    },
    {
        "name": "Unit Testing",
        "focus": "Does one function, method, or component work in isolation?",
        "description": "Validates small units of code, usually by developers, before larger flows are tested.",
        "examples": ["A Python add(a, b) function returns the expected sum"],
        "tools": ["PyTest", "JUnit", "NUnit"],
    },
    {
        "name": "Integration Testing",
        "focus": "Do connected modules communicate correctly?",
        "description": "Checks behavior across boundaries such as UI to API to database or third-party services.",
        "examples": ["UI -> API -> Database flow", "Payment gateway integration"],
        "tools": [],
    },
    {
        "name": "System Testing",
        "focus": "Does the complete application work as one system?",
        "description": "Tests the fully assembled application across UI, backend, APIs, and database.",
        "examples": ["Full e-commerce website validation"],
        "tools": [],
    },
    {
        "name": "End-to-End (E2E) Testing",
        "focus": "Can a real user complete the workflow from start to finish?",
        "description": "Validates realistic journeys such as registration, login, ordering, and confirmation.",
        "examples": ["Register -> Login -> Place order -> Receive confirmation email"],
        "tools": ["Selenium", "Playwright", "Cypress"],
    },
    {
        "name": "Regression Testing",
        "focus": "Did new changes break existing features?",
        "description": "Re-runs important coverage after code changes, often through automated suites.",
        "examples": [
            "After adding a payment method, verify login, cart, and search still work"
        ],
        "tools": [],
    },
    {
        "name": "Smoke Testing",
        "focus": "Is the build stable enough for deeper testing?",
        "description": "Performs quick high-level checks before committing more testing time.",
        "examples": ["App launches", "Login works", "Main pages open"],
        "tools": [],
    },
    {
        "name": "Sanity Testing",
        "focus": "Does a specific bug fix or narrow change work properly?",
        "description": "Targets a small area after a focused change, such as a checkout fix.",
        "examples": ["Verify only checkout-related flows after a checkout defect fix"],
        "tools": [],
    },
    {
        "name": "Performance Testing",
        "focus": "Is the system fast, stable, and responsive under expected or extreme traffic?",
        "description": "Measures behavior through load, stress, spike, and endurance scenarios.",
        "examples": [
            "Load testing",
            "Stress testing",
            "Spike testing",
            "Endurance testing",
        ],
        "tools": ["JMeter", "LoadRunner", "k6"],
    },
    {
        "name": "Security Testing",
        "focus": "Are there vulnerabilities or authorization risks?",
        "description": "Looks for issues such as injection, weak authentication, data leakage, and access flaws.",
        "examples": [
            "SQL injection checks",
            "Authentication checks",
            "Authorization checks",
            "Data leak checks",
        ],
        "tools": ["OWASP ZAP", "Burp Suite"],
    },
    {
        "name": "Usability Testing",
        "focus": "Is the application clear and easy to use?",
        "description": "Evaluates navigation clarity, button visibility, accessibility, and user experience quality.",
        "examples": ["Navigation clarity", "Button visibility", "Ease of use"],
        "tools": [],
    },
    {
        "name": "Compatibility Testing",
        "focus": "Does the application work across target environments?",
        "description": "Checks browsers, devices, operating systems, versions, and screen sizes.",
        "examples": ["Chrome vs Firefox vs Safari", "Mobile vs desktop layouts"],
        "tools": [],
    },
    {
        "name": "Database Testing",
        "focus": "Are data integrity, CRUD operations, stored procedures, and consistency correct?",
        "description": "Validates backend database behavior and requires strong SQL awareness.",
        "examples": [
            "After registration, user data is stored correctly in the database"
        ],
        "tools": ["SQL"],
    },
]
STATUSES = ["Not Started", "In Progress", "Passed", "Failed", "Blocked"]
PRIORITIES = ["Critical", "High", "Medium", "Low"]
AUTOMATION_STATES = ["Manual", "Automated", "Planned"]
SEED_CASES: list[dict[str, str]] = [
    {
        "title": "Validate successful login with valid credentials",
        "testing_type": "Functional Testing",
        "requirement": "Users with active accounts can sign in and land on the dashboard.",
        "steps": "1. Open login page\n2. Enter valid email and password\n3. Submit login form",
        "expected_result": "User is authenticated and dashboard is displayed.",
        "actual_result": "Dashboard opens after authentication.",
        "priority": "High",
        "status": "Passed",
        "owner": "QA Team",
        "environment": "Chrome / Windows",
        "automation": "Automated",
        "tags": "login, business-rule",
    },
    {
        "title": "Verify add function returns correct sum",
        "testing_type": "Unit Testing",
        "requirement": "The add(a, b) helper returns the numeric sum of two inputs.",
        "steps": "1. Call add(2, 3)\n2. Call add(-1, 1)\n3. Assert returned values",
        "expected_result": "The function returns 5 and 0 respectively.",
        "actual_result": "Unit assertions pass.",
        "priority": "Medium",
        "status": "Passed",
        "owner": "Developer",
        "environment": "PyTest",
        "automation": "Automated",
        "tags": "unit, python",
    },
    {
        "title": "Confirm product search writes recent query to database",
        "testing_type": "Integration Testing",
        "requirement": "Search UI, API, and database history table stay synchronized.",
        "steps": "1. Search for laptop\n2. Inspect API response\n3. Verify search_history database row",
        "expected_result": "The UI receives matching results and the database stores the search term.",
        "actual_result": "Pending API environment refresh.",
        "priority": "High",
        "status": "In Progress",
        "owner": "Integration QA",
        "environment": "Staging",
        "automation": "Planned",
        "tags": "ui, api, database",
    },
    {
        "title": "Run full checkout system validation",
        "testing_type": "System Testing",
        "requirement": "UI, backend, APIs, and database complete checkout together.",
        "steps": "1. Login\n2. Add product to cart\n3. Checkout\n4. Confirm order in admin and database",
        "expected_result": "Order is created, paid, visible to admin, and persisted in the database.",
        "actual_result": "Payment callback is intermittent.",
        "priority": "Critical",
        "status": "Failed",
        "owner": "System QA",
        "environment": "Staging",
        "automation": "Manual",
        "tags": "checkout, payment",
    },
    {
        "title": "Complete new customer purchase journey",
        "testing_type": "End-to-End (E2E) Testing",
        "requirement": "A new customer can register, sign in, place an order, and receive confirmation.",
        "steps": "1. Register account\n2. Login\n3. Place order\n4. Check confirmation email",
        "expected_result": "The complete customer journey succeeds without manual intervention.",
        "actual_result": "Email assertion is not automated yet.",
        "priority": "Critical",
        "status": "In Progress",
        "owner": "Automation QA",
        "environment": "Playwright / Staging",
        "automation": "Planned",
        "tags": "e2e, customer-journey",
    },
    {
        "title": "Run cart, login, and search regression pack",
        "testing_type": "Regression Testing",
        "requirement": "Existing critical features remain stable after payment method change.",
        "steps": "1. Execute login regression\n2. Execute cart regression\n3. Execute search regression",
        "expected_result": "All existing smoke and critical regression scenarios pass.",
        "actual_result": "Login and cart pass. Search suite queued.",
        "priority": "High",
        "status": "In Progress",
        "owner": "Regression QA",
        "environment": "CI",
        "automation": "Automated",
        "tags": "regression, release",
    },
    {
        "title": "Smoke check build 2.4.1",
        "testing_type": "Smoke Testing",
        "requirement": "The build is stable enough for detailed testing.",
        "steps": "1. Launch app\n2. Login\n3. Open dashboard, cart, and profile pages",
        "expected_result": "Application launches and core pages respond successfully.",
        "actual_result": "All smoke checks passed.",
        "priority": "Critical",
        "status": "Passed",
        "owner": "Release QA",
        "environment": "Build 2.4.1",
        "automation": "Automated",
        "tags": "smoke, release-gate",
    },
    {
        "title": "Verify checkout bug fix for invalid coupon handling",
        "testing_type": "Sanity Testing",
        "requirement": "Checkout remains usable when invalid coupon codes are entered.",
        "steps": "1. Add item to cart\n2. Enter invalid coupon\n3. Continue checkout",
        "expected_result": "A clear coupon error is shown and checkout remains available.",
        "actual_result": "Waiting for fixed deployment.",
        "priority": "High",
        "status": "Blocked",
        "owner": "Feature QA",
        "environment": "QA",
        "automation": "Manual",
        "tags": "checkout, bug-fix",
    },
    {
        "title": "Measure checkout API under 500 concurrent users",
        "testing_type": "Performance Testing",
        "requirement": "Checkout API responds within SLA during expected peak traffic.",
        "steps": "1. Run k6 load profile\n2. Monitor p95 response time\n3. Review error rate",
        "expected_result": "p95 response time remains under 800 ms and error rate under 1 percent.",
        "actual_result": "Not started.",
        "priority": "High",
        "status": "Not Started",
        "owner": "Performance QA",
        "environment": "k6 / Perf",
        "automation": "Automated",
        "tags": "load, checkout, sla",
    },
    {
        "title": "Check login form for SQL injection and auth bypass",
        "testing_type": "Security Testing",
        "requirement": "Authentication endpoints reject injection payloads and bypass attempts.",
        "steps": "1. Send SQL injection payloads\n2. Attempt auth bypass\n3. Review logs for leaks",
        "expected_result": "Malicious input is rejected, no sensitive data leaks, and logs remain clean.",
        "actual_result": "No injection found; authorization review pending.",
        "priority": "Critical",
        "status": "In Progress",
        "owner": "Security QA",
        "environment": "OWASP ZAP",
        "automation": "Planned",
        "tags": "security, auth, injection",
    },
    {
        "title": "Evaluate navigation clarity on mobile checkout",
        "testing_type": "Usability Testing",
        "requirement": "Mobile checkout navigation is clear for first-time users.",
        "steps": "1. Ask participant to find cart\n2. Observe checkout progression\n3. Record friction points",
        "expected_result": "Users can complete checkout without confusion or hidden controls.",
        "actual_result": "Participants asked for clearer shipping step labels.",
        "priority": "Medium",
        "status": "Failed",
        "owner": "UX QA",
        "environment": "Mobile usability lab",
        "automation": "Manual",
        "tags": "ux, mobile",
    },
    {
        "title": "Validate order history across target browsers",
        "testing_type": "Compatibility Testing",
        "requirement": "Order history works on supported desktop and mobile browsers.",
        "steps": "1. Open order history in Chrome\n2. Repeat in Firefox\n3. Repeat in Safari responsive viewport",
        "expected_result": "Layout, filters, and order details work consistently.",
        "actual_result": "Safari date picker styling needs review.",
        "priority": "Medium",
        "status": "In Progress",
        "owner": "Compatibility QA",
        "environment": "Browser matrix",
        "automation": "Manual",
        "tags": "browser, responsive",
    },
    {
        "title": "Verify registration data is persisted correctly",
        "testing_type": "Database Testing",
        "requirement": "Registration creates consistent user, profile, and audit records.",
        "steps": "1. Register a new user\n2. Query users table\n3. Query profile table\n4. Verify audit row",
        "expected_result": "All related records are created with correct foreign keys and timestamps.",
        "actual_result": "Not started.",
        "priority": "High",
        "status": "Not Started",
        "owner": "Database QA",
        "environment": "SQLite / QA DB",
        "automation": "Manual",
        "tags": "database, crud, integrity",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = str(DATABASE_PATH)
    app.secret_key = os.environ.get("SECRET_KEY", "qa-test-manager-dev-secret")

    @app.teardown_appcontext
    def close_db(error: Exception | None = None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        init_db()

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/home")
    def demo_home() -> str:
        return render_template(
            "home.html",
            active_page="home",
            user=get_current_demo_user(),
            stats=get_demo_site_stats(),
        )

    @app.route("/login", methods=["GET", "POST"])
    def demo_login() -> str | Response:
        error = ""
        email = ""
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = (
                get_db()
                .execute("SELECT * FROM demo_users WHERE email = ?", (email,))
                .fetchone()
            )
            if user and check_password_hash(user["password_hash"], password):
                session["demo_user_id"] = user["id"]
                log_demo_login_attempt(email, "success")
                return redirect(url_for("demo_dashboard"))
            log_demo_login_attempt(email, "failed")
            error = "Invalid email or password."
        return render_template(
            "login.html",
            active_page="login",
            error=error,
            email=email,
            user=get_current_demo_user(),
        )

    @app.route("/signin", methods=["GET", "POST"])
    def demo_signin() -> str | Response:
        error = ""
        form = {"name": "", "email": ""}
        if request.method == "POST":
            form = {
                "name": request.form.get("name", "").strip(),
                "email": request.form.get("email", "").strip().lower(),
            }
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not form["name"] or not form["email"] or not password:
                error = "Name, email, and password are required."
            elif len(password) < 8:
                error = "Password must be at least 8 characters."
            elif password != confirm_password:
                error = "Passwords do not match."
            else:
                db = get_db()
                existing = db.execute(
                    "SELECT id FROM demo_users WHERE email = ?", (form["email"],)
                ).fetchone()
                if existing:
                    error = "An account already exists for this email."
                else:
                    now = utc_now()
                    cursor = db.execute(
                        """
                        INSERT INTO demo_users (name, email, password_hash, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            form["name"],
                            form["email"],
                            generate_password_hash(password),
                            now,
                        ),
                    )
                    db.commit()
                    session["demo_user_id"] = cursor.lastrowid
                    return redirect(url_for("demo_dashboard"))
        return render_template(
            "signin.html",
            active_page="signin",
            error=error,
            form=form,
            user=get_current_demo_user(),
        )

    @app.get("/dashboard")
    def demo_dashboard() -> str | Response:
        user = get_current_demo_user()
        if user is None:
            return redirect(url_for("demo_login"))
        return render_template(
            "dashboard.html",
            active_page="dashboard",
            user=user,
            stats=get_demo_site_stats(),
        )

    @app.get("/logout")
    def demo_logout() -> Response:
        session.pop("demo_user_id", None)
        return redirect(url_for("demo_home"))

    @app.get("/about")
    def demo_about() -> str:
        return render_template(
            "about.html", active_page="about", user=get_current_demo_user()
        )

    @app.get("/services")
    def demo_services() -> str:
        return render_template(
            "services.html",
            active_page="services",
            user=get_current_demo_user(),
            services=DEMO_SERVICES,
        )

    @app.route("/contact", methods=["GET", "POST"])
    def demo_contact() -> str:
        error = ""
        success = ""
        form = {"name": "", "email": "", "message": ""}
        if request.method == "POST":
            form = {
                "name": request.form.get("name", "").strip(),
                "email": request.form.get("email", "").strip().lower(),
                "message": request.form.get("message", "").strip(),
            }
            if not form["name"] or not form["email"] or not form["message"]:
                error = "Name, email, and message are required."
            else:
                get_db().execute(
                    """
                    INSERT INTO demo_contact_messages (name, email, message, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (form["name"], form["email"], form["message"], utc_now()),
                )
                get_db().commit()
                success = "Message saved successfully."
                form = {"name": "", "email": "", "message": ""}
        return render_template(
            "contact.html",
            active_page="contact",
            error=error,
            success=success,
            form=form,
            user=get_current_demo_user(),
        )

    @app.get("/api/testing-types")
    def get_testing_types() -> Response:
        return jsonify(
            {
                "testing_types": TESTING_TYPES,
                "statuses": STATUSES,
                "priorities": PRIORITIES,
                "automation_states": AUTOMATION_STATES,
            }
        )

    @app.get("/api/test-cases")
    def list_test_cases() -> Response:
        rows = query_cases(request.args)
        return jsonify({"cases": [dict(row) for row in rows]})

    @app.post("/api/test-cases")
    def create_test_case() -> tuple[Response, int]:
        payload = request.get_json(silent=True) or {}
        cleaned, errors = validate_case_payload(payload)
        if errors:
            return jsonify({"errors": errors}), 400
        now = utc_now()
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO test_cases (
                title, testing_type, requirement, steps, expected_result, actual_result,
                priority, status, owner, environment, automation, tags, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cleaned["title"],
                cleaned["testing_type"],
                cleaned["requirement"],
                cleaned["steps"],
                cleaned["expected_result"],
                cleaned["actual_result"],
                cleaned["priority"],
                cleaned["status"],
                cleaned["owner"],
                cleaned["environment"],
                cleaned["automation"],
                cleaned["tags"],
                now,
                now,
            ),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM test_cases WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return jsonify({"case": dict(row)}), 201

    @app.get("/api/test-cases/<int:case_id>")
    def get_test_case(case_id: int) -> Response | tuple[Response, int]:
        row = get_case_or_none(case_id)
        if row is None:
            return jsonify({"error": "Test case not found"}), 404
        return jsonify({"case": dict(row)})

    @app.put("/api/test-cases/<int:case_id>")
    def update_test_case(case_id: int) -> Response | tuple[Response, int]:
        if get_case_or_none(case_id) is None:
            return jsonify({"error": "Test case not found"}), 404
        payload = request.get_json(silent=True) or {}
        cleaned, errors = validate_case_payload(payload)
        if errors:
            return jsonify({"errors": errors}), 400
        now = utc_now()
        db = get_db()
        db.execute(
            """
            UPDATE test_cases
            SET title = ?, testing_type = ?, requirement = ?, steps = ?, expected_result = ?,
                actual_result = ?, priority = ?, status = ?, owner = ?, environment = ?,
                automation = ?, tags = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                cleaned["title"],
                cleaned["testing_type"],
                cleaned["requirement"],
                cleaned["steps"],
                cleaned["expected_result"],
                cleaned["actual_result"],
                cleaned["priority"],
                cleaned["status"],
                cleaned["owner"],
                cleaned["environment"],
                cleaned["automation"],
                cleaned["tags"],
                now,
                case_id,
            ),
        )
        db.commit()
        row = get_case_or_none(case_id)
        return jsonify({"case": dict(row)})

    @app.delete("/api/test-cases/<int:case_id>")
    def delete_test_case(case_id: int) -> Response | tuple[Response, int]:
        if get_case_or_none(case_id) is None:
            return jsonify({"error": "Test case not found"}), 404
        db = get_db()
        db.execute("DELETE FROM test_cases WHERE id = ?", (case_id,))
        db.commit()
        return jsonify({"deleted": case_id})

    @app.get("/api/analytics")
    def analytics() -> Response:
        cases = [dict(row) for row in query_cases(request.args)]
        return jsonify({"analytics": build_analytics(cases)})

    @app.post("/api/live-test")
    def run_live_test() -> tuple[Response, int] | Response:
        payload = request.get_json(silent=True) or {}
        base_url = normalize_base_url(str(payload.get("base_url", "")).strip())
        pages = parse_line_values(payload.get("pages", ""))
        expected_keywords = parse_line_values(payload.get("expected_keywords", ""))
        check_links = bool(payload.get("check_links", True))
        from urllib.parse import urlparse

current_host = request.host

target_host = urlparse(base_url).netloc

if current_host == target_host:
    return jsonify({
        "error": "Self-testing the same Railway app is blocked to prevent worker deadlocks."
    }), 400
        if not base_url:
            return jsonify({"error": "Base URL is required"}), 400
        parsed_base = urlparse(base_url)
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            return jsonify({"error": "Base URL must be a valid http or https URL"}), 400
        if not pages:
            pages = ["/"]
        run_result = execute_live_test(base_url, pages, expected_keywords, check_links)
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO live_test_runs (base_url, pages, summary_json, results_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                base_url,
                "\n".join(pages),
                json.dumps(run_result["summary"]),
                json.dumps(run_result),
                utc_now(),
            ),
        )
        db.commit()
        run_result["id"] = cursor.lastrowid
        return jsonify({"run": run_result})

    @app.get("/api/live-runs")
    def list_live_runs() -> Response:
        rows = get_db().execute("""
            SELECT id, base_url, pages, summary_json, created_at
            FROM live_test_runs
            ORDER BY id DESC
            LIMIT 12
            """).fetchall()
        runs = []
        for row in rows:
            item = dict(row)
            item["summary"] = json.loads(item.pop("summary_json"))
            runs.append(item)
        return jsonify({"runs": runs})

    @app.get("/api/live-runs/<int:run_id>")
    def get_live_run(run_id: int) -> Response | tuple[Response, int]:
        row = (
            get_db()
            .execute("SELECT results_json FROM live_test_runs WHERE id = ?", (run_id,))
            .fetchone()
        )
        if row is None:
            return jsonify({"error": "Live test run not found"}), 404
        return jsonify({"run": json.loads(row["results_json"])})

    @app.delete("/api/live-runs/<int:run_id>")
    def delete_live_run(run_id: int) -> Response | tuple[Response, int]:
        db = get_db()
        row = db.execute(
            "SELECT id FROM live_test_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Live test run not found"}), 404
        db.execute("DELETE FROM live_test_runs WHERE id = ?", (run_id,))
        db.commit()
        return jsonify({"deleted": run_id})

    @app.post("/api/automation-run")
    def run_automation() -> tuple[Response, int] | Response:
        payload = request.get_json(silent=True) or {}
        scenario_name = str(payload.get("scenario_name", "Untitled automation")).strip()
        base_url = normalize_base_url(str(payload.get("base_url", "")).strip())
        steps_text = str(payload.get("steps", "")).strip()
        timeout_ms = parse_timeout(
            payload.get("timeout_ms", DEFAULT_AUTOMATION_TIMEOUT_MS)
        )
        headless = bool(payload.get("headless", True))
        if not scenario_name:
            scenario_name = "Untitled automation"
        if not base_url:
            return jsonify({"error": "Base URL is required"}), 400
        parsed_base = urlparse(base_url)
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            return jsonify({"error": "Base URL must be a valid http or https URL"}), 400
        if not steps_text:
            return jsonify({"error": "Automation steps are required"}), 400
        run_result = execute_browser_automation(
            scenario_name=scenario_name,
            base_url=base_url,
            steps_text=steps_text,
            timeout_ms=timeout_ms,
            headless=headless,
        )
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO automation_runs (
                scenario_name, base_url, steps, summary_json, results_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_name,
                base_url,
                steps_text,
                json.dumps(run_result["summary"]),
                json.dumps(run_result),
                utc_now(),
            ),
        )
        db.commit()
        run_result["id"] = cursor.lastrowid
        return jsonify({"run": run_result})

    @app.get("/api/automation-runs")
    def list_automation_runs() -> Response:
        rows = get_db().execute("""
            SELECT id, scenario_name, base_url, summary_json, created_at
            FROM automation_runs
            ORDER BY id DESC
            LIMIT 12
            """).fetchall()
        runs = []
        for row in rows:
            item = dict(row)
            item["summary"] = json.loads(item.pop("summary_json"))
            runs.append(item)
        return jsonify({"runs": runs})

    @app.get("/api/automation-runs/<int:run_id>")
    def get_automation_run(run_id: int) -> Response | tuple[Response, int]:
        row = (
            get_db()
            .execute("SELECT results_json FROM automation_runs WHERE id = ?", (run_id,))
            .fetchone()
        )
        if row is None:
            return jsonify({"error": "Automation run not found"}), 404
        return jsonify({"run": json.loads(row["results_json"])})

    @app.delete("/api/automation-runs/<int:run_id>")
    def delete_automation_run(run_id: int) -> Response | tuple[Response, int]:
        db = get_db()
        row = db.execute(
            "SELECT id FROM automation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "Automation run not found"}), 404
        db.execute("DELETE FROM automation_runs WHERE id = ?", (run_id,))
        db.commit()
        return jsonify({"deleted": run_id})

    @app.post("/api/api-test-runs")
    def run_api_tests() -> tuple[Response, int] | Response:
        payload = request.get_json(silent=True) or {}
        suite_name = (
            str(payload.get("suite_name", "API test suite")).strip() or "API test suite"
        )
        base_url = normalize_base_url(str(payload.get("base_url", "")).strip())
        engine = str(payload.get("engine", "playwright")).strip().lower()
        requests_text = str(payload.get("requests", "")).strip()
        timeout_ms = parse_timeout(
            payload.get("timeout_ms", DEFAULT_AUTOMATION_TIMEOUT_MS)
        )
        headers_text = str(payload.get("headers", "{}")).strip() or "{}"
        if not base_url:
            return jsonify({"error": "Base URL is required"}), 400
        parsed_base = urlparse(base_url)
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            return jsonify({"error": "Base URL must be a valid http or https URL"}), 400
        if engine not in {"http", "playwright", "selenium"}:
            return (
                jsonify({"error": "Engine must be http, playwright, or selenium"}),
                400,
            )
        if not requests_text:
            return jsonify({"error": "API request steps are required"}), 400
        try:
            suite_headers = json.loads(headers_text)
        except json.JSONDecodeError as error:
            return jsonify({"error": f"Headers must be valid JSON: {error}"}), 400
        if not isinstance(suite_headers, dict):
            return jsonify({"error": "Headers JSON must be an object"}), 400
        run_result = execute_api_test_suite(
            suite_name=suite_name,
            base_url=base_url,
            engine=engine,
            requests_text=requests_text,
            suite_headers={
                str(key): str(value) for key, value in suite_headers.items()
            },
            timeout_ms=timeout_ms,
        )
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO api_test_runs (
                suite_name, base_url, engine, requests_text, summary_json, results_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                suite_name,
                base_url,
                engine,
                requests_text,
                json.dumps(run_result["summary"]),
                json.dumps(run_result),
                utc_now(),
            ),
        )
        db.commit()
        run_result["id"] = cursor.lastrowid
        return jsonify({"run": run_result})

    @app.get("/api/api-test-runs")
    def list_api_test_runs() -> Response:
        rows = get_db().execute("""
            SELECT id, suite_name, base_url, engine, summary_json, created_at
            FROM api_test_runs
            ORDER BY id DESC
            LIMIT 12
            """).fetchall()
        runs = []
        for row in rows:
            item = dict(row)
            item["summary"] = json.loads(item.pop("summary_json"))
            runs.append(item)
        return jsonify({"runs": runs})

    @app.get("/api/api-test-runs/<int:run_id>")
    def get_api_test_run(run_id: int) -> Response | tuple[Response, int]:
        row = (
            get_db()
            .execute("SELECT results_json FROM api_test_runs WHERE id = ?", (run_id,))
            .fetchone()
        )
        if row is None:
            return jsonify({"error": "API test run not found"}), 404
        return jsonify({"run": json.loads(row["results_json"])})

    @app.delete("/api/api-test-runs/<int:run_id>")
    def delete_api_test_run(run_id: int) -> Response | tuple[Response, int]:
        db = get_db()
        row = db.execute(
            "SELECT id FROM api_test_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "API test run not found"}), 404
        db.execute("DELETE FROM api_test_runs WHERE id = ?", (run_id,))
        db.commit()
        return jsonify({"deleted": run_id})

    @app.get("/api/export")
    def export_cases() -> Response:
        rows = (
            get_db()
            .execute("SELECT * FROM test_cases ORDER BY updated_at DESC, id DESC")
            .fetchall()
        )
        payload = {
            "exported_at": utc_now(),
            "testing_types": TESTING_TYPES,
            "cases": [dict(row) for row in rows],
        }
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": "attachment; filename=test-cases-export.json"
            },
        )

    @app.get("/api/export-pdf")
    def export_pdf() -> Response:
        db = get_db()
        cases = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM test_cases ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        ]
        live_rows = db.execute("""
            SELECT id, base_url, summary_json, created_at
            FROM live_test_runs
            ORDER BY id DESC
            LIMIT 8
            """).fetchall()
        automation_rows = db.execute("""
            SELECT id, scenario_name, base_url, summary_json, created_at
            FROM automation_runs
            ORDER BY id DESC
            LIMIT 8
            """).fetchall()
        api_rows = db.execute("""
            SELECT id, suite_name, base_url, engine, summary_json, created_at
            FROM api_test_runs
            ORDER BY id DESC
            LIMIT 8
            """).fetchall()
        pdf_bytes = build_pdf_report(cases, live_rows, automation_rows, api_rows)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment; filename=qa-test-report.pdf"},
        )

    @app.post("/api/import")
    def import_cases() -> tuple[Response, int] | Response:
        payload = request.get_json(silent=True) or {}
        incoming_cases = payload.get("cases")
        replace_existing = bool(payload.get("replace_existing", False))
        if not isinstance(incoming_cases, list):
            return jsonify({"error": "Expected JSON body with a cases list"}), 400
        db = get_db()
        if replace_existing:
            db.execute("DELETE FROM test_cases")
        imported = 0
        skipped: list[dict[str, Any]] = []
        now = utc_now()
        for index, raw_case in enumerate(incoming_cases, start=1):
            cleaned, errors = validate_case_payload(raw_case)
            if errors:
                skipped.append({"row": index, "errors": errors})
                continue
            db.execute(
                """
                INSERT INTO test_cases (
                    title, testing_type, requirement, steps, expected_result, actual_result,
                    priority, status, owner, environment, automation, tags, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cleaned["title"],
                    cleaned["testing_type"],
                    cleaned["requirement"],
                    cleaned["steps"],
                    cleaned["expected_result"],
                    cleaned["actual_result"],
                    cleaned["priority"],
                    cleaned["status"],
                    cleaned["owner"],
                    cleaned["environment"],
                    cleaned["automation"],
                    cleaned["tags"],
                    raw_case.get("created_at", now),
                    now,
                ),
            )
            imported += 1
        db.commit()
        return jsonify({"imported": imported, "skipped": skipped})

    @app.post("/api/reset-demo")
    def reset_demo() -> Response:
        reset_seed_data()
        return jsonify({"message": "Demo data restored"})

    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(str(DATABASE_PATH))
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db() -> None:
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            testing_type TEXT NOT NULL,
            requirement TEXT NOT NULL,
            steps TEXT NOT NULL,
            expected_result TEXT NOT NULL,
            actual_result TEXT DEFAULT '',
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT DEFAULT '',
            environment TEXT DEFAULT '',
            automation TEXT NOT NULL,
            tags TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS live_test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_url TEXT NOT NULL,
            pages TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS automation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            steps TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suite_name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            engine TEXT NOT NULL,
            requests_text TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS demo_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS demo_contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS demo_login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
    seed_demo_site_data(db)
    existing = db.execute("SELECT COUNT(*) AS count FROM test_cases").fetchone()[
        "count"
    ]
    if existing == 0:
        insert_seed_cases(db)
    db.commit()


def insert_seed_cases(db: sqlite3.Connection) -> None:
    now = utc_now()
    for case in SEED_CASES:
        db.execute(
            """
            INSERT INTO test_cases (
                title, testing_type, requirement, steps, expected_result, actual_result,
                priority, status, owner, environment, automation, tags, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case["title"],
                case["testing_type"],
                case["requirement"],
                case["steps"],
                case["expected_result"],
                case["actual_result"],
                case["priority"],
                case["status"],
                case["owner"],
                case["environment"],
                case["automation"],
                case["tags"],
                now,
                now,
            ),
        )


def seed_demo_site_data(db: sqlite3.Connection) -> None:
    existing = db.execute(
        "SELECT id FROM demo_users WHERE email = ?", ("tester@example.com",)
    ).fetchone()
    if existing:
        return
    db.execute(
        """
        INSERT INTO demo_users (name, email, password_hash, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            "Demo Tester",
            "tester@example.com",
            generate_password_hash("Password123!"),
            utc_now(),
        ),
    )


def get_current_demo_user() -> dict[str, Any] | None:
    user_id = session.get("demo_user_id")
    if not user_id:
        return None
    row = (
        get_db()
        .execute(
            "SELECT id, name, email, created_at FROM demo_users WHERE id = ?",
            (user_id,),
        )
        .fetchone()
    )
    return dict(row) if row else None


def get_demo_site_stats() -> dict[str, int]:
    db = get_db()
    return {
        "users": db.execute("SELECT COUNT(*) AS count FROM demo_users").fetchone()[
            "count"
        ],
        "messages": db.execute(
            "SELECT COUNT(*) AS count FROM demo_contact_messages"
        ).fetchone()["count"],
        "login_attempts": db.execute(
            "SELECT COUNT(*) AS count FROM demo_login_attempts"
        ).fetchone()["count"],
        "services": len(DEMO_SERVICES),
    }


def log_demo_login_attempt(email: str, result: str) -> None:
    get_db().execute(
        """
        INSERT INTO demo_login_attempts (email, result, created_at)
        VALUES (?, ?, ?)
        """,
        (email or "blank", result, utc_now()),
    )
    get_db().commit()


def reset_seed_data() -> None:
    db = get_db()
    db.execute("DELETE FROM test_cases")
    insert_seed_cases(db)
    db.commit()


def validate_case_payload(payload: Any) -> tuple[dict[str, str], list[str]]:
    if not isinstance(payload, dict):
        return {}, ["Payload must be a JSON object"]

    def text(name: str, default: str = "") -> str:
        value = payload.get(name, default)
        if value is None:
            return ""
        return str(value).strip()

    cleaned = {
        "title": text("title"),
        "testing_type": text("testing_type"),
        "requirement": text("requirement"),
        "steps": text("steps"),
        "expected_result": text("expected_result"),
        "actual_result": text("actual_result"),
        "priority": text("priority", "Medium"),
        "status": text("status", "Not Started"),
        "owner": text("owner"),
        "environment": text("environment"),
        "automation": text("automation", "Manual"),
        "tags": text("tags"),
    }
    errors: list[str] = []
    required_fields = [
        "title",
        "testing_type",
        "requirement",
        "steps",
        "expected_result",
    ]
    for field in required_fields:
        if not cleaned[field]:
            errors.append(f"{field.replace('_', ' ').title()} is required")
    valid_type_names = {item["name"] for item in TESTING_TYPES}
    if cleaned["testing_type"] and cleaned["testing_type"] not in valid_type_names:
        errors.append("Testing type is not supported")
    if cleaned["priority"] not in PRIORITIES:
        errors.append("Priority is not supported")
    if cleaned["status"] not in STATUSES:
        errors.append("Status is not supported")
    if cleaned["automation"] not in AUTOMATION_STATES:
        errors.append("Automation value is not supported")
    return cleaned, errors


def get_case_or_none(case_id: int) -> sqlite3.Row | None:
    return (
        get_db().execute("SELECT * FROM test_cases WHERE id = ?", (case_id,)).fetchone()
    )


def query_cases(args: dict[str, Any]) -> list[sqlite3.Row]:
    clauses: list[str] = []
    values: list[str] = []
    search = str(args.get("search", "")).strip()
    if search:
        like = f"%{search}%"
        clauses.append("""
            (
                title LIKE ? OR requirement LIKE ? OR steps LIKE ? OR expected_result LIKE ?
                OR actual_result LIKE ? OR owner LIKE ? OR environment LIKE ? OR tags LIKE ?
            )
            """)
        values.extend([like] * 8)
    for query_key, column in (
        ("testing_type", "testing_type"),
        ("status", "status"),
        ("priority", "priority"),
        ("automation", "automation"),
    ):
        value = str(args.get(query_key, "")).strip()
        if value:
            clauses.append(f"{column} = ?")
            values.append(value)
    sql = "SELECT * FROM test_cases"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += """
        ORDER BY
            CASE priority
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                ELSE 4
            END,
            updated_at DESC,
            id DESC
    """
    return get_db().execute(sql, values).fetchall()


def build_analytics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    by_status = {status: 0 for status in STATUSES}
    by_type = {item["name"]: 0 for item in TESTING_TYPES}
    by_priority = {priority: 0 for priority in PRIORITIES}
    by_automation = {state: 0 for state in AUTOMATION_STATES}
    for case in cases:
        by_status[case["status"]] = by_status.get(case["status"], 0) + 1
        by_type[case["testing_type"]] = by_type.get(case["testing_type"], 0) + 1
        by_priority[case["priority"]] = by_priority.get(case["priority"], 0) + 1
        by_automation[case["automation"]] = by_automation.get(case["automation"], 0) + 1
    passed = by_status.get("Passed", 0)
    failed = by_status.get("Failed", 0)
    blocked = by_status.get("Blocked", 0)
    active = by_status.get("In Progress", 0) + by_status.get("Not Started", 0)
    automated = by_automation.get("Automated", 0)
    critical_open = sum(
        1
        for case in cases
        if case["priority"] == "Critical" and case["status"] not in {"Passed"}
    )
    pass_rate = round((passed / total) * 100, 1) if total else 0
    automation_rate = round((automated / total) * 100, 1) if total else 0
    risk_score = min(100, failed * 18 + blocked * 14 + critical_open * 12 + active * 4)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "active": active,
        "critical_open": critical_open,
        "pass_rate": pass_rate,
        "automation_rate": automation_rate,
        "risk_score": risk_score,
        "by_status": by_status,
        "by_type": by_type,
        "by_priority": by_priority,
        "by_automation": by_automation,
    }


class PageSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self.buttons: list[dict[str, str]] = []
        self.forms: list[dict[str, Any]] = []
        self._in_title = False
        self._skip_depth = 0
        self._current_link: dict[str, str] | None = None
        self._current_button: dict[str, str] | None = None
        self._current_form: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        elif tag == "a":
            href = attrs_dict.get("href", "").strip()
            if href:
                self._current_link = {"href": href, "text": ""}
        elif tag == "form":
            self._current_form = {
                "action": attrs_dict.get("action", ""),
                "method": attrs_dict.get("method", "get").upper(),
                "inputs": [],
                "buttons": [],
            }
        elif tag == "input":
            input_type = attrs_dict.get("type", "text").lower() or "text"
            input_info = {
                "type": input_type,
                "name": attrs_dict.get("name", ""),
                "id": attrs_dict.get("id", ""),
                "placeholder": attrs_dict.get("placeholder", ""),
                "value": attrs_dict.get("value", ""),
            }
            if self._current_form is not None:
                self._current_form["inputs"].append(input_info)
            if input_type in {"submit", "button", "reset"}:
                label = (
                    attrs_dict.get("value")
                    or attrs_dict.get("name")
                    or input_type.title()
                )
                button = {"text": label.strip(), "type": input_type}
                self.buttons.append(button)
                if self._current_form is not None:
                    self._current_form["buttons"].append(button)
        elif tag == "button":
            self._current_button = {
                "text": "",
                "type": attrs_dict.get("type", "button"),
            }

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if not clean:
            return
        if self._in_title:
            self.title_parts.append(clean)
        elif self._current_link is not None:
            self._current_link["text"] = f"{self._current_link['text']} {clean}".strip()
        elif self._current_button is not None:
            self._current_button["text"] = (
                f"{self._current_button['text']} {clean}".strip()
            )
        elif self._skip_depth == 0:
            self.text_parts.append(clean)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._current_link is not None:
            self.links.append(self._current_link)
            self._current_link = None
        elif tag == "button" and self._current_button is not None:
            button = {
                "text": self._current_button["text"].strip() or "Button",
                "type": self._current_button.get("type", "button"),
            }
            self.buttons.append(button)
            if self._current_form is not None:
                self._current_form["buttons"].append(button)
            self._current_button = None
        elif tag == "form" and self._current_form is not None:
            self.forms.append(self._current_form)
            self._current_form = None

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        return " ".join(self.text_parts).strip()


def parse_line_values(value: Any) -> list[str]:
    if isinstance(value, list):
        source = "\n".join(str(item) for item in value)
    else:
        source = str(value or "")
    normalized = source.replace(",", "\n")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def normalize_base_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def build_page_url(base_url: str, page: str) -> str:
    page = page.strip()
    parsed = urlparse(page)
    if parsed.scheme in {"http", "https"}:
        return page
    if not page or page == "/":
        return base_url
    if page.startswith("/"):
        return urljoin(base_url, page)
    return urljoin(f"{base_url.rstrip('/')}/", page)


def execute_live_test(
    base_url: str,
    pages: list[str],
    expected_keywords: list[str],
    check_links: bool,
) -> dict[str, Any]:
    page_results = []
    discovered_links: dict[str, str] = {}
    for page in pages:
        url = build_page_url(base_url, page)
        result = inspect_page(url, page, expected_keywords)
        page_results.append(result)
        if check_links:
            collect_internal_links(base_url, result, discovered_links)
    link_results = []
    if check_links:
        for url, label in list(discovered_links.items())[:MAX_LINK_CHECKS]:
            link_results.append(check_link(url, label))
    failed_pages = sum(1 for item in page_results if item["status"] == "Failed")
    warning_pages = sum(1 for item in page_results if item["status"] == "Warning")
    passed_pages = sum(1 for item in page_results if item["status"] == "Passed")
    broken_links = sum(1 for item in link_results if not item["ok"])
    summary_status = "Passed"
    if failed_pages or broken_links:
        summary_status = "Failed"
    elif warning_pages:
        summary_status = "Warning"
    summary = {
        "status": summary_status,
        "pages_total": len(page_results),
        "passed_pages": passed_pages,
        "warning_pages": warning_pages,
        "failed_pages": failed_pages,
        "links_checked": len(link_results),
        "broken_links": broken_links,
    }
    return {
        "base_url": base_url,
        "pages": pages,
        "expected_keywords": expected_keywords,
        "check_links": check_links,
        "summary": summary,
        "page_results": page_results,
        "link_results": link_results,
        "created_at": utc_now(),
    }


def inspect_page(
    url: str, page_label: str, expected_keywords: list[str]
) -> dict[str, Any]:
    fetched = fetch_url(url)
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "name": "Page loads",
            "passed": fetched["ok"],
            "message": (
                f"HTTP {fetched['status_code']}"
                if fetched["status_code"]
                else fetched["error"]
            ),
        }
    )
    parser = PageSignalParser()
    parse_error = ""
    if fetched["body"] and "html" in fetched["content_type"].lower():
        try:
            parser.feed(fetched["body"])
        except Exception as error:
            parse_error = str(error)
    if fetched["ok"] and "html" not in fetched["content_type"].lower():
        checks.append(
            {
                "name": "HTML document",
                "passed": False,
                "severity": "warning",
                "message": f"Received {fetched['content_type'] or 'unknown content type'}",
            }
        )
    if parse_error:
        checks.append(
            {
                "name": "HTML parse",
                "passed": False,
                "severity": "warning",
                "message": parse_error,
            }
        )
    combined_text = " ".join(
        [
            parser.title,
            parser.text,
            " ".join(button["text"] for button in parser.buttons),
            " ".join(link["text"] for link in parser.links),
            url,
        ]
    ).lower()
    for keyword in expected_keywords:
        checks.append(
            {
                "name": f"Text contains '{keyword}'",
                "passed": keyword.lower() in combined_text,
                "message": "Found" if keyword.lower() in combined_text else "Missing",
            }
        )
    lower_context = f"{page_label} {url}".lower()
    is_auth_page = any(
        token in lower_context for token in ["login", "signin", "sign-in", "sign_in"]
    )
    if is_auth_page:
        login_checks = detect_login_signals(parser)
        checks.extend(login_checks)
    if not parser.buttons and not parser.links:
        checks.append(
            {
                "name": "Clickable controls",
                "passed": False,
                "severity": "warning",
                "message": "No links or buttons were detected in the HTML response",
            }
        )
    else:
        checks.append(
            {
                "name": "Clickable controls",
                "passed": True,
                "message": f"{len(parser.links)} links and {len(parser.buttons)} buttons detected",
            }
        )
    has_failure = any(
        not check["passed"] and check.get("severity") != "warning" for check in checks
    )
    has_warning = any(
        not check["passed"] and check.get("severity") == "warning" for check in checks
    )
    status = "Failed" if has_failure else "Warning" if has_warning else "Passed"
    return {
        "page": page_label,
        "url": url,
        "final_url": fetched["final_url"],
        "status_code": fetched["status_code"],
        "load_ms": fetched["load_ms"],
        "content_type": fetched["content_type"],
        "title": parser.title,
        "status": status,
        "checks": checks,
        "forms": summarize_forms(parser.forms),
        "buttons": parser.buttons[:20],
        "links": normalize_links(url, parser.links[:40]),
        "error": fetched["error"],
    }


def fetch_url(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "User-Agent": "QA-Test-Manager/1.0 (+local testing app)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body_bytes = response.read(MAX_HTML_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            body = body_bytes.decode(charset, errors="replace")
            return {
                "ok": 200 <= response.status < 400,
                "status_code": response.status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type", ""),
                "body": body,
                "load_ms": int((time.perf_counter() - started) * 1000),
                "error": "",
            }
    except HTTPError as error:
        body = ""
        try:
            charset = error.headers.get_content_charset() or "utf-8"
            body = error.read(MAX_HTML_BYTES).decode(charset, errors="replace")
        except Exception:
            pass
        return {
            "ok": False,
            "status_code": error.code,
            "final_url": url,
            "content_type": (
                error.headers.get("Content-Type", "") if error.headers else ""
            ),
            "body": body,
            "load_ms": int((time.perf_counter() - started) * 1000),
            "error": str(error),
        }
    except (URLError, TimeoutError, OSError) as error:
        return {
            "ok": False,
            "status_code": 0,
            "final_url": url,
            "content_type": "",
            "body": "",
            "load_ms": int((time.perf_counter() - started) * 1000),
            "error": str(error),
        }


def detect_login_signals(parser: PageSignalParser) -> list[dict[str, Any]]:
    inputs = [field for form in parser.forms for field in form["inputs"]]
    password_fields = [field for field in inputs if field["type"] == "password"]
    user_fields = [
        field
        for field in inputs
        if field["type"] in {"email", "text", "tel"}
        or any(
            token
            in " ".join([field["name"], field["id"], field["placeholder"]]).lower()
            for token in ["email", "user", "login", "mobile", "phone"]
        )
    ]
    submit_buttons = [
        button
        for button in parser.buttons
        if button.get("type", "").lower() == "submit"
        or any(
            token in button.get("text", "").lower()
            for token in ["login", "sign in", "signin", "submit"]
        )
    ]
    return [
        {
            "name": "Login form password field",
            "passed": bool(password_fields),
            "message": f"{len(password_fields)} password field(s) found",
        },
        {
            "name": "Login username/email field",
            "passed": bool(user_fields),
            "message": f"{len(user_fields)} username/email field(s) found",
        },
        {
            "name": "Login submit control",
            "passed": bool(submit_buttons),
            "message": f"{len(submit_buttons)} submit control(s) found",
        },
    ]


def summarize_forms(forms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for form in forms[:10]:
        summaries.append(
            {
                "action": form["action"],
                "method": form["method"],
                "input_types": [field["type"] for field in form["inputs"]],
                "input_count": len(form["inputs"]),
                "button_count": len(form["buttons"]),
            }
        )
    return summaries


def normalize_links(page_url: str, links: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "text": link.get("text", "")[:120],
            "href": link.get("href", ""),
            "absolute_url": urljoin(page_url, link.get("href", "")),
        }
        for link in links
    ]


def collect_internal_links(
    base_url: str, page_result: dict[str, Any], discovered: dict[str, str]
) -> None:
    base_host = urlparse(base_url).netloc.lower()
    for link in page_result.get("links", []):
        href = link.get("href", "").strip()
        absolute = link.get("absolute_url", "")
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != base_host:
            continue
        clean_url = absolute.split("#", 1)[0]
        discovered.setdefault(clean_url, link.get("text") or clean_url)
        if len(discovered) >= MAX_LINK_CHECKS:
            break


def check_link(url: str, label: str) -> dict[str, Any]:
    fetched = fetch_url(url)
    return {
        "url": url,
        "label": label[:120],
        "status_code": fetched["status_code"],
        "load_ms": fetched["load_ms"],
        "ok": fetched["ok"],
        "error": fetched["error"],
    }


def parse_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = DEFAULT_AUTOMATION_TIMEOUT_MS
    return max(1_000, min(timeout, 60_000))


def parse_automation_steps(steps_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    aliases = {
        "assert_text": "expect_text",
        "assert_url": "expect_url",
        "assert_visible": "expect_visible",
        "assert_title": "expect_title",
    }
    supported = {
        "goto",
        "fill",
        "click",
        "check",
        "uncheck",
        "select",
        "press",
        "wait",
        "expect_text",
        "expect_url",
        "expect_visible",
        "expect_title",
    }
    parsed_steps: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, raw_line in enumerate(steps_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pieces = stripped.split(maxsplit=1)
        command = aliases.get(
            pieces[0].lower().replace("-", "_"), pieces[0].lower().replace("-", "_")
        )
        argument = pieces[1].strip() if len(pieces) > 1 else ""
        if command not in supported:
            errors.append(f"Line {line_number}: unsupported command '{pieces[0]}'")
        elif command != "wait" and not argument:
            errors.append(f"Line {line_number}: '{command}' needs a value")
        else:
            parsed_steps.append(
                {
                    "line": line_number,
                    "raw": raw_line,
                    "command": command,
                    "argument": argument,
                }
            )
    if not parsed_steps and not errors:
        errors.append("No runnable automation steps were found")
    return parsed_steps, errors


def execute_browser_automation(
    scenario_name: str,
    base_url: str,
    steps_text: str,
    timeout_ms: int,
    headless: bool,
) -> dict[str, Any]:
    parsed_steps, parse_errors = parse_automation_steps(steps_text)
    if parse_errors:
        step_results = [
            {
                "line": 0,
                "command": "parse",
                "target": "",
                "passed": False,
                "message": error,
                "duration_ms": 0,
            }
            for error in parse_errors
        ]
        return build_automation_run_result(
            scenario_name,
            base_url,
            steps_text,
            timeout_ms,
            headless,
            "Failed",
            step_results,
            "",
            "",
            "Fix the step format and run again.",
        )
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        return execute_http_automation(
            scenario_name,
            base_url,
            steps_text,
            timeout_ms,
            headless,
            parsed_steps,
            f"Used HTML runner because Playwright is not installed: {error}. "
            "JavaScript-only flows need: pip install -r requirements.txt; python -m playwright install chromium",
        )
    step_results: list[dict[str, Any]] = []
    final_url = ""
    page_title = ""
    setup_message = ""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            for step in parsed_steps:
                step_results.append(run_browser_step(page, base_url, step, timeout_ms))
                if not step_results[-1]["passed"]:
                    break
            final_url = page.url
            try:
                page_title = page.title()
            except Exception:
                page_title = ""
            context.close()
            browser.close()
    except Exception as error:
        message = str(error)
        if "Executable doesn't exist" in message or "playwright install" in message:
            return execute_http_automation(
                scenario_name,
                base_url,
                steps_text,
                timeout_ms,
                headless,
                parsed_steps,
                "Used HTML runner because the Playwright browser is missing. "
                "JavaScript-only flows need: python -m playwright install chromium",
            )
        else:
            setup_message = message
            status = "Failed"
        if not step_results or step_results[-1]["passed"]:
            step_results.append(
                {
                    "line": 0,
                    "command": "browser",
                    "target": "chromium",
                    "passed": False,
                    "message": message,
                    "duration_ms": 0,
                }
            )
        return build_automation_run_result(
            scenario_name,
            base_url,
            steps_text,
            timeout_ms,
            headless,
            status,
            step_results,
            final_url,
            page_title,
            setup_message,
        )
    status = "Passed" if all(item["passed"] for item in step_results) else "Failed"
    return build_automation_run_result(
        scenario_name,
        base_url,
        steps_text,
        timeout_ms,
        headless,
        status,
        step_results,
        final_url,
        page_title,
        setup_message,
    )


def run_browser_step(
    page: Any, base_url: str, step: dict[str, Any], timeout_ms: int
) -> dict[str, Any]:
    started = time.perf_counter()
    command = step["command"]
    argument = step["argument"]
    try:
        message = ""
        target = argument
        if command == "goto":
            target = build_page_url(base_url, argument)
            response = page.goto(
                target, wait_until="domcontentloaded", timeout=timeout_ms
            )
            status = response.status if response else 0
            passed = bool(response and status < 400)
            message = (
                f"Loaded {target} with HTTP {status}"
                if response
                else f"Loaded {target}"
            )
        elif command == "fill":
            selector, value = split_step_assignment(argument)
            target = selector
            page.locator(selector).first.fill(value, timeout=timeout_ms)
            message = f"Filled {selector}"
            passed = True
        elif command == "click":
            page.locator(argument).first.click(timeout=timeout_ms)
            message = f"Clicked {argument}"
            passed = True
        elif command == "check":
            page.locator(argument).first.check(timeout=timeout_ms)
            message = f"Checked {argument}"
            passed = True
        elif command == "uncheck":
            page.locator(argument).first.uncheck(timeout=timeout_ms)
            message = f"Unchecked {argument}"
            passed = True
        elif command == "select":
            selector, value = split_step_assignment(argument)
            target = selector
            page.locator(selector).first.select_option(value, timeout=timeout_ms)
            message = f"Selected {value} in {selector}"
            passed = True
        elif command == "press":
            selector, key = split_step_assignment(argument)
            target = selector
            page.locator(selector).first.press(key, timeout=timeout_ms)
            message = f"Pressed {key} in {selector}"
            passed = True
        elif command == "wait":
            wait_target = argument.strip()
            target = wait_target or "load"
            if not wait_target:
                page.wait_for_load_state("load", timeout=timeout_ms)
                message = "Waited for page load"
            elif wait_target.isdigit():
                page.wait_for_timeout(int(wait_target))
                message = f"Waited {wait_target} ms"
            elif wait_target in {"load", "domcontentloaded", "networkidle"}:
                page.wait_for_load_state(wait_target, timeout=timeout_ms)
                message = f"Waited for {wait_target}"
            else:
                page.locator(wait_target).first.wait_for(
                    state="visible", timeout=timeout_ms
                )
                message = f"Waited for {wait_target}"
            passed = True
        elif command == "expect_text":
            body_text = page.locator("body").inner_text(timeout=timeout_ms)
            passed = argument.lower() in body_text.lower()
            message = "Text found" if passed else f"Text not found: {argument}"
        elif command == "expect_url":
            if argument not in page.url:
                page.wait_for_url(f"**{argument}**", timeout=timeout_ms)
            passed = argument in page.url
            message = f"Current URL is {page.url}"
        elif command == "expect_visible":
            page.locator(argument).first.wait_for(state="visible", timeout=timeout_ms)
            passed = True
            message = f"{argument} is visible"
        elif command == "expect_title":
            title = page.title()
            passed = argument.lower() in title.lower()
            message = (
                f"Title is '{title}'"
                if passed
                else f"Title '{title}' does not contain '{argument}'"
            )
        else:
            passed = False
            message = f"Unsupported command: {command}"
        return {
            "line": step["line"],
            "command": command,
            "target": target,
            "passed": passed,
            "message": message,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as error:
        return {
            "line": step["line"],
            "command": command,
            "target": argument,
            "passed": False,
            "message": str(error).splitlines()[0],
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


def execute_http_automation(
    scenario_name: str,
    base_url: str,
    steps_text: str,
    timeout_ms: int,
    headless: bool,
    parsed_steps: list[dict[str, Any]],
    fallback_message: str,
) -> dict[str, Any]:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    state: dict[str, Any] = {
        "current_url": "",
        "parser": PageSignalParser(),
        "raw_text": "",
        "filled": {},
        "timeout_seconds": max(1, timeout_ms / 1000),
    }
    step_results = []
    for step in parsed_steps:
        step_results.append(run_http_step(opener, state, base_url, step))
        if not step_results[-1]["passed"]:
            break
    status = (
        "Passed"
        if step_results and all(item["passed"] for item in step_results)
        else "Failed"
    )
    return build_automation_run_result(
        scenario_name,
        base_url,
        steps_text,
        timeout_ms,
        headless,
        status,
        step_results,
        state.get("current_url", ""),
        state.get("parser", PageSignalParser()).title,
        fallback_message,
    )


def run_http_step(
    opener: Any,
    state: dict[str, Any],
    base_url: str,
    step: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    command = step["command"]
    argument = step["argument"]
    target = argument
    try:
        if command == "goto":
            target = build_page_url(base_url, argument)
            fetched = fetch_with_opener(opener, target, state["timeout_seconds"])
            update_http_state(state, fetched)
            passed = fetched["ok"]
            message = f"Loaded {target} with HTTP {fetched['status_code']}"
        elif command == "fill":
            selector, value = split_step_assignment(argument)
            target = selector
            state["filled"][selector] = value
            passed = True
            message = f"Stored value for {selector}"
        elif command == "click":
            fetched, message = http_click(opener, state, argument)
            update_http_state(state, fetched)
            passed = fetched["ok"]
        elif command == "expect_text":
            visible_text = get_http_visible_text(state)
            passed = argument.lower() in visible_text.lower()
            message = "Text found" if passed else f"Text not found: {argument}"
        elif command == "expect_title":
            title = state["parser"].title
            passed = argument.lower() in title.lower()
            message = (
                f"Title is '{title}'"
                if passed
                else f"Title '{title}' does not contain '{argument}'"
            )
        elif command == "expect_url":
            current_url = state.get("current_url", "")
            passed = argument in current_url
            message = f"Current URL is {current_url}"
        elif command == "expect_visible":
            visible_text = get_http_visible_text(state)
            matched = (
                http_selector_exists(state["parser"], argument)
                or argument.lower() in visible_text.lower()
            )
            passed = matched
            message = (
                f"{argument} was detected" if passed else f"{argument} was not detected"
            )
        elif command in {"wait", "check", "uncheck", "select", "press"}:
            passed = True
            message = f"{command} recorded by HTML runner"
        else:
            passed = False
            message = f"Unsupported by HTML runner: {command}"
        return {
            "line": step["line"],
            "command": command,
            "target": target,
            "passed": passed,
            "message": message,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as error:
        return {
            "line": step["line"],
            "command": command,
            "target": target,
            "passed": False,
            "message": str(error).splitlines()[0],
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


def fetch_with_opener(
    opener: Any,
    url: str,
    timeout_seconds: float,
    data: dict[str, str] | None = None,
    method: str = "GET",
) -> dict[str, Any]:
    started = time.perf_counter()
    body = urlencode(data or {}).encode("utf-8") if data is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "User-Agent": "QA-Test-Manager/1.0 (+local automation runner)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            body_bytes = response.read(MAX_HTML_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            return {
                "ok": 200 <= response.status < 400,
                "status_code": response.status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type", ""),
                "body": body_bytes.decode(charset, errors="replace"),
                "load_ms": int((time.perf_counter() - started) * 1000),
                "error": "",
            }
    except HTTPError as error:
        error_body = ""
        try:
            charset = error.headers.get_content_charset() or "utf-8"
            error_body = error.read(MAX_HTML_BYTES).decode(charset, errors="replace")
        except Exception:
            pass
        return {
            "ok": False,
            "status_code": error.code,
            "final_url": url,
            "content_type": (
                error.headers.get("Content-Type", "") if error.headers else ""
            ),
            "body": error_body,
            "load_ms": int((time.perf_counter() - started) * 1000),
            "error": str(error),
        }
    except (URLError, TimeoutError, OSError) as error:
        return {
            "ok": False,
            "status_code": 0,
            "final_url": url,
            "content_type": "",
            "body": "",
            "load_ms": int((time.perf_counter() - started) * 1000),
            "error": str(error),
        }


def update_http_state(state: dict[str, Any], fetched: dict[str, Any]) -> None:
    parser = PageSignalParser()
    if fetched["body"]:
        try:
            parser.feed(fetched["body"])
        except Exception:
            pass
    state["current_url"] = fetched["final_url"]
    state["parser"] = parser
    state["raw_text"] = fetched["body"]


def get_http_visible_text(state: dict[str, Any]) -> str:
    parser = state["parser"]
    return " ".join(
        [
            parser.title,
            parser.text,
            " ".join(button["text"] for button in parser.buttons),
            " ".join(link["text"] for link in parser.links),
            state.get("current_url", ""),
        ]
    )


def http_click(
    opener: Any, state: dict[str, Any], selector: str
) -> tuple[dict[str, Any], str]:
    link = find_http_link(state["parser"], selector)
    if link is not None:
        url = urljoin(state["current_url"], link["href"])
        return (
            fetch_with_opener(opener, url, state["timeout_seconds"]),
            f"Clicked link {selector}",
        )
    form = choose_form_for_submission(state["parser"], selector)
    if form is None:
        raise ValueError(f"No link or form submit matched '{selector}'")
    data = build_form_data(form, state["filled"])
    action = urljoin(state["current_url"], form.get("action") or state["current_url"])
    method = form.get("method", "GET").upper()
    if method == "POST":
        fetched = fetch_with_opener(
            opener, action, state["timeout_seconds"], data=data, method="POST"
        )
    else:
        separator = "&" if "?" in action else "?"
        fetched = fetch_with_opener(
            opener, f"{action}{separator}{urlencode(data)}", state["timeout_seconds"]
        )
    return fetched, f"Submitted form using {selector}"


def find_http_link(parser: PageSignalParser, selector: str) -> dict[str, str] | None:
    target = selector.strip()
    lowered = target.lower()
    if lowered.startswith("text="):
        text = target[5:].strip().lower()
        for link in parser.links:
            if text and text in link.get("text", "").lower():
                return link
    for link in parser.links:
        if target == link.get("href") or target in link.get("href", ""):
            return link
    return None


def choose_form_for_submission(
    parser: PageSignalParser, selector: str
) -> dict[str, Any] | None:
    if not parser.forms:
        return None
    lowered = selector.lower()
    for form in parser.forms:
        for button in form.get("buttons", []):
            button_text = button.get("text", "").lower()
            button_type = button.get("type", "").lower()
            if (
                "submit" in lowered
                and button_type == "submit"
                or button_text
                and button_text in lowered
                or any(token in button_text for token in ["login", "sign in", "signin"])
            ):
                return form
    for form in parser.forms:
        if any(field["type"] == "password" for field in form.get("inputs", [])):
            return form
    return parser.forms[0]


def build_form_data(form: dict[str, Any], filled: dict[str, str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for field in form.get("inputs", []):
        name = field.get("name") or field.get("id")
        if not name:
            continue
        if field.get("type") in {"submit", "button", "reset", "file"}:
            continue
        data[name] = field.get("value", "")
        matched_value = find_filled_value_for_field(field, filled)
        if matched_value is not None:
            data[name] = matched_value
    return data


def find_filled_value_for_field(
    field: dict[str, str], filled: dict[str, str]
) -> str | None:
    haystack = " ".join(
        [
            field.get("name", ""),
            field.get("id", ""),
            field.get("placeholder", ""),
            field.get("type", ""),
        ]
    ).lower()
    for selector, value in filled.items():
        lowered = selector.lower()
        name = field.get("name", "").lower()
        field_id = field.get("id", "").lower()
        if selector == field.get("name") or selector == field.get("id"):
            return value
        if name and f'name="{name}"' in lowered:
            return value
        if field_id and (lowered == f"#{field_id}" or f'id="{field_id}"' in lowered):
            return value
        if any(token and token in lowered for token in haystack.split()):
            return value
    return None


def http_selector_exists(parser: PageSignalParser, selector: str) -> bool:
    lowered = selector.lower()
    if lowered.startswith("text="):
        text = lowered[5:].strip()
        return any(
            text in link.get("text", "").lower() for link in parser.links
        ) or any(text in button.get("text", "").lower() for button in parser.buttons)
    for form in parser.forms:
        for field in form.get("inputs", []):
            name = field.get("name", "").lower()
            field_id = field.get("id", "").lower()
            if name and f'name="{name}"' in lowered:
                return True
            if field_id and (
                lowered == f"#{field_id}" or f'id="{field_id}"' in lowered
            ):
                return True
    return False


def split_step_assignment(argument: str) -> tuple[str, str]:
    if " = " not in argument:
        raise ValueError("Use this format: selector = value")
    selector, value = argument.split(" = ", 1)
    selector = selector.strip()
    value = value.strip()
    if not selector or not value:
        raise ValueError("Selector and value are required")
    return selector, value


def build_automation_run_result(
    scenario_name: str,
    base_url: str,
    steps_text: str,
    timeout_ms: int,
    headless: bool,
    status: str,
    step_results: list[dict[str, Any]],
    final_url: str,
    page_title: str,
    setup_message: str,
) -> dict[str, Any]:
    passed_steps = sum(1 for item in step_results if item["passed"])
    failed_steps = sum(1 for item in step_results if not item["passed"])
    return {
        "scenario_name": scenario_name,
        "base_url": base_url,
        "steps": steps_text,
        "timeout_ms": timeout_ms,
        "headless": headless,
        "summary": {
            "status": status,
            "steps_total": len(step_results),
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "final_url": final_url,
            "page_title": page_title,
            "setup_message": setup_message,
        },
        "step_results": step_results,
        "created_at": utc_now(),
    }


def parse_api_request_blocks(
    requests_text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    blocks = [
        block.strip()
        for block in requests_text.replace("\r\n", "\n").split("\n\n")
        if block.strip()
    ]
    parsed: list[dict[str, Any]] = []
    errors: list[str] = []
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    for block_number, block in enumerate(blocks, start=1):
        lines = [
            line.strip()
            for line in block.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not lines:
            continue
        first = lines[0].split(maxsplit=1)
        if len(first) != 2 or first[0].upper() not in valid_methods:
            errors.append(
                f"Block {block_number}: first line must be like 'GET /api/path'"
            )
            continue
        request_item = {
            "block": block_number,
            "method": first[0].upper(),
            "url": first[1].strip(),
            "headers": {},
            "body": "",
            "expect_status": None,
            "expect_text": [],
            "expect_json": [],
            "expect_max_ms": None,
            "raw": block,
        }
        for line in lines[1:]:
            upper = line.upper()
            if upper.startswith("HEADER "):
                header_value = line[7:].strip()
                if ":" not in header_value:
                    errors.append(
                        f"Block {block_number}: HEADER must be like 'HEADER Name: Value'"
                    )
                    continue
                key, value = header_value.split(":", 1)
                request_item["headers"][key.strip()] = value.strip()
            elif upper.startswith("BODY "):
                request_item["body"] = line[5:].strip()
            elif upper.startswith("EXPECT_STATUS "):
                try:
                    request_item["expect_status"] = int(line[14:].strip())
                except ValueError:
                    errors.append(
                        f"Block {block_number}: EXPECT_STATUS must be a number"
                    )
            elif upper.startswith("EXPECT_TEXT "):
                request_item["expect_text"].append(line[12:].strip())
            elif upper.startswith("EXPECT_JSON "):
                expression = line[12:].strip()
                if " = " not in expression:
                    errors.append(
                        f"Block {block_number}: EXPECT_JSON must be like 'path.to.value = expected'"
                    )
                else:
                    path, expected = expression.split(" = ", 1)
                    request_item["expect_json"].append(
                        {
                            "path": path.strip(),
                            "expected": parse_expected_value(expected.strip()),
                        }
                    )
            elif upper.startswith("EXPECT_MAX_MS "):
                try:
                    request_item["expect_max_ms"] = int(line[14:].strip())
                except ValueError:
                    errors.append(
                        f"Block {block_number}: EXPECT_MAX_MS must be a number"
                    )
            else:
                errors.append(f"Block {block_number}: unsupported line '{line}'")
        parsed.append(request_item)
    if not parsed and not errors:
        errors.append("No runnable API request blocks were found")
    return parsed, errors


def parse_expected_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")


def execute_api_test_suite(
    suite_name: str,
    base_url: str,
    engine: str,
    requests_text: str,
    suite_headers: dict[str, str],
    timeout_ms: int,
) -> dict[str, Any]:
    request_items, parse_errors = parse_api_request_blocks(requests_text)
    if parse_errors:
        request_results = [
            {
                "block": 0,
                "method": "PARSE",
                "url": "",
                "status_code": 0,
                "duration_ms": 0,
                "passed": False,
                "checks": [
                    {"name": "Request format", "passed": False, "message": error}
                ],
                "response_excerpt": "",
            }
            for error in parse_errors
        ]
        return build_api_run_result(
            suite_name,
            base_url,
            engine,
            timeout_ms,
            requests_text,
            "Failed",
            request_results,
            "",
        )
    setup_message = ""
    if engine == "playwright":
        request_results, setup_message = run_api_suite_with_playwright(
            base_url, request_items, suite_headers, timeout_ms
        )
    elif engine == "selenium":
        request_results, setup_message = run_api_suite_with_selenium(
            base_url, request_items, suite_headers, timeout_ms
        )
    else:
        request_results = run_api_suite_with_http(
            base_url, request_items, suite_headers, timeout_ms
        )
    if setup_message and not request_results:
        request_results = [
            {
                "block": 0,
                "method": engine.upper(),
                "url": base_url,
                "status_code": 0,
                "duration_ms": 0,
                "passed": False,
                "checks": [
                    {"name": "Engine setup", "passed": False, "message": setup_message}
                ],
                "response_excerpt": "",
            }
        ]
    status = (
        "Passed"
        if request_results and all(item["passed"] for item in request_results)
        else "Failed"
    )
    return build_api_run_result(
        suite_name,
        base_url,
        engine,
        timeout_ms,
        requests_text,
        status,
        request_results,
        setup_message,
    )


def run_api_suite_with_http(
    base_url: str,
    request_items: list[dict[str, Any]],
    suite_headers: dict[str, str],
    timeout_ms: int,
) -> list[dict[str, Any]]:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    results = []
    for item in request_items:
        url = build_page_url(base_url, item["url"])
        headers = {**suite_headers, **item["headers"]}
        response = perform_http_api_request(
            opener, item["method"], url, headers, item["body"], timeout_ms / 1000
        )
        results.append(evaluate_api_response(item, url, response))
    return results


def run_api_suite_with_playwright(
    base_url: str,
    request_items: list[dict[str, Any]],
    suite_headers: dict[str, str],
    timeout_ms: int,
) -> tuple[list[dict[str, Any]], str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        return [], f"Playwright is not installed: {error}"
    results = []
    try:
        with sync_playwright() as playwright:
            context = playwright.request.new_context(
                extra_http_headers=suite_headers, timeout=timeout_ms
            )
            for item in request_items:
                url = build_page_url(base_url, item["url"])
                headers = item["headers"]
                started = time.perf_counter()
                response = context.fetch(
                    url,
                    method=item["method"],
                    headers=headers or None,
                    data=item["body"] or None,
                    timeout=timeout_ms,
                )
                text = response.text()
                result = {
                    "ok": 200 <= response.status < 400,
                    "status_code": response.status,
                    "final_url": url,
                    "body": text,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "error": "",
                }
                results.append(evaluate_api_response(item, url, result))
            context.dispose()
    except Exception as error:
        return results, str(error)
    return results, ""


def run_api_suite_with_selenium(
    base_url: str,
    request_items: list[dict[str, Any]],
    suite_headers: dict[str, str],
    timeout_ms: int,
) -> tuple[list[dict[str, Any]], str]:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception as error:
        return [], f"Selenium is not installed: {error}"
    results = []
    driver = None
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=options)
        driver.set_script_timeout(max(1, timeout_ms // 1000))
        driver.get(base_url)
        for item in request_items:
            url = build_page_url(base_url, item["url"])
            headers = {**suite_headers, **item["headers"]}
            started = time.perf_counter()
            script_result = driver.execute_async_script(
                """
                const [url, method, headers, body, done] = arguments;
                fetch(url, {
                  method,
                  headers,
                  body: body || undefined,
                  credentials: 'include'
                })
                  .then(async response => done({
                    ok: response.ok,
                    status_code: response.status,
                    final_url: response.url,
                    body: await response.text(),
                    error: ''
                  }))
                  .catch(error => done({
                    ok: false,
                    status_code: 0,
                    final_url: url,
                    body: '',
                    error: String(error)
                  }));
                """,
                url,
                item["method"],
                headers,
                item["body"],
            )
            script_result["duration_ms"] = int((time.perf_counter() - started) * 1000)
            results.append(evaluate_api_response(item, url, script_result))
    except Exception as error:
        return results, f"Selenium run failed: {error}"
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    return results, ""


def perform_http_api_request(
    opener: Any,
    method: str,
    url: str,
    headers: dict[str, str],
    body: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    data = body.encode("utf-8") if body and method not in {"GET", "HEAD"} else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "User-Agent": "QA-Test-Manager/1.0 (+api testing)",
            **headers,
        },
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body_text = response.read(MAX_HTML_BYTES).decode(charset, errors="replace")
            return {
                "ok": 200 <= response.status < 400,
                "status_code": response.status,
                "final_url": response.geturl(),
                "body": body_text,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error": "",
            }
    except HTTPError as error:
        error_body = ""
        try:
            charset = error.headers.get_content_charset() or "utf-8"
            error_body = error.read(MAX_HTML_BYTES).decode(charset, errors="replace")
        except Exception:
            pass
        return {
            "ok": False,
            "status_code": error.code,
            "final_url": url,
            "body": error_body,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": str(error),
        }
    except (URLError, TimeoutError, OSError) as error:
        return {
            "ok": False,
            "status_code": 0,
            "final_url": url,
            "body": "",
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "error": str(error),
        }


def evaluate_api_response(
    item: dict[str, Any], url: str, response: dict[str, Any]
) -> dict[str, Any]:
    checks = []
    expected_status = item["expect_status"]
    if expected_status is None:
        checks.append(
            {
                "name": "HTTP success",
                "passed": 200 <= response["status_code"] < 400,
                "message": f"HTTP {response['status_code']}",
            }
        )
    else:
        checks.append(
            {
                "name": f"Status is {expected_status}",
                "passed": response["status_code"] == expected_status,
                "message": f"HTTP {response['status_code']}",
            }
        )
    for expected_text in item["expect_text"]:
        checks.append(
            {
                "name": f"Text contains '{expected_text}'",
                "passed": expected_text.lower() in response["body"].lower(),
                "message": (
                    "Found"
                    if expected_text.lower() in response["body"].lower()
                    else "Missing"
                ),
            }
        )
    response_json: Any = None
    json_error = ""
    if item["expect_json"]:
        try:
            response_json = json.loads(response["body"])
        except json.JSONDecodeError as error:
            json_error = str(error)
    for expected_json in item["expect_json"]:
        actual_value = (
            get_json_path_value(response_json, expected_json["path"])
            if response_json is not None
            else None
        )
        passed = actual_value == expected_json["expected"]
        checks.append(
            {
                "name": f"JSON {expected_json['path']}",
                "passed": passed,
                "message": (
                    f"Expected {expected_json['expected']!r}, got {actual_value!r}"
                    if not json_error
                    else json_error
                ),
            }
        )
    if item["expect_max_ms"] is not None:
        checks.append(
            {
                "name": f"Response under {item['expect_max_ms']} ms",
                "passed": response["duration_ms"] <= item["expect_max_ms"],
                "message": f"{response['duration_ms']} ms",
            }
        )
    if response["error"]:
        checks.append(
            {"name": "Request error", "passed": False, "message": response["error"]}
        )
    return {
        "block": item["block"],
        "method": item["method"],
        "url": url,
        "status_code": response["status_code"],
        "duration_ms": response["duration_ms"],
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "response_excerpt": response["body"][:800],
    }


def get_json_path_value(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def build_api_run_result(
    suite_name: str,
    base_url: str,
    engine: str,
    timeout_ms: int,
    requests_text: str,
    status: str,
    request_results: list[dict[str, Any]],
    setup_message: str,
) -> dict[str, Any]:
    passed_requests = sum(1 for item in request_results if item["passed"])
    failed_requests = sum(1 for item in request_results if not item["passed"])
    average_ms = (
        round(
            sum(item["duration_ms"] for item in request_results) / len(request_results),
            1,
        )
        if request_results
        else 0
    )
    return {
        "suite_name": suite_name,
        "base_url": base_url,
        "engine": engine,
        "timeout_ms": timeout_ms,
        "requests": requests_text,
        "summary": {
            "status": status,
            "requests_total": len(request_results),
            "passed_requests": passed_requests,
            "failed_requests": failed_requests,
            "average_ms": average_ms,
            "setup_message": setup_message,
        },
        "request_results": request_results,
        "created_at": utc_now(),
    }


def build_pdf_report(
    cases: list[dict[str, Any]],
    live_rows: list[sqlite3.Row],
    automation_rows: list[sqlite3.Row],
    api_rows: list[sqlite3.Row],
) -> bytes:
    analytics = build_analytics(cases)
    lines = [
        "QA Test Manager Report",
        f"Generated: {utc_now()}",
        "",
        "Summary",
        f"Total cases: {analytics['total']}",
        f"Pass rate: {analytics['pass_rate']}%",
        f"Automation coverage: {analytics['automation_rate']}%",
        f"Open risk score: {analytics['risk_score']}",
        f"Critical open cases: {analytics['critical_open']}",
        "",
        "Status Distribution",
    ]
    lines.extend(
        f"- {status}: {count}" for status, count in analytics["by_status"].items()
    )
    lines.extend(["", "Testing Type Coverage"])
    lines.extend(
        f"- {testing_type}: {count}"
        for testing_type, count in analytics["by_type"].items()
        if count
    )
    lines.extend(["", "Recent Test Cases"])
    for case in cases[:18]:
        lines.extend(
            [
                f"#{case['id']} {case['title']}",
                f"  Type: {case['testing_type']} | Status: {case['status']} | Priority: {case['priority']} | Automation: {case['automation']}",
                f"  Owner: {case['owner'] or 'Unassigned'} | Environment: {case['environment'] or 'N/A'}",
            ]
        )
    if not cases:
        lines.append("- No test cases found.")
    lines.extend(["", "Recent Live Page Runs"])
    if live_rows:
        for row in live_rows:
            summary = json.loads(row["summary_json"])
            lines.append(
                f"#{row['id']} {row['base_url']} | {summary['status']} | pages {summary['pages_total']} | broken links {summary['broken_links']}"
            )
    else:
        lines.append("- No live runs found.")
    lines.extend(["", "Recent Automation Runs"])
    if automation_rows:
        for row in automation_rows:
            summary = json.loads(row["summary_json"])
            lines.append(
                f"#{row['id']} {row['scenario_name']} | {summary['status']} | steps {summary['steps_total']} | base {row['base_url']}"
            )
    else:
        lines.append("- No automation runs found.")
    lines.extend(["", "Recent API Test Runs"])
    if api_rows:
        for row in api_rows:
            summary = json.loads(row["summary_json"])
            lines.append(
                f"#{row['id']} {row['suite_name']} | {row['engine']} | {summary['status']} | requests {summary['requests_total']} | base {row['base_url']}"
            )
    else:
        lines.append("- No API test runs found.")
    return make_simple_pdf(lines)


def make_simple_pdf(lines: list[str]) -> bytes:
    page_width = 612
    page_height = 792
    margin_x = 48
    top_y = 744
    line_height = 14
    min_y = 54
    pages: list[list[str]] = [[]]
    for line in lines:
        wrapped = wrap_pdf_line(line, 92) or [""]
        for wrapped_line in wrapped:
            if len(pages[-1]) >= (top_y - min_y) // line_height:
                pages.append([])
            pages[-1].append(wrapped_line)
    objects: list[bytes] = []

    def add_object(content: bytes) -> int:
        objects.append(content)
        return len(objects)

    catalog_id = add_object(b"")
    pages_id = add_object(b"")
    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for page_lines in pages:
        content_lines = ["BT", "/F1 10 Tf", "14 TL", f"{margin_x} {top_y} Td"]
        for index, line in enumerate(page_lines):
            if index:
                content_lines.append("T*")
            content_lines.append(f"({escape_pdf_text(line)}) Tj")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", errors="replace")
        content_id = add_object(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        page_ids.append(page_id)
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode(
        "ascii"
    )
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    )
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, content in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(content)
        output.extend(b"\nendobj\n")
    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def wrap_pdf_line(line: str, width: int) -> list[str]:
    if len(line) <= width:
        return [line]
    words = line.split()
    if not words:
        return [line[:width]]
    wrapped: list[str] = []
    current = ""
    for word in words:
        if len(word) > width:
            if current:
                wrapped.append(current)
                current = ""
            wrapped.extend(
                word[index : index + width] for index in range(0, len(word), width)
            )
        elif not current:
            current = word
        elif len(current) + len(word) + 1 <= width:
            current = f"{current} {word}"
        else:
            wrapped.append(current)
            current = word
    if current:
        wrapped.append(current)
    return wrapped


def escape_pdf_text(text: str) -> str:
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


app = create_app()
if __name__ == "__main__":
    app.run(debug=True, port=5001)
