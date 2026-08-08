"""
templates.py — stub for v0.2

v0.1: no template system, returns None.
v0.2 will add curated templates (fastapi, nextjs, python-lib, etc.)
and expose list/get helpers.
"""

TEMPLATES = {}

def list_templates():
    return list(TEMPLATES.keys())

def get_template(name: str):
    return TEMPLATES.get(name)
