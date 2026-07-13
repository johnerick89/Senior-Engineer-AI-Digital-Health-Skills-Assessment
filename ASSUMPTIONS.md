## Preliminary Fixes & Assumptions

I had issues starting the containers due to issues building chainlit_app. It was taking too long to resolve the dependencies so I made the following changes:

- Added `opentelemetry-instrumentation-groq==0.58.1` to `chainlit_app/requirements.txt` since `chainlit==2.5.5` (via literalai) was pulling in OpenTelemetry packages, and the resolver was trying to pull `opentelemetry-instrumentation-groq` because of how the dependency graph resolves.
- Updated `chainlit_app/Dockerfile` by modifying the Install Python dependencies step so that the step can have a timeout and also use the legacy resolver
