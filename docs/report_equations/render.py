"""Render report display equations as GitHub-compatible PNGs.

Run: MPLCONFIGDIR=/private/tmp/orie_mpl python docs/report_equations/render.py
Editable mathematical sources are in equations.json next to this script.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent

def main():
    for entry in json.loads((ROOT / 'equations.json').read_text()):
        # Separate long comma-delimited clauses where the source already wrapped.
        lines = [line.strip() for line in entry['latex'].splitlines() if line.strip()]
        fig = plt.figure(figsize=(10, max(.6, .55 * len(lines))), facecolor='white')
        for i, line in enumerate(lines):
            fig.text(.03, 1-(i+.5)/len(lines), '$'+line+'$', fontsize=16,
                     va='center', color='#172B40')
        fig.savefig(ROOT / (entry['name']+'.png'), dpi=180,
                    bbox_inches='tight', pad_inches=.16, facecolor='white')
        plt.close(fig)

if __name__ == '__main__':
    main()
