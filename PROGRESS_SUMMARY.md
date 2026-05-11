# AMD Hackathon Progress Summary

Updated: 2026-05-08 19:58:09

## Goal

Build an actually agentic AI website builder for the AMD hackathon:

- understand a business from text + uploaded assets
- extract useful business signals with AMD GPU multimodal inference
- plan the site and workflows with a real agent graph
- critique and revise the design plan
- render a business-ready website/app flow from that plan
- run the full UI + AMD API flow in a real browser

## What We Built

### 1. Frontend demo app

Core frontend files:

- `index.html`
- `app.js`
- `styles.css`

Current capabilities:

- business intake form
- asset upload
- AMD inference trigger
- BuildSpec display
- generated website view
- admin/dashboard flow
- QA/readiness panel

### 2. AMD multimodal inference backend

Backend/API files:

- `amd_inference_server.py`
- `amd_vision_extract.py`
- `buildspec_planner.py`

This pipeline can:

- accept business text + uploaded images
- run multimodal extraction on AMD GPU
- return structured extraction results
- generate the old deterministic `buildSpec`
- run the new agentic graph and return planning artifacts

### 3. Schema-first agentic planning system

Agent system files:

- `agentic_models.py`
- `vertical_rulebooks.py`
- `agentic_planner.py`
- `agentic_graph.py`

Current graph stages:

1. `business_profile`
2. `requirements`
3. `design_candidates`
4. `critique`
5. `revise`

Current API response now includes:

- `businessProfile`
- `requirementsSpec`
- `designCandidates`
- `critiqueReports`
- `designSpec`

## Major Backend Progress

### Business profile is stable

We moved away from letting the model hallucinate deterministic known fields.

Current result:

- `name`, `location`, `goal` are preserved from input
- uncertain fields are inferred
- `businessProfile` is stable and no longer collapses due to wrapper noise

### Requirements semantics are cleaner

We fixed requirements normalization and separated:

- real `compliance_requirements`
- design anti-patterns in `avoid_patterns`

So we no longer pollute compliance with things like:

- `text-heavy hero copy`
- `hidden pricing`
- `weak food imagery`

### Candidate generation now has real structural divergence

This was a major step forward.

We now explicitly force two different strategy modes:

- `candidate_1`: conversion-first
- `candidate_2`: trust/browsing-first

This is no longer just a wording difference.

Latest successful AMD output showed:

#### Candidate 1

- `hero_offer_banner`
- `primary_workflow_form` early on the home page
- denser, action-first flow
- primary CTA: `Order Now`

#### Candidate 2

- `hero_trust_banner`
- `gallery_strip`
- `review_band`
- softer action placement
- primary CTA: `Explore Menu`

So the backend now produces meaningfully different design directions for the same input.

### Critique is no longer empty

The critic still leans fallback-heavy, but it now:

- produces a critique for every candidate
- marks a likely winner
- preserves strengths / weaknesses / revision instructions

This means the graph stays alive and returns usable downstream planning output.

### DesignSpec is now materially useful

`designSpec` now includes:

- chosen candidate id
- visual system
- primary action
- real pages
- real sections
- decision rationale

That is a real planning artifact now, not placeholder mush.

## Major Frontend Progress

### Frontend now follows backend `designSpec` much more faithfully

We patched `app.js` so the renderer is no longer mostly freelancing.

Important improvements:

- preserve full page + section metadata from backend `designSpec`
- detect actual hero type:
  - `hero_offer_banner`
  - `hero_trust_banner`
- render backend section types directly
- render additional planned pages beyond just the first page
- show planner rationale in the rendered output

New/updated section rendering now supports:

- `page_nav`
- `gallery_strip`
- `category_strip`
- `menu_showcase`
- `primary_workflow_form`
- `review_band`
- `trust_band`
- `proof_band`

This means the frontend can now visibly reflect:

- conversion-first plans
- trust/browsing-first plans

instead of making everything look like the same generic storefront.

### AMD server now serves the frontend too

We updated `amd_inference_server.py` so FastAPI serves:

- `/` -> `index.html`
- `/app.js`
- `/styles.css`
- `/jupyter-preview`

This is important because the old split setup:

- Jupyter page
- separate static server
- separate AMD API

created too many routing/proxy/browser-origin problems.

Now the intended deployment shape is:

- one server
- one origin
- one browser entrypoint

## Infrastructure / Deployment Lessons

### The old Jupyter proxy path is not reliable for this droplet

Important lesson:

The recreated droplet did **not** behave like the earlier environment.

These routes repeatedly failed or behaved inconsistently:

- `/proxy/3000`
- `/proxy/8000`
- `/lab/proxy/...`
- `/proxy/absolute/...`

So the old “open app through Jupyter proxy” approach should no longer be treated as the main path.

