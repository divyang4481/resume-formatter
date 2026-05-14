import os
import boto3
import io
from docx import Document

async def inspect():
    bucket = "agentic-document-input-bucket" # Fallback
    key = "0dcafeac-dcd0-47ce-bcf0-516f4f57b037/FIN_BA_UK_Client_v1.docx" # Based on job log
    
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket, Key=key)
    data = response['Body'].read()
    
    doc = Document(io.BytesIO(data))
    for p in doc.paragraphs:
        if "Candidate" in p.text:
            print(f"TEXT: {p.text}")
            print(f"HEX: {p.text.encode('utf-8').hex()}")
            for run in p.runs:
                print(f"  RUN: {run.text} | HEX: {run.text.encode('utf-8').hex()}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(inspect())
