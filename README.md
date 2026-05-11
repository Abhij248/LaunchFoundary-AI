# AMD Hackathon Starter

This folder contains the first AMD Developer Cloud/Jupyter starter pack for the autonomous AI web agency project.

## Files

- `amd_gpu_buildspec_starter.ipynb` - run this inside AMD Jupyter to verify ROCm/PyTorch GPU access and generate the first build spec.
- `buildspec_planner.py` - reusable planner logic for vertical inference, feature selection, missing info checks, and QA scoring.
- `requirements-amd.txt` - minimal packages for the notebook.
- `requirements-amd-vision.txt` - packages for Qwen2.5-VL image extraction on AMD GPU.
- `amd_vision_extract.py` - extracts business signals from uploaded images using a multimodal model.

## Run In AMD Jupyter

Open a terminal or notebook cell in the AMD Jupyter environment:

```bash
pip install -r requirements-amd.txt
```

Then open and run:

```text
amd_gpu_buildspec_starter.ipynb
```

The notebook checks:

- `rocm-smi`
- PyTorch GPU availability through `torch.cuda`
- Optional Qwen inference on GPU
- Build spec generation for restaurant and clinic examples

If model download is slow or blocked, the notebook still works using the local deterministic planner in `buildspec_planner.py`.

## Local Demo App

Open `index.html` in a browser to run the local product demo. The app supports:

- Business intake
- Business asset image upload
- Demo extraction of asset signals
- BuildSpec generation/import
- Generated website preview
- Working order/booking/lead workflow
- Admin dashboard
- QA/readiness report

The asset extraction step is intentionally shaped for AMD Developer Cloud: in the final demo, uploaded menus, flyers, brochures, storefront photos, and service images can be processed by a vision/multimodal model on AMD GPU, then converted into the same BuildSpec format the app already consumes.

## AMD Vision Extraction

Inside AMD Jupyter, install the vision dependencies:

```bash
pip install -r requirements-amd-vision.txt
```

Upload one or more images, then run:

```bash
python amd_vision_extract.py menu.jpg flyer.png
```

This writes:

- `asset-extractions.json` - structured model outputs for each image.
- `asset-signals.txt` - concise text you can add to the business details before generating the BuildSpec.

## Automated AMD API Flow

For the real product flow, users should not run notebooks. Run the AMD inference API on the AMD Developer Cloud instance:

```bash
pip install -r requirements-amd-server.txt
uvicorn amd_inference_server:app --host 0.0.0.0 --port 8000
```

Then in the local browser app:

1. Enter the AMD API URL, for example `http://YOUR_AMD_HOST:8000`.
2. Fill in business details.
3. Upload images.
4. Click `Generate With AMD`.

The app sends business details and images to `/generate-buildspec`. The AMD server runs Qwen2.5-VL on GPU, extracts asset signals, generates the BuildSpec, and returns it to the app automatically.
