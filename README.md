# Collaboration API

[![Deployed on Vercel](https://img.shields.io/badge/Deployed%20on-Vercel-black?style=for-the-badge&logo=vercel)](https://vercel.com/likhonsheikhdev/v0-api-build-configuration)
[![Built with v0](https://img.shields.io/badge/Built%20with-v0.app-black?style=for-the-badge)](https://v0.app/chat/nLdwCeHL888)

An extended REST API for projects and real-time chat with AI integration.

## Features

*   **Project Management:** Create, update, and manage projects.
*   **Real-time Chat:** Real-time chat functionality with support for multiple participants.
*   **AI Integration:** Integrated with the Minimax AI for intelligent responses.
*   **Sequential Thinking:** A unique tool that allows the AI to break down complex problems into a series of thoughts.

## Getting Started

### Prerequisites

*   Python 3.8+
*   pip

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/your-repository.git
    ```
2.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Set the `MINIMAX_API_KEY` environment variable:
    ```bash
    export MINIMAX_API_KEY='your-api-key'
    ```
4.  Run the application:
    ```bash
    python api.py
    ```

## API Documentation

The complete API documentation can be found in the `/docs` directory. The OpenAPI specification is available in `docs/openapi.yaml`.

## Usage Examples

### AI Reply

**Endpoint:** `POST /v1/chats/{id}/ai/reply`

**Request Body:**

```json
{
  "sender_id": "user123"
}
```

### Sequential Thinking

The `sequential_thinking` endpoint allows you to generate a sequence of thoughts to solve a problem.

**Endpoint:** `POST /v1/chats/{id}/ai/think`

**Request Body:**

```json
{
  "prompt": "Optimize this blockchain consensus protocol for speed.",
  "goal": "Enhance throughput without security loss",
  "totalThoughts": 5
}
```

**Response:**

```json
{
  "thoughts": [
    {"id": 1, "content": "Identify bottlenecks in consensus steps."},
    {"id": 2, "content": "Explore parallel transaction validation."},
    {"id": 3, "content": "Evaluate tradeoffs in security vs. latency."},
    {"id": 4, "content": "Integrate lightweight cryptographic proofs."},
    {"id": 5, "content": "Conclude with hybrid consensus model summary."}
  ],
  "final_answer": "A hybrid consensus combining BFT and DAG ensures higher throughput with stable security guarantees."
}
```
