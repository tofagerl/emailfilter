#!/usr/bin/env python3
"""Example script demonstrating how to use the emailfilter package."""

import json
import os
from typing import Dict, List
from pprint import pprint

from emailfilter import filter

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
sample_file = os.path.join(script_dir, "sample_emails.json")

# Load sample emails
with open(sample_file, "r") as f:
    emails: List[Dict[str, str]] = json.load(f)

print("All emails:")
print(f"Total: {len(emails)}")
print("-" * 50)

# Filter emails from GitHub
github_filters: Dict[str, str] = {"from": "github.com"}
github_emails: List[Dict[str, str]] = filter.filter_emails(emails, github_filters)

print("\nGitHub emails:")
print(f"Total: {len(github_emails)}")
pprint(github_emails)
print("-" * 50)

# Filter emails with "Meeting" in the subject
meeting_filters: Dict[str, str] = {"subject": "Meeting"}
meeting_emails: List[Dict[str, str]] = filter.filter_emails(emails, meeting_filters)

print("\nMeeting emails:")
print(f"Total: {len(meeting_emails)}")
pprint(meeting_emails)
print("-" * 50)

# Filter emails sent by jane.smith@company.com
jane_filters: Dict[str, str] = {"from": "jane.smith@company.com"}
jane_emails: List[Dict[str, str]] = filter.filter_emails(emails, jane_filters)

print("\nEmails from Jane:")
print(f"Total: {len(jane_emails)}")
pprint(jane_emails)
print("-" * 50)

# Demonstrate the process_emails function
print("\nDemonstrating process_emails function:")
filter.process_emails() 