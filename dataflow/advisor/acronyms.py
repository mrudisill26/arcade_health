"""Expand Red Hat acronyms before embedding queries."""

from __future__ import annotations

import re

ACRONYMS: dict[str, str] = {
    "AAP": "Ansible Automation Platform",
    "ACM": "Advanced Cluster Management",
    "RHACM": "Advanced Cluster Management",
    "ACS": "Advanced Cluster Security",
    "RHACS": "Advanced Cluster Security",
    "RHOAI": "Red Hat OpenShift AI",
    "OCP": "OpenShift Container Platform",
    "ARO": "Azure Red Hat OpenShift",
    "ROSA": "Red Hat OpenShift Service on AWS",
    "RHEL": "Red Hat Enterprise Linux",
    "RHDH": "Red Hat Developer Hub",
    "SNO": "Single Node OpenShift",
    "RHSSO": "Red Hat Single Sign-On",
    "EDA": "Event-Driven Ansible",
    "TAP": "Trusted Application Pipeline",
}

STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "about",
    "what", "show", "need", "content", "similar", "item", "demo", "using",
}


def expand_acronyms(text: str) -> str:
    expanded = text
    for acronym, full in ACRONYMS.items():
        pattern = re.compile(rf"\b{re.escape(acronym)}\b", re.IGNORECASE)
        expanded = pattern.sub(f"{acronym} ({full})", expanded)
    return expanded
