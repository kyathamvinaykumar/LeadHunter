"""On-demand, single-page website quality checks."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from time import perf_counter
from urllib.parse import urlsplit

import requests


class WebsiteAuditError(Exception):
    """Raised when the selected website cannot be audited."""


@dataclass(frozen=True)
class WebsiteAuditResult:
    url: str
    https: bool | None
    meta_title: bool | None
    meta_description: bool | None
    contact_form: bool | None
    mobile_viewport: bool | None
    social_links: tuple[str, ...]
    reachable: bool = True
    response_time_ms: float | None = None
    page_title: str | None = None
    website_builder: str = "Unknown"
    response_status_code: int | None = None
    meta_description_text: str | None = None

    @property
    def score(self) -> int | None:
        if not self.reachable:
            return None
        return (
            2 * int(self.https is True)
            + 2 * int(self.meta_title is True)
            + 2 * int(self.meta_description is True)
            + 2 * int(self.contact_form is True)
            + int(self.mobile_viewport is True)
            + int(bool(self.social_links))
        )

    @property
    def grade(self) -> str:
        if self.score is None:
            return "Unknown"
        if self.score >= 9:
            return "Excellent"
        if self.score >= 7:
            return "Good"
        if self.score >= 5:
            return "Average"
        return "Poor"

    @property
    def summary(self) -> str:
        if not self.reachable:
            return "Website could not be reached; content checks are unavailable."
        return f"{sum(value is True for value in self.checks().values())} of 6 checks passed."

    @property
    def quality_status(self) -> str:
        if self.score is None:
            return "Unknown"
        if self.score >= 9:
            return "Excellent"
        if self.score >= 7:
            return "Good"
        return "Needs Improvement"

    def checks(self) -> dict[str, bool | None]:
        return {
            "HTTPS": self.https,
            "Meta Title": self.meta_title,
            "Meta Description": self.meta_description,
            "Contact Form": self.contact_form,
            "Mobile Viewport": self.mobile_viewport,
            "Social Links": bool(self.social_links) if self.reachable else None,
        }

    def to_export_dict(self) -> dict[str, str | int | float | bool | list[str] | None]:
        return {
            "website_audit_score": self.score,
            "website_audit_grade": self.grade,
            "website_quality_status": self.quality_status,
            "website_audit_summary": self.summary,
            "audit_https": self.https,
            "audit_reachable": self.reachable,
            "audit_response_time_ms": self.response_time_ms,
            "audit_page_title": self.page_title,
            "audit_meta_description_text": self.meta_description_text,
            "audit_website_builder": self.website_builder,
            "audit_http_status": self.response_status_code,
            "audit_meta_title": self.meta_title,
            "audit_meta_description": self.meta_description,
            "audit_contact_form": self.contact_form,
            "audit_mobile_viewport": self.mobile_viewport,
            "audit_social_links": list(self.social_links),
        }


class _AuditHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_exists = False
        self.title_text = ""
        self.description_exists = False
        self.description_text = ""
        self.viewport_exists = False
        self.contact_form_exists = False
        self.social_links: set[str] = set()
        self._in_title = False
        self._title_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attributes.get("name", "").casefold()
            content = attributes.get("content", "").strip()
            if name == "description" and content:
                self.description_exists = True
                self.description_text = content
            if name == "viewport" and content:
                self.viewport_exists = True
        elif tag == "form":
            self.contact_form_exists = True
        elif tag == "a":
            href = attributes.get("href", "").casefold()
            for domain in ("instagram.com", "facebook.com", "linkedin.com"):
                if domain in href:
                    self.social_links.add(domain)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.title_text = " ".join(self._title_text.split())
            self.title_exists = bool(self.title_text)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_text += data


class WebsiteAuditor:
    """Audit one website when explicitly called by the user."""

    def __init__(
        self,
        *,
        timeout: float = 12.0,
        session: requests.Session | None = None,
        user_agent: str = "LeadHunter/0.1 (website quality audit)",
    ) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()
        self._user_agent = user_agent

    def audit(self, website_url: str) -> WebsiteAuditResult:
        url = website_url.strip()
        parsed = urlsplit(url)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Website URL must be a valid HTTP or HTTPS URL.")
        started = perf_counter()
        try:
            response = self._session.get(
                url,
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout,
            )
        except requests.RequestException:
            elapsed_ms = (perf_counter() - started) * 1000
            return self._unreachable_result(url, elapsed_ms)
        elapsed_ms = (perf_counter() - started) * 1000
        response_status = getattr(response, "status_code", None)
        if not isinstance(response_status, int):
            response_status = None

        parser = _AuditHTMLParser()
        try:
            parser.feed(response.text)
            parser.close()
        except (AssertionError, ValueError) as error:
            raise WebsiteAuditError("The website returned malformed HTML.") from error

        return WebsiteAuditResult(
            url=response.url or url,
            https=(urlsplit(response.url or url).scheme.casefold() == "https"),
            meta_title=parser.title_exists,
            meta_description=parser.description_exists,
            contact_form=parser.contact_form_exists,
            mobile_viewport=parser.viewport_exists,
            social_links=tuple(sorted(parser.social_links)),
            reachable=True,
            response_time_ms=round(elapsed_ms, 1),
            page_title=parser.title_text or None,
            website_builder=self._detect_builder(response.url or url, response.text),
            response_status_code=response_status,
            meta_description_text=parser.description_text or None,
        )

    @staticmethod
    def _detect_builder(url: str, html: str) -> str:
        source = f"{url}\n{html}".casefold()
        signatures = (
            ("Wix", ("wixstatic.com", "wix.com", "x-wix")),
            ("WordPress", ("wp-content", "wp-includes", "wordpress")),
            ("Squarespace", ("squarespace.com", "static1.squarespace.com")),
            ("Shopify", ("cdn.shopify.com", "shopify.theme", "myshopify.com")),
            ("Webflow", ("webflow.js", "website-files.com", "webflow.com")),
        )
        for builder, markers in signatures:
            if any(marker in source for marker in markers):
                return builder
        return "Unknown"

    @staticmethod
    def _unreachable_result(url: str, response_time_ms: float) -> WebsiteAuditResult:
        return WebsiteAuditResult(
            url=url,
            https=urlsplit(url).scheme.casefold() == "https",
            meta_title=None,
            meta_description=None,
            contact_form=None,
            mobile_viewport=None,
            social_links=(),
            reachable=False,
            response_time_ms=round(response_time_ms, 1),
        )