### The real serving blocker was Docker port mapping

The root issue was not the app code.

The `rocm` container was only exposing:

- `8888 -> 8888`

and not:

- `8000 -> 8000`

So:

- the app/API worked inside the container
- but could not be reached externally in a browser

This was diagnosed by:

- local health check succeeding inside the container
- external `Test-NetConnection ... -Port 8000` failing
- `docker ps` showing only port `8888` published

### Correct deployment shape now

The container must be started with both ports published:

- `8888` for Jupyter
- `8000` for the FastAPI app

That is the browser path we should use going forward.

## Current Known Good State

As of the latest checkpoint:

- Jupyter is running
- dependencies are reinstalled
- ROCm torch is fixed
- `uvicorn` runs successfully on `0.0.0.0:8000`
- `Test-NetConnection ... -Port 8000` succeeded
- `http://<droplet-ip>:8000/health` works
- `http://<droplet-ip>:8000/` opens the real app in browser

This is the first clean browser path we should trust.

## One Remaining Frontend Issue

The AMD API input field still defaults to `auto`, and that auto-resolution logic was written during the Jupyter proxy mess.

So when the page is now opened directly at:

- `http://<droplet-ip>:8000/`

the AMD button may still try old proxy candidates like:

- `/proxy/8000`
- `/proxy/absolute/8000`

and fail even though the real API is already on the same origin.

### Immediate workaround

Set the AMD inference API URL manually in the UI to:

```text
http://<droplet-ip>:8000
```

or eventually just `/`

### Next cleanup

Patch `auto` mode so it:

1. tries the current origin first
2. only falls back to Jupyter proxy candidates if needed

That should make the end-to-end browser flow finally feel normal again.

## Current Quality Snapshot

### Real now

- AMD GPU multimodal extraction
- typed LangGraph pipeline
- business profile inference
- requirements normalization
- candidate / critique / revision architecture
- strict schema enforcement
- deterministic fallback paths for malformed model outputs
- structurally divergent design candidates
- useful `designSpec`
- frontend renderer that follows backend planning much more directly
- single-server FastAPI deployment path for UI + API

### Still not fully solved

- critic quality is still too fallback-heavy
- subtype inference is still shallow
- some design rationale is still generic
- auto AMD endpoint detection needs to prefer same-origin direct mode
- full browser “Generate With AMD” flow still needs final cleanup after the new direct-port deployment

## Most Important Next Step

We are no longer blocked on:

- crashing schemas
- empty critiques
- hollow `designSpec`
- invisible frontend differences
- Jupyter-only viewing

The next best step is:

1. fix AMD API URL `auto` mode for direct browser deployment
2. confirm full browser `Generate With AMD` works against `:8000`
3. then improve:
   - critic quality
   - subtype inference
   - richer asset-grounded rationale

In short:

> the system now has a real backbone; the next work is finishing the clean browser flow and then improving quality.

## Key Files

- `index.html`
- `app.js`
- `styles.css`
- `jupyter_preview.html`
- `amd_inference_server.py`
- `amd_vision_extract.py`
- `buildspec_planner.py`
- `agentic_models.py`
- `vertical_rulebooks.py`
- `agentic_planner.py`
- `agentic_graph.py`

## Recommended Restart Checklist

If resuming later on a fresh AMD droplet:

1. Start the `rocm` container with both ports:

```bash
docker run -d --name rocm -p 8888:8888 -p 8000:8000 --device /dev/kfd --device /dev/dri --group-add video --cap-add SYS_PTRACE --security-opt seccomp=unconfined --security-opt apparmor=unconfined --shm-size 16G -e JUPYTER_TOKEN='...' rocm /bin/sh -c "jupyter lab --no-browser --notebook-dir=/home/rocm-user/jupyter --ServerApp.allow_remote_access=true --IdentityProvider.token=\${JUPYTER_TOKEN} --allow-root --ip=0.0.0.0"
```

2. Upload project files into `/home/rocm-user/jupyter`

3. Install dependencies:

```bash
cd /home/rocm-user/jupyter
pip install -r requirements-amd-server.txt
```

4. Verify ROCm torch:

```bash
python -c "import torch; print('torch', torch.__version__); print('hip', torch.version.hip); print('cuda available', torch.cuda.is_available()); print('device count', torch.cuda.device_count())"
```

5. Start the AMD app:

```bash
cd /home/rocm-user/jupyter
python -m uvicorn amd_inference_server:app --host 0.0.0.0 --port 8000
```

6. Test from laptop:

```powershell
Test-NetConnection <droplet-ip> -Port 8000
```

7. Open:

```text
http://<droplet-ip>:8000/
```

8. If AMD generate fails in browser, manually set AMD API URL to:

```text
http://<droplet-ip>:8000
```
