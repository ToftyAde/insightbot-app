#!/usr/bin/env python
import os, sys, json, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cfg = ROOT / "configs"
data = ROOT / "data" / "sources"

def count_csv(p):
    import csv
    with open(p, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # minus header

def main():
    train_csv = data / "sources_train.csv"
    test_csv = data / "sources_test.csv"
    print(f"Training sources: {count_csv(train_csv)}")
    print(f"Testing sources: {count_csv(test_csv)}")
    # Show a couple examples
    import json
    with open(data / "sources_train.json", encoding="utf-8") as f:
        arr = json.load(f)
    print('Example training source:', arr[0])

if __name__ == "__main__":
    main()
