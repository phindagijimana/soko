"""Object storage backends."""

import boto3
from moto import mock_aws

from app.storage import LocalStorage, S3Storage, reset_storage_cache


def test_local_storage_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr('app.storage.settings.upload_dir', str(tmp_path / 'up'))
    monkeypatch.setattr('app.storage.settings.storage_backend', 'local')
    reset_storage_cache()
    st = LocalStorage()
    url = st.save('a.png', b'\x89PNG', 'image/png')
    assert url == '/media/a.png'
    assert (tmp_path / 'up' / 'a.png').read_bytes() == b'\x89PNG'


@mock_aws
def test_s3_storage_put_object(monkeypatch):
    conn = boto3.client('s3', region_name='us-east-1')
    conn.create_bucket(Bucket='testbucket')

    monkeypatch.setattr('app.storage.settings.storage_backend', 's3')
    monkeypatch.setattr('app.storage.settings.s3_bucket_name', 'testbucket')
    monkeypatch.setattr('app.storage.settings.aws_region', 'us-east-1')
    monkeypatch.setattr('app.storage.settings.aws_access_key_id', 'testing')
    monkeypatch.setattr('app.storage.settings.aws_secret_access_key', 'testing')
    monkeypatch.setattr('app.storage.settings.aws_endpoint_url', '')
    monkeypatch.setattr('app.storage.settings.media_public_base_url', 'https://cdn.example.com/media')
    reset_storage_cache()

    st = S3Storage()
    url = st.save('x.jpg', b'abc', 'image/jpeg')
    assert url == 'https://cdn.example.com/media/x.jpg'

    obj = conn.get_object(Bucket='testbucket', Key='x.jpg')
    assert obj['Body'].read() == b'abc'
