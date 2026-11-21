#!/usr/bin/env python3
"""Append the first Gemini 4 Carbon High run."""
from export_neon import Publication, main

CARBON = Publication(
    'carbon-high-01', 'gemini-4-carbon-high', 'high', '2026-11-21', '1.11.0', '1.10.0',
    '2026-11-21', (2, .10, 10), 'https://cloud.google.com/model-garden/pricing', 'carbon', 102,
)


if __name__ == '__main__':
    main(CARBON)
