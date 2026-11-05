# SweetSpot: LLM Inference Energy Efficiency Benchmark Dataset

- Source: https://doi.org/10.5281/zenodo.18714476
- Article: https://arxiv.org/abs/2602.05695
- Authors: Hiari Pizzini Cavagna, Andrea Proia, Giacomo Madella, Giovanni B. Esposito, Francesco Antici, Daniele Cesarini, Zeynep Kiziltan, and Andrea Bartolini
- License: Creative Commons Attribution 4.0 International (CC BY 4.0)
- Downloaded file: `dataset.zip` (4,981,037 bytes)
- MD5: `99ab713606e5b59dd7b09715b2d306ce`

The archive contains summary CSV tables and power traces for 13 models measured on NVIDIA H100 with TensorRT-LLM. The tables include controlled input/output lengths, request counts, energy, and energy per output token.

`validation_sweetspot_v02.py` audits all 13 summary tables against the local CompareAI model names. It documents three plausible model/version links and evaluates output-only, additive input/output, and power-law input/output models on a deterministic 80/20 split of SweetSpot configurations. It also applies held-out CompareAI coefficients to SweetSpot's exact input/output lengths as an external transfer check. Results are kept separate from CompareAI because SweetSpot reports measurements from a specific hardware and inference-engine configuration, while CompareAI provides provider-side estimates. The audit and result tables are saved beside this file.
