"""Public site for the dataset (SPEC plans/2026-10-03-public-site).

``python -m disclosures web {build,check,publish-data,make-fixture,probe-links}``.
This package imports only the standard library, Jinja2 (pages, phase B) and the stdlib-only
parts of ``disclosures`` (``export``, ``dbconst``, ``normalise``, ``sources``), so a CI runner
can build the site after ``pip install Jinja2`` alone (ADR-W2).
"""

WEB_BUNDLE_VERSION = "1"
