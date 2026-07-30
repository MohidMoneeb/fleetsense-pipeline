"""Credential helper: use Streamlit secrets when deployed, local AWS config when running locally.
Import this and call boto3_kwargs() wherever you build a boto3 client/resource.
"""
import os

def boto3_kwargs():
    """Return kwargs for boto3.resource/client. On Streamlit Cloud, reads st.secrets;
    locally, returns just the region so your ~/.aws profile is used."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    try:
        import streamlit as st
        if "AWS_ACCESS_KEY_ID" in st.secrets:
            return {
                "region_name": st.secrets.get("AWS_REGION", region),
                "aws_access_key_id": st.secrets["AWS_ACCESS_KEY_ID"],
                "aws_secret_access_key": st.secrets["AWS_SECRET_ACCESS_KEY"],
            }
    except Exception:
        pass
    return {"region_name": region}
