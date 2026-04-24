"""SMS module: Twilio REST path and credential detection."""

from unittest.mock import MagicMock, patch

import pytest

from app import sms as sms_mod


def test_twilio_credentials_configured_false_for_placeholder(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, 'twilio_account_sid', 'placeholder')
    monkeypatch.setattr(sms_mod.settings, 'twilio_auth_token', 'placeholder')
    assert sms_mod.twilio_credentials_configured() is False


def test_twilio_credentials_configured_true_for_ac_sid(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, 'twilio_account_sid', 'AC' + 'a' * 31)  # 33 chars
    monkeypatch.setattr(sms_mod.settings, 'twilio_auth_token', 'not-placeholder')
    assert sms_mod.twilio_credentials_configured() is True


def test_sms_delivery_mode_placeholder_when_twilio_not_configured(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, 'sms_provider', 'twilio')
    monkeypatch.setattr(sms_mod.settings, 'twilio_account_sid', 'placeholder')
    assert sms_mod.sms_delivery_mode() == 'placeholder'


def test_sms_delivery_mode_file(monkeypatch):
    monkeypatch.setattr(sms_mod.settings, 'sms_provider', 'file')
    assert sms_mod.sms_delivery_mode() == 'file'


@patch('app.sms.httpx.Client')
def test_twilio_send_calls_api(mock_client_class, monkeypatch, tmp_path):
    monkeypatch.setattr(sms_mod.settings, 'sms_provider', 'twilio')
    monkeypatch.setattr(sms_mod.settings, 'twilio_account_sid', 'AC' + 'b' * 31)
    monkeypatch.setattr(sms_mod.settings, 'twilio_auth_token', 'secret-token')
    monkeypatch.setattr(sms_mod.settings, 'twilio_from_phone', '+15550001111')
    monkeypatch.setattr(sms_mod.settings, 'sms_status_callback_url', 'placeholder')
    monkeypatch.setattr(sms_mod.settings, 'sms_log_path', str(tmp_path / 'sms.txt'))

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {'sid': 'SM123', 'status': 'queued'}
    mock_response.text = 'ok'

    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.post.return_value = mock_response
    mock_client_class.return_value = mock_instance

    client = sms_mod.SMSClient()
    out = client.send('+250788000111', 'Hello')

    assert out['placeholder'] is False
    assert out['twilio_sid'] == 'SM123'
    mock_instance.post.assert_called_once()
    call_kw = mock_instance.post.call_args
    assert 'api.twilio.com' in str(call_kw)


@patch('app.sms.httpx.Client')
def test_twilio_send_raises_on_api_error(mock_client_class, monkeypatch, tmp_path):
    monkeypatch.setattr(sms_mod.settings, 'sms_provider', 'twilio')
    monkeypatch.setattr(sms_mod.settings, 'twilio_account_sid', 'AC' + 'c' * 31)
    monkeypatch.setattr(sms_mod.settings, 'twilio_auth_token', 'secret-token')
    monkeypatch.setattr(sms_mod.settings, 'twilio_from_phone', '+15550001111')
    monkeypatch.setattr(sms_mod.settings, 'sms_log_path', str(tmp_path / 'sms.txt'))

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {'message': 'Invalid phone'}
    mock_response.text = 'bad'

    mock_instance = MagicMock()
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    mock_instance.post.return_value = mock_response
    mock_client_class.return_value = mock_instance

    client = sms_mod.SMSClient()
    with pytest.raises(sms_mod.SMSDeliveryError, match='Twilio error'):
        client.send('+bad', 'x')
