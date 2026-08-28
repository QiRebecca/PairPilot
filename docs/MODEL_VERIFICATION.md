# Gemini model verification

Live verification completed 2026-08-28 using Application Default Credentials
against Vertex AI in the dedicated hackathon project.

## Selected model

| Item | Verified value |
|---|---|
| Model ID | `gemini-3.7-flash` |
| Launch stage | GA |
| Model family | Gemini 3 Flash |
| Endpoint | Vertex AI `generateContent` publisher-model endpoint |
| API version | `v1` |
| Location | `global` |
| Authentication | OAuth access token derived from ADC; no API key |
| Runtime default thinking level | `LOW` for ordinary bounded agent turns |

This model is newer than the contest's required Gemini 3.5 minimum. The
official current model page lists function calling, structured output, and
pay-as-you-go support, which match PairPilot's ADK tool-calling workload.

## Authenticated smoke request

Request intent:

```text
Reply with exactly: PAIRPILOT_MODEL_OK
```

Sanitized response metadata:

```json
{
  "text": "PAIRPILOT_MODEL_OK",
  "finishReason": "STOP",
  "modelVersion": "gemini-3.7-flash",
  "responseId": "RLSRav-BIIG3mPUP7K_l8AI",
  "createTime": "2026-08-28T16:16:04.524543Z",
  "usageMetadata": {
    "promptTokenCount": 12,
    "candidatesTokenCount": 7,
    "totalTokenCount": 19,
    "trafficType": "ON_DEMAND"
  }
}
```

The HTTP request returned successfully from:

```text
https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/
publishers/google/models/gemini-3.7-flash:generateContent
```

No access token, refresh token, account email, or billing identifier is stored
in this report.

## No silent fallback

Production configuration will fail closed if `gemini-3.7-flash` is unavailable.
The UI and structured logs must display the model ID returned by the live
response. Development fallback is a separate, visibly labelled execution mode
and may not be used for the judging deployment.

## Sources

- [Gemini 3.7 Flash model page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-7-flash)
- [Gemini 3.7 Flash developer guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-7-flash)
- [Google Gen AI SDK overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/sdks/overview)

