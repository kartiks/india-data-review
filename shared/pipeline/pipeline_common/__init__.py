"""Code shared by the India Data Review pipelines (budget, gdp, jobs-prices).

- report: the validation report every area writes (Markdown for people, JSON for the site)
- download: HTTP downloads with retries, saving with snapshots, the sources manifest, MoSPI's paged API
- budget_glance: where Budget at a Glance is on indiabudget.gov.in, and the GDP the budget assumes
- text: ids made from labels (slug) and fiscal-year labels (fy, fy_start, prev_fy, next_fy)
- numbers: reading numbers as sources print them (number, blank_or_number, strict_number)

Area-specific code stays in the areas.
"""
