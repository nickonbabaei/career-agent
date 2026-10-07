#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  print 'The project virtual environment is missing. Complete README setup first.'
  read '?Press Return to close.'
  exit 1
fi
.venv/bin/python -m server.app --open
if [[ $? -ne 0 ]]; then
  print 'If Career Desk is already running, open http://127.0.0.1:8765 in your browser.'
  read '?Press Return to close.'
fi
