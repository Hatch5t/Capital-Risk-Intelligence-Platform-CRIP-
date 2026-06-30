# Future Plans for CRIP (Capital Risk Intelligence Platform)

This document outlines the strategic roadmap for scaling, improving, and deploying the CRIP platform.

## 1. General Improvements & Improvisation
- **Advanced Caching:** Implement aggressive caching mechanisms (e.g., Redis or Streamlit's `@st.cache_data`) for dataset processing, report generation, and API responses to eliminate redundant page reloads and improve performance.
- **Enhanced UI/UX:** Upgrade the Streamlit UI with better state management, custom CSS, or migrate the frontend to a dedicated framework (e.g., Next.js or React) to allow for more complex, dynamic, and responsive designs.
- **Asynchronous Processing:** Move heavy tasks like actuarial report generation and model training to background workers (e.g., Celery, RabbitMQ) to keep the frontend highly responsive.

## 2. Implementing RAG (Retrieval-Augmented Generation)
Integrating RAG will allow the Chat Agent to answer questions directly from internal documents, past risk reports, and compliance guidelines without retraining models.
- **Vector Database Setup:** Integrate a vector database like Pinecone, ChromaDB, or Qdrant to store embeddings of textual documents, compliance rules, and historical reports.
- **Embedding Pipelines:** Use embedding models to chunk and vectorize incoming PDFs and text documents.
- **Agent Integration:** Update the `chat_agent.py` to first query the vector database for relevant context before passing the user prompt to the LLM. This provides factual, context-aware responses and reduces hallucinations.

## 3. Dynamic Dataset Handling (Schema Agnostic Processing)
To support different types of datasets that don't match the exact hardcoded column structures:
- **LLM-Powered Data Mapping:** Use an LLM to inspect the columns of newly uploaded datasets and automatically map them to the platform's required standard features (e.g., mapping `Client_Age`, `BirthDate`, or `DOB` to a standard `Age` feature).
- **Data Profiling & Schema Inference:** Integrate libraries like `ydata-profiling` or `Great Expectations` to automatically infer column types and statistical properties upon upload.
- **Flexible Pipeline Configurations:** Refactor the `data_governance`, `pricing`, and `orchestrator` pipelines to rely on metadata configurations rather than hardcoded column names, dynamically adjusting the workflow based on available features.

## 4. Cloud Hosting and Going Public
Transitioning from local development to a public, scalable cloud infrastructure:
- **Containerization (Docker):** Create a `Dockerfile` and `docker-compose.yml` to package the app, its dependencies (from `requirements.txt`), and any databases into consistent, portable containers.
- **Cloud Provider (AWS / GCP / Azure):**
  - **Compute:** Deploy the Docker containers to managed serverless compute services like Google Cloud Run, AWS App Runner, or AWS Fargate for auto-scaling capabilities.
  - **Storage:** Use cloud object storage (e.g., AWS S3, Google Cloud Storage) to securely handle uploaded user datasets and generated PDF reports instead of saving them to the local filesystem.
- **CI/CD Pipeline:** Implement GitHub Actions to automatically lint, test, and deploy code changes to the cloud environment whenever a new commit is pushed.
- **Security & Authentication:** Integrate robust user authentication (e.g., Auth0, Firebase Auth, or Clerk) to protect public access and ensure all data transmitted over the internet is secured via HTTPS/SSL.
