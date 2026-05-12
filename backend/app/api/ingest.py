from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from app.services.document_ingestion_service import extract_upload_files


router = APIRouter()


class IngestedDocument(BaseModel):
    filename: str
    content_type: str
    text: str
    warnings: list[str]


class IngestResponse(BaseModel):
    documents: list[IngestedDocument]
    combined_text: str
    warnings: list[str]


@router.post("/documents", response_model=IngestResponse)
async def ingest_documents(files: list[UploadFile] = File(...)):
    documents, combined_text, warnings = await extract_upload_files(files)
    return IngestResponse(
        documents=[
            IngestedDocument(
                filename=doc.filename,
                content_type=doc.content_type,
                text=doc.text,
                warnings=doc.warnings,
            )
            for doc in documents
        ],
        combined_text=combined_text,
        warnings=warnings,
    )
