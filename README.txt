1) Put bot_detector_bundle.joblib into scripts/
2) Install Python packages:
   pip install -r scripts/requirements.txt
3) Install Node packages in project root:
   npm install express
4) Start server:
   node server.js
5) Test health:
   GET http://localhost:3000/health
6) Test scoring:
   POST http://localhost:3000/api/risk-score
   JSON body: {"events":[{"eventType":"mousemove","t_ms":10,"pageX":100,"pageY":100},{"eventType":"click","t_ms":50,"pageX":110,"pageY":110}]}

Windows note:
If Python is not found, set environment variable before starting Node:
set PYTHON_BIN=py
or in PowerShell:
$env:PYTHON_BIN="py"
