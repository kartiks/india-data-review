"""Code shared by the India Data Review pipelines (budget, gdp, jobs-prices).

- report: the validation report every area writes (Markdown for people, JSON for the site)
- download: HTTP downloads with retries, saving with snapshots, the sources manifest, MoSPI's paged API
- budget_glance: where Budget at a Glance is on indiabudget.gov.in, and the GDP the budget assumes

Area-specific code stays in the areas.
"""
