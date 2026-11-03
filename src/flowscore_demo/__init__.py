"""Demo-only code: synthetic Philippine borrowers for the app demo (slice 2, D23).

Kept outside the `flowscore` research package so that research code can never use synthetic
data (hard rule 9). The dependency goes one way only: this package may import `flowscore`
(the canonical schema), and nothing in `flowscore` may import this package
(tests/test_synthetic.py::test_research_package_never_imports_the_demo_package).
"""
