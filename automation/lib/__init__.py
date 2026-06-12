"""Family inc. shared library — single implementations only.

Rules (ENGINEERING.md §1): scripts never define utilities that belong here.
Nothing outside `sheet.py` reads the master workbook. Nothing outside
`outbox.py` writes toward a phone. Nothing outside `llm.py` imports anthropic.
"""
