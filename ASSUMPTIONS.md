## Preliminary Fixes & Assumptions

I had issues starting the containers due to issues building chainlit_app. It was taking too long to resolve the dependencies so I made the following changes:

- Added `opentelemetry-instrumentation-groq==0.58.1` to `chainlit_app/requirements.txt` since `chainlit==2.5.5` (via literalai) was pulling in OpenTelemetry packages, and the resolver was trying to pull `opentelemetry-instrumentation-groq` because of how the dependency graph resolves.
- Updated `chainlit_app/Dockerfile` by modifying the Install Python dependencies step so that the step can have a timeout and also use the legacy resolver

## Tooling Assumption

A note on tooling: I used AI coding assistants (Cursor) during development, consistent with how I'd approach this work in a real engineering role. I reached out on **13-Jul-2026@11:20 AM** to confirm this was acceptable but hadn't received a response by the time I needed to begin, given the 72-hour window. Happy to discuss my usage and reasoning in more detail during review.

## Starter app changes

1. Move the assessment link from the root url to its own assignemnt endpoint so that the root (/) can be for health endpoint
