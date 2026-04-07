#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo "Starting Red Moon Recovery..."
python app.py
