# AIFairTrack

**AI Fairness & Risk Monitoring Dashboard for LLMs & AR/VR Annotation Pipelines**  
*Version v0.1 — Public Release (Starter Kit)*

AIFairTrack is an open-source dashboard that evaluates fairness of NLP/LLM predictions and AR/VR annotation datasets. 
This starter kit includes a minimal Streamlit app, sample datasets, a whitepaper outline, policy mapping, and demo scripts.

## Quickstart
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
pip install -r requirements.txt
streamlit run aims_track/app.py
```
Then upload one of the sample files in `aims_track/examples/` and click **Evaluate**.

## Contents
- `aims_track/app.py` — Streamlit dashboard
- `aims_track/modules/metrics.py` — simple fairness metrics (disparate impact, rate gaps)
- `benchmarks/` — example results CSV
- `docs/` — threat model, policy mapping (NIST AI RMF table), quick start
- `whitepaper/outline.md` — 5–7 page scaffold
- `slides/demo_slides.md` — script for a 2-minute demo

## License
MIT